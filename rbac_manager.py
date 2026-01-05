#!/usr/bin/env python3
"""
RBAC Manager for Claude QnA System

Manages role-based access control using employee code and access_record.json.
Injects MongoDB aggregation pipeline filters to enforce data access permissions.
"""

import json
import os
from typing import Dict, List, Optional, Any


class RBACManager:
    """Manages role-based access control for MongoDB queries"""

    def __init__(self, access_record_path: str = "json_repo/access_record.json"):
        """
        Initialize RBAC manager with access control records.

        Args:
            access_record_path: Path to access_record.json file
        """
        self.access_record_path = access_record_path
        self.access_records = self._load_access_records()

        # Field name mappings for different collections
        # Some collections use different case/naming conventions
        self.field_mappings = {
            "region": ["Region", "region", "REGION"],
            "grade": ["GRADE", "Grade", "grade"],
            "department": ["DEPARTMENT", "Department", "department"]
        }

    def _load_access_records(self) -> List[Dict]:
        """Load access records from JSON file"""
        try:
            with open(self.access_record_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Access record file not found at {self.access_record_path}")
            return []
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {self.access_record_path}")
            return []

    def get_user_permissions(self, emp_code: int) -> Optional[Dict[str, Any]]:
        """
        Get user permissions by employee code.

        Args:
            emp_code: Employee code

        Returns:
            Dictionary with permissions:
            {
                "emp_code": 7190,
                "name": "Ashwin Shukla",
                "designation": "Senior Vice President - Human Resources",
                "regions": ["Central","Corporate","East","North","South","West"],
                "grades": ["M0","M1","M2","M3","M4","M5","M6"],
                "departments": [],  # empty means all departments
                "full_access": True  # if all regions, all grades, empty dept restrictions
            }
        """
        for record in self.access_records:
            if record["Emp Code"] == emp_code:
                # Extract permissions
                regions = record.get("Region", [])
                grades = record.get("Grade", [])
                departments = record.get("Department_exception", [])

                # Determine if user has full access
                all_regions = {"Central", "Corporate", "East", "North", "South", "West"}
                all_grades = {"M0", "M1", "M2", "M3", "M4", "M5", "M6"}
                has_all_regions = set(regions) == all_regions
                has_all_grades = set(grades) == all_grades
                has_no_dept_restrictions = len(departments) == 0

                full_access = has_all_regions and has_all_grades and has_no_dept_restrictions

                return {
                    "emp_code": emp_code,
                    "name": f"{record.get('NAME', '')} {record.get('SURNAME', '')}".strip(),
                    "designation": record.get("DESIGNATION", ""),
                    "department": record.get("DEPARTMENT", ""),
                    "user_grade": record.get("GRADE", ""),
                    "regions": regions,
                    "grades": grades,
                    "departments": departments,
                    "full_access": full_access
                }

        # Employee code not found in access records
        return None

    def create_rbac_filter(self, permissions: Dict[str, Any],
                          collection_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create MongoDB $match filter based on permissions and collection schema.

        Args:
            permissions: User permissions from get_user_permissions()
            collection_schema: Schema of the collection (field names and types)

        Returns:
            MongoDB $match filter dictionary
        """
        if permissions.get("full_access"):
            # Full access - no restrictions
            return {}

        rbac_filter = {}

        # Detect which field names exist in this collection's schema
        schema_fields = set(collection_schema.get("fields", []))

        # Add region filter if regions are restricted
        if permissions["regions"]:
            region_field = self._find_field_in_schema(schema_fields, self.field_mappings["region"])
            if region_field:
                rbac_filter[region_field] = {"$in": permissions["regions"]}

        # Add grade filter if grades are restricted
        if permissions["grades"]:
            grade_field = self._find_field_in_schema(schema_fields, self.field_mappings["grade"])
            if grade_field:
                rbac_filter[grade_field] = {"$in": permissions["grades"]}

        # Add department filter if departments are restricted
        if permissions["departments"]:  # Non-empty means restricted to these departments
            dept_field = self._find_field_in_schema(schema_fields, self.field_mappings["department"])
            if dept_field:
                rbac_filter[dept_field] = {"$in": permissions["departments"]}

        return rbac_filter

    def _find_field_in_schema(self, schema_fields: set, possible_names: List[str]) -> Optional[str]:
        """Find which field name variant exists in the schema"""
        for name in possible_names:
            if name in schema_fields:
                return name
        return None

    def inject_rbac_into_pipeline(self, pipeline: List[Dict],
                                  rbac_filter: Dict[str, Any]) -> List[Dict]:
        """
        Inject RBAC filter at the beginning of aggregation pipeline.

        Args:
            pipeline: Original MongoDB aggregation pipeline
            rbac_filter: RBAC filter from create_rbac_filter()

        Returns:
            Modified pipeline with RBAC filter injected
        """
        if not rbac_filter:
            # No restrictions - return original pipeline
            return pipeline

        # Check if pipeline already has a $match stage at the beginning
        if pipeline and "$match" in pipeline[0]:
            # Merge with existing $match using $and
            existing_match = pipeline[0]["$match"]
            merged_match = {
                "$and": [
                    rbac_filter,
                    existing_match
                ]
            }
            return [{"$match": merged_match}] + pipeline[1:]
        else:
            # Inject new $match stage at the beginning
            return [{"$match": rbac_filter}] + pipeline

    def get_user_context_string(self, permissions: Dict[str, Any]) -> str:
        """
        Generate a user context string for display or logging.

        Args:
            permissions: User permissions from get_user_permissions()

        Returns:
            Human-readable string describing user's access level
        """
        if permissions.get("full_access"):
            return f"{permissions['name']} ({permissions['designation']}) - Full Access to All Data"

        context_parts = [
            f"{permissions['name']} ({permissions['designation']})",
            f"Regions: {', '.join(permissions['regions']) if permissions['regions'] else 'All'}",
            f"Grades: {', '.join(permissions['grades']) if permissions['grades'] else 'All'}",
        ]

        if permissions['departments']:
            context_parts.append(f"Departments: {', '.join(permissions['departments'])}")
        else:
            context_parts.append("Departments: All")

        return " | ".join(context_parts)

    def validate_emp_code(self, emp_code: int) -> bool:
        """
        Check if employee code exists in access records.

        Args:
            emp_code: Employee code to validate

        Returns:
            True if employee has access, False otherwise
        """
        return any(record["Emp Code"] == emp_code for record in self.access_records)

    def get_all_authorized_users(self) -> List[Dict[str, Any]]:
        """
        Get list of all authorized users.

        Returns:
            List of dictionaries with emp_code, name, and designation
        """
        return [
            {
                "emp_code": record["Emp Code"],
                "name": f"{record.get('NAME', '')} {record.get('SURNAME', '')}".strip(),
                "designation": record.get("DESIGNATION", "")
            }
            for record in self.access_records
        ]
