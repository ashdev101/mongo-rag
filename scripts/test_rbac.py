#!/usr/bin/env python3
"""
Test script for RBAC functionality

Demonstrates how different users see different data based on their access levels.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rbac_manager import RBACManager


def main():
    print("=" * 80)
    print("RBAC Manager Test")
    print("=" * 80)
    print()

    # Initialize RBAC Manager
    try:
        rbac = RBACManager()
        print("✅ RBAC Manager initialized successfully")
        print(f"   Access records loaded: {len(rbac.access_records)}")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Show all authorized users
    print("=" * 80)
    print("ALL AUTHORIZED USERS")
    print("=" * 80)
    users = rbac.get_all_authorized_users()
    for user in users:
        print(f"  [{user['emp_code']:4d}] {user['name']:30s} - {user['designation']}")
    print()

    # Test different access levels
    test_users = [
        (3996, "CHRO - Full Access"),
        (7190, "SVP HR - Full Access"),
        (6671, "Manager HR - North Region Only"),
        (871, "VP HR - Corporate, West, Central Only"),
    ]

    for emp_code, description in test_users:
        print("=" * 80)
        print(f"TEST: {description}")
        print("=" * 80)

        permissions = rbac.get_user_permissions(emp_code)

        if not permissions:
            print(f"❌ Employee code {emp_code} not found")
            print()
            continue

        print(f"Employee: {permissions['name']}")
        print(f"Designation: {permissions['designation']}")
        print(f"Department: {permissions['department']}")
        print(f"Grade: {permissions['user_grade']}")
        print()

        print(f"Full Access: {'✅ YES' if permissions['full_access'] else '❌ NO'}")
        print(f"Accessible Regions: {', '.join(permissions['regions']) if permissions['regions'] else 'All'}")
        print(f"Accessible Grades: {', '.join(permissions['grades']) if permissions['grades'] else 'All'}")

        if permissions['departments']:
            print(f"Accessible Departments: {', '.join(permissions['departments'])}")
        else:
            print("Accessible Departments: All")

        print()
        print(f"Access Summary: {rbac.get_user_context_string(permissions)}")
        print()

        # Simulate RBAC filter for base_report collection
        collection_schema = {
            "fields": ["_id", "employee code", "primary email", "GRADE", "Region", "DEPARTMENT", "Assignment Status Type"]
        }

        rbac_filter = rbac.create_rbac_filter(permissions, collection_schema)

        if rbac_filter:
            print("🔒 RBAC Filter Applied:")
            print(f"   {rbac_filter}")
        else:
            print("🔓 No RBAC filter (full access)")

        print()

    # Test invalid employee code
    print("=" * 80)
    print("TEST: Invalid Employee Code")
    print("=" * 80)

    invalid_permissions = rbac.get_user_permissions(99999)
    if invalid_permissions:
        print("❌ Should not have found permissions!")
    else:
        print("✅ Correctly returned None for invalid employee code")

    print()
    print("=" * 80)
    print("✅ RBAC Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
