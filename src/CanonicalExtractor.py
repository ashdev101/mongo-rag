from rapidfuzz import process, fuzz
from databse_dsitcint_values import CANONICAL_GRADES, CANONICAL_DEPARTMENTS, CANONICAL_REGIONS

import re

class CanonicalExtractor:
    def __init__(self, grades, departments, regions, score_threshold=80):
        self.grades = [g.lower() for g in grades]
        self.departments = [d.lower() for d in departments]
        self.regions = [r.lower() for r in regions]
        self.score_threshold = score_threshold

    def _clean(self, text: str):
        return re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()

    def _find_grades(self, query: str):
        # detect patterns like M1 / m1 / m01 etc
        grades = re.findall(r"\bm[0-6]\b", query)
        return sorted(set(g.upper() for g in grades))

    def _generate_phrases(self, words, max_n=3):
        for n in range(1, max_n + 1):
            for i in range(len(words) - n + 1):
                yield " ".join(words[i:i + n])

    def _fuzzy_best_matches(self, phrases, canonical):
        results = set()

        for p in phrases:
            match, score, _ = process.extractOne(p, canonical, scorer=fuzz.token_sort_ratio)
            if score >= self.score_threshold:
                results.add(match)

        # ---- refinement: remove generic substring matches if a more specific one exists ----
        final = set(results)
        for a in results:
            for b in results:
                if a != b and a in b and len(a) < len(b):
                    # a is shorter and substring of b → drop a
                    if a in final:
                        final.remove(a)

        return list(final)

    
    def sanitize_result(result: dict) -> dict:
        """
        Remove any values from the extraction result that are not part of original canonical lists.
        """
        clean = {
            "grades": [g for g in result.get("grades", []) if g in CANONICAL_GRADES],
            "departments": [d for d in result.get("departments", []) if d in CANONICAL_DEPARTMENTS],
            "regions": [r for r in result.get("regions", []) if r in CANONICAL_REGIONS],
        }
        return clean
              

    def extract(self, query: str):
        cleaned = self._clean(query)
        words = cleaned.split()

        grades = self._find_grades(cleaned)
        phrases = list(self._generate_phrases(words, max_n=4))

        departments = self._fuzzy_best_matches(phrases, self.departments)
        regions = self._fuzzy_best_matches(phrases, self.regions)

        result = {
            "grades": grades,
            "departments": [d.title() for d in set(departments)],
            "regions": [r.title() for r in set(regions)],
        }

        return CanonicalExtractor.sanitize_result(result)





if __name__ == "__main__":
    grades = CANONICAL_GRADES
    departments = CANONICAL_DEPARTMENTS
    regions = CANONICAL_REGIONS

    extractor = CanonicalExtractor(grades, departments, regions )

    TEST_CASES = [
        {
            "query": "show the employees who left the company last quarter specifically from the north and west regions and in business development or b2b and only for m1 and m2 band",
            "expected": {
                "grades": ["M1", "M2"],
                "departments": ["Business Development", "B2B"],
                "regions": ["North", "West"]
            }
        },
        {
            "query": "i need attrition data for guys in corporate or north zone who resigned from facilities or executive office this year any grade but prefer m0 m1",
            "expected": {
                "grades": ["M0", "M1"],
                "departments": ["Facilities", "Executive Office"],
                "regions": ["Corporate", "North"]
            }
        },
        {
            "query": "pull a list of all the people who moved out of the organization from the west region belonging to business development grade m2 only",
            "expected": {
                "grades": ["M2"],
                "departments": ["Business Development"],
                "regions": ["West"]
            }
        },
        {
            "query": "fetch the resignations from interactive services across north and central regions especially from grades m1 m3",
            "expected": {
                "grades": ["M1", "M3"],
                "departments": ["Interactive Services"],
                "regions": ["North", "Central"]
            }
        },
        {
            "query": "share resignations count from facilities and finance for west and north grades m0 m1 m2 only",
            "expected": {
                "grades": ["M0", "M1", "M2"],
                "departments": ["Facilities", "Finance"],
                "regions": ["West", "North"]
            }
        },
        {
            "query": "query attrition of employees leaving from corporate region with grades m1 to m4 from business development and executive office",
            "expected": {
                "grades": ["M1", "M2", "M3", "M4"],
                "departments": ["Business Development", "Executive Office"],
                "regions": ["Corporate"]
            }
        },
        {
            "query": "pls share 2025 resigns from WEST & NORTH only for m1 m2 in b2b or busines developmint",
            "expected": {
                "grades": ["M1", "M2"],
                "departments": ["B2B", "Business Development"],
                "regions": ["West", "North"]
            }
        },
        {
            "query": "fetch resignation from corporat region grade m1 m2 m3 facilites deparmnt",
            "expected": {
                "grades": ["M1", "M2", "M3"],
                "departments": ["Facilities"],
                "regions": ["Corporate"]
            }
        },
        {
            "query": "attrtion for west > north > b2b + facilities grade m1 m2 asap",
            "expected": {
                "grades": ["M1", "M2"],
                "departments": ["B2B", "Facilities"],
                "regions": ["West", "North"]
            }
        },
        {
            "query": "who left org this year grade M2 M1 regions north west dep business develeopment",
            "expected": {
                "grades": ["M1", "M2"],
                "departments": ["Business Development"],
                "regions": ["North", "West"]
            }
        },
        {
            "query": "year 2025 resigneees from corporate and north for M1 to M2 from b2b only",
            "expected": {
                "grades": ["M1", "M2"],
                "departments": ["B2B"],
                "regions": ["Corporate", "North"]
            }
        },
        {
            "query": "employees resigned from m1 m2 bands belonging to north and west departments business dev exec office interactive service",
            "expected": {
                "grades": ["M1", "M2"],
                "departments": ["Business Development", "Executive Office", "Interactive Services"],
                "regions": ["North", "West"]
            }
        }
    ]


    from pprint import pprint

    def run_tests():
        passed = 0
        failed = 0

        for i, case in enumerate(TEST_CASES, start=1):
            output = extractor.extract(case["query"])
            
            # Sort for comparison (order not important)
            exp = {k: sorted(v) for k, v in case["expected"].items()}
            got = {k: sorted(v) for k, v in output.items()}

            if exp == got:
                print(f"✅ Test {i} PASSED")
                passed += 1
            else:
                print(f"❌ Test {i} FAILED")
                print("Query:", case["query"])
                print("Expected:")
                pprint(exp)
                print("Got:")
                pprint(got)
                print("-" * 80)
                failed += 1

        print("\n============ FINAL SUMMARY ============")
        print(f"Total: {len(TEST_CASES)}, Passed: {passed}, Failed: {failed}")

    run_tests()
