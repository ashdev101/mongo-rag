from rapidfuzz import process, fuzz
from databse_dsitcint_values import CANONICAL_GRADES, CANONICAL_DEPARTMENTS, CANONICAL_REGIONS

class CanonicalExtractor:
    def __init__(self, grades, departments, regions, score_threshold=75):
        self.grades = grades
        self.departments = departments
        self.regions = regions
        self.score_threshold = score_threshold

    def _match_items(self, query, canonical_list):
        query = query.lower()
        results = []

        for item in canonical_list:
            match, score, _ = process.extractOne(
                query, [item], scorer=fuzz.partial_ratio
            )
            if score >= self.score_threshold:
                results.append(item)
        return list(set(results))

    def extract(self, query: str) -> dict:
        return {
            "grades": self._match_items(query, self.grades),
            "departments": self._match_items(query, self.departments),
            "regions": self._match_items(query, self.regions)
        }


if __name__ == "__main__":
    grades = CANONICAL_GRADES
    departments = CANONICAL_DEPARTMENTS
    regions = CANONICAL_REGIONS

    extractor = CanonicalExtractor(grades, departments, regions , score_threshold=50)

    query = "Give me the list of m2 and m4 employees from HR and fynence in eats and wyst."
    result = extractor.extract(query)
    print(result)