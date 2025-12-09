import unittest
from pprint import pprint
from aggregation.AggregationRBAC import AggregationRBAC

# Assuming AggregationRBAC is already imported from your module
# from rbac_module import AggregationRBAC

class TestAggregationRBAC(unittest.TestCase):

    def test_normal_user_simple_project(self):
        user = {"isHR": False, "employeeCode": 7207}
        pipeline = [{"$project": {"name": 1, "_id": 0}}]

        rbac = AggregationRBAC(user)
        secure_pipeline = rbac.enforce(pipeline)

        expected = [
            {"$match": {"employee code": 7207}},
            {"$project": {"name": 1, "_id": 0}}
        ]

        self.assertEqual(secure_pipeline, expected)

    def test_hr_user_with_match_and_lookup(self):
        user = {
            "isHR": True,
            "region": ["APAC", "EMEA"],
            "department": ["HR", "Finance"],
            "grades": ["A", "B"]
        }

        pipeline = [
            {"$match": {"status": "active"}},
            {"$lookup": {
                "from": "goal",
                "localField": "employee code",
                "foreignField": "employee code",
                "as": "goals"
            }}
        ]

        rbac = AggregationRBAC(user)
        secure_pipeline = rbac.enforce(pipeline)

        expected_match = {
            "$match": {
                "$and": [
                    {"status": "active"},
                    {
                        "region": {"$in": ["APAC", "EMEA"]},
                        "department": {"$in": ["HR", "Finance"]},
                        "grade": {"$in": ["A", "B"]}
                    }
                ]
            }
        }

        expected_lookup = {
            "$lookup": {
                "from": "goal",
                "let": {"lf": "$employee code"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$employee code", "$$lf"]}}},
                    {"$match": {
                        "region": {"$in": ["APAC", "EMEA"]},
                        "department": {"$in": ["HR", "Finance"]},
                        "grade": {"$in": ["A", "B"]}
                    }}
                ],
                "as": "goals"
            }
        }

        expected_pipeline = [expected_match, expected_lookup]

        self.assertEqual(secure_pipeline, expected_pipeline)

    def test_facet_pipeline_hr(self):
        user = {
            "isHR": True,
            "region": ["APAC"],
            "department": ["HR"],
            "grades": ["A"]
        }

        pipeline = [
            {"$facet": {
                "summary": [{"$group": {"_id": "$grade", "count": {"$sum": 1}}}],
                "details": [{"$project": {"name": 1}}]
            }}
        ]

        rbac = AggregationRBAC(user)
        secure_pipeline = rbac.enforce(pipeline)

        expected_facet = {
            "$facet": {
                "summary": [
                    {"$match": {
                        "region": {"$in": ["APAC"]},
                        "department": {"$in": ["HR"]},
                        "grade": {"$in": ["A"]}
                    }},
                    {"$group": {"_id": "$grade", "count": {"$sum": 1}}}
                ],
                "details": [
                    {"$match": {
                        "region": {"$in": ["APAC"]},
                        "department": {"$in": ["HR"]},
                        "grade": {"$in": ["A"]}
                    }},
                    {"$project": {"name": 1}}
                ]
            }
        }

        self.assertEqual(secure_pipeline, [expected_facet])

    def test_union_with_normal_user(self):
        user = {"isHR": False, "employeeCode": 9999}
        pipeline = [
            {"$unionWith": "reviews"}
        ]

        rbac = AggregationRBAC(user)
        secure_pipeline = rbac.enforce(pipeline)

        expected = [
            {"$match": {"employee code": 9999}},
            {"$unionWith": {"coll": "reviews", "pipeline": [{"$match": {"employee code": 9999}}]}}
        ]

        self.assertEqual(secure_pipeline, expected)

    def test_nested_lookup_inside_facet(self):
        user = {"isHR": False, "employeeCode": 1234}
        pipeline = [
            {"$facet": {
                "details": [
                    {"$lookup": {
                        "from": "goals",
                        "localField": "employee code",
                        "foreignField": "employee code",
                        "as": "goals"
                    }},
                    {"$project": {"status": 1}}
                ]
            }}
        ]

        rbac = AggregationRBAC(user)
        secure_pipeline = rbac.enforce(pipeline)

        expected = [
            {"$facet": {
                "details": [
                    {"$match": {"employee code": 1234}},
                    {"$lookup": {
                        "from": "goals",
                        "let": {"lf": "$employee code"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["$employee code", "$$lf"]}}},
                            {"$match": {"employee code": 1234}}
                        ],
                        "as": "goals"
                    }},
                    {"$project": {"status": 1}}
                ]
            }}
        ]

        self.assertEqual(secure_pipeline, expected)


if __name__ == "__main__":
    unittest.main()
