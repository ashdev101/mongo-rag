from copy import deepcopy

class AggregationRBAC:
    """
    Class to enforce role-based access conditions on MongoDB aggregation pipelines.
    """

    def __init__(self, user: dict):
        """
        user structure expected:
        {
            "isHR": bool,
            "employeeCode": 7207,
            "region": ["APAC", "EMEA"],
            "department": ["HR", "Finance"],
            "grades": ["A", "B"]
        }
        """
        self.user = user
        self.security_filter = self._build_security_filter()

    # --------------------------------------------
    #  Internal helpers
    # --------------------------------------------

    def _build_security_filter(self):
        """Builds the $match RBAC filter based on the user type."""

        # Normal user → only employee-code access
        if not self.user.get("isHR", False):
            return {"employee code": self.user["employeeCode"]}

        # HR user → controlled access based on lists
        filters = []
        if self.user.get("region"):
            filters.append({"region": {"$in": self.user["region"]}})
        if self.user.get("department"):
            filters.append({"department": {"$in": self.user["department"]}})
        if self.user.get("grades"):
            filters.append({"grade": {"$in": self.user["grades"]}})

        # If no restrictions provided → unrestricted (no security filter needed)
        if not filters:
            return {}

        return {"$and": filters} if len(filters) > 1 else filters[0]

    def _inject_match(self, existing_match):
        """
        Merges RBAC with existing $match safely.
        Avoids generating: {'$and': [existing, {}]} or useless duplicate conditions.
        """

        # If no RBAC filter needed (HR unrestricted)
        if self.security_filter == {}:
            return existing_match

        # If pipeline already restricts to this employee (normal user)
        if (
            not self.user.get("isHR", False)
            and isinstance(existing_match, dict)
            and existing_match.get("employee code") == self.user["employeeCode"]
        ):
            return existing_match

        # If existing match is identical to RBAC rule
        if existing_match == self.security_filter:
            return existing_match

        # Safe AND merge
        return {"$and": [existing_match, self.security_filter]}

    def _process_lookup(self, stage):
        """Converts $lookup to pipeline form if required and injects RBAC filter."""
        lookup = stage["$lookup"]

        # No RBAC restriction → do nothing
        if not self.security_filter:
            return stage

        # If lookup already has pipeline → prepend RBAC filter
        if "pipeline" in lookup:
            lookup["pipeline"].insert(0, {"$match": self.security_filter})
            return stage

        # Convert shorthand lookup to pipeline form
        new_lookup = {
            "from": lookup["from"],
            "let": {"lf": f"${lookup['localField']}"},
            "pipeline": [
                {"$match": self.security_filter},  # RBAC FIRST
                {"$match": {"$expr": {"$eq": [f"${lookup['foreignField']}", "$$lf"]}}}  # JOIN SECOND
            ],
            "as": lookup["as"],
        }

        stage["$lookup"] = new_lookup
        return stage       # ← the missing return was the bug


    def _process_facet(self, stage):
        """Inject security match into each facet sub-pipeline."""
        facet = stage["$facet"]
        
        if not self.security_filter:
            return stage

        for name, sub_pipeline in facet.items():
            if not sub_pipeline:
                sub_pipeline.insert(0, {"$match": self.security_filter})
                continue

            head = sub_pipeline[0]
            if "$match" in head:
                sub_pipeline[0]["$match"] = self._inject_match(head["$match"])
            else:
                sub_pipeline.insert(0, {"$match": self.security_filter})

        return stage

    def _process_union_with(self, stage):
        """Adds RBAC restriction to $unionWith."""
        uw = stage["$unionWith"]
        if not self.security_filter:
            return stage

        # No RBAC filter needed
        if self.security_filter == {}:
            return stage

        if isinstance(uw, str):  # shorthand
            stage["$unionWith"] = {
                "coll": uw,
                "pipeline": [{"$match": self.security_filter}]
            }
        else:
            uw.setdefault("pipeline", [])
            uw["pipeline"].insert(0, {"$match": self.security_filter})

        return stage

    # --------------------------------------------
    #  Public API
    # --------------------------------------------

    def enforce(self, pipeline: list):
        pipeline = deepcopy(pipeline)
        injected = False
        print("input pipeline:", pipeline)

        for i, stage in enumerate(pipeline):

            if "$match" in stage and not injected and self.security_filter:
                pipeline[i]["$match"] = self._inject_match(stage["$match"])
                injected = True

            elif "$lookup" in stage:
                pipeline[i] = self._process_lookup(stage)
                if not injected and self.security_filter:
                    pipeline.insert(0, {"$match": self.security_filter})
                    injected = True

            elif "$facet" in stage:
                pipeline[i] = self._process_facet(stage)

            elif "$unionWith" in stage:
                pipeline[i] = self._process_union_with(stage)

        if not injected and self.security_filter:
            pipeline.insert(0, {"$match": self.security_filter})

        print("output pipeline:", pipeline)

        return pipeline





if __name__ == "__main__":
    import unittest
    from copy import deepcopy


    class TestAggregationRBAC(unittest.TestCase):

        @classmethod
        def setUpClass(cls):
            cls.normal_user = {
                "isHR": False,
                "employeeCode": 7207,
                "region": [],
                "department": [],
                "grades": []
            }

            cls.hr_user_scoped = {
                "isHR": True,
                "employeeCode": None,
                "region": ["APAC"],
                "department": ["HR"],
                "grades": ["A"]
            }

            cls.hr_user_unrestricted = {
                "isHR": True,
                "employeeCode": None,
                "region": [],
                "department": [],
                "grades": []
            }

        # ---------------------------------------------------
        # NORMAL USER (6 tests)
        # ---------------------------------------------------

        def test_normal_user_match_already_correct(self):
            pipeline = [{"$match": {"employee code": 7207}}]
            result = AggregationRBAC(self.normal_user).enforce(deepcopy(pipeline))
            self.assertEqual(result, pipeline)

        def test_normal_user_no_match(self):
            pipeline = [{"$project": {"name": 1}}]
            result = AggregationRBAC(self.normal_user).enforce(deepcopy(pipeline))
            self.assertEqual(result[0], {"$match": {"employee code": 7207}})

        def test_normal_user_existing_other_match(self):
            pipeline = [{"$match": {"department": "HR"}}]
            result = AggregationRBAC(self.normal_user).enforce(deepcopy(pipeline))
            self.assertEqual(
                result[0],
                {"$match": {"$and": [{"department": "HR"}, {"employee code": 7207}]}}
            )

        def test_lookup_short_form_normal_user(self):
            pipeline = [{"$lookup": {
                "from": "goals",
                "localField": "employee code",
                "foreignField": "employee code",
                "as": "goalData"
            }}]
            result = AggregationRBAC(self.normal_user).enforce(deepcopy(pipeline))
            lookup = result[1]["$lookup"]  # changed index from 0 → 1
            self.assertIn("pipeline", lookup)
            self.assertEqual(lookup["pipeline"][0]["$match"], {"employee code": 7207})

        def test_facet_injection_normal_user(self):
            pipeline = [{"$facet": {
                "f1": [{"$project": {"x": 1}}],
                "f2": [{"$match": {"grade": "A"}}, {"$project": {"y": 1}}]
            }}]
            result = AggregationRBAC(self.normal_user).enforce(deepcopy(pipeline))
            self.assertEqual(
                result[1]["$facet"]["f1"][0],
                {"$match": {"employee code": 7207}}
            )

        def test_union_with_string_normal_user(self):
            pipeline = [{"$unionWith": "goals"}]
            result = AggregationRBAC(self.normal_user).enforce(deepcopy(pipeline))
            self.assertEqual(
                result[1]["$unionWith"]["pipeline"][0],
                {"$match": {"employee code": 7207}}
            )


        # ---------------------------------------------------
        # HR SCOPED USER (4 tests)
        # ---------------------------------------------------

        def test_hr_scoped_no_match(self):
            pipeline = [{"$project": {"name": 1}}]
            result = AggregationRBAC(self.hr_user_scoped).enforce(deepcopy(pipeline))
            self.assertEqual(
                result[0],
                {"$match": {"$and": [
                    {"region": {"$in": ["APAC"]}},
                    {"department": {"$in": ["HR"]}},
                    {"grade": {"$in": ["A"]}}
                ]}}
            )

        def test_hr_scoped_existing_match(self):
            pipeline = [{"$match": {"region": "APAC"}}]
            result = AggregationRBAC(self.hr_user_scoped).enforce(deepcopy(pipeline))
            self.assertIn("$and", result[0]["$match"])

        def test_lookup_pipeline_form_hr(self):
            pipeline = [{"$lookup": {
                "from": "goals",
                "pipeline": [{"$project": {"status": 1}}],
                "as": "goalData"
            }}]
            result = AggregationRBAC(self.hr_user_scoped).enforce(deepcopy(pipeline))
            lookup = result[1]["$lookup"]  # changed index from 0 → 1
            self.assertIn("$match", lookup["pipeline"][0])


        def test_union_with_pipeline_hr_scoped(self):
            pipeline = [{"$unionWith": {"coll": "goals", "pipeline": [{"$project": {"z": 1}}]}}]
            result = AggregationRBAC(self.hr_user_scoped).enforce(deepcopy(pipeline))
            uw = result[1]["$unionWith"]  # changed index from 0 → 1
            self.assertIn("$match", uw["pipeline"][0])


        # ---------------------------------------------------
        # HR UNRESTRICTED USER (2 tests)
        # ---------------------------------------------------

        def test_hr_unrestricted_no_match(self):
            pipeline = [{"$project": {"x": 1}}]
            result = AggregationRBAC(self.hr_user_unrestricted).enforce(deepcopy(pipeline))
            self.assertEqual(result, pipeline)  # should not insert match

        def test_hr_unrestricted_existing_match(self):
            pipeline = [{"$match": {"region": "APAC"}}]
            result = AggregationRBAC(self.hr_user_unrestricted).enforce(deepcopy(pipeline))
            self.assertEqual(result, pipeline)  # should not modify match



    unittest.main()
