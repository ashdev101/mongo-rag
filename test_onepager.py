"""
Test script for OnePager class
Run this to test the OnePager functionality locally
"""
from src.OnePager import OnePager
import json


def test_onepager():
    """Test the OnePager report generation"""
    
    print("=" * 60)
    print("Testing OnePager Report Generator")
    print("=" * 60)
    
    try:
        # Initialize OnePager
        print("\n1. Initializing OnePager...")
        onepager = OnePager()
        print("✓ OnePager initialized successfully")
        
        # Test employee code and HR email
        # UPDATE THESE WITH ACTUAL VALUES FROM YOUR DATABASE
        employee_code = "3159"  # Replace with actual employee code
        hr_email = "snehas@tatasky.com"  # Replace with actual HR email
        
        print(f"\n2. Testing with:")
        print(f"   Employee Code: {employee_code}")
        print(f"   HR Email: {hr_email}")
        
        # Generate report
        print("\n3. Generating report...")
        report = onepager.generate_report(employee_code, hr_email)
        
        # Display results
        print("\n4. Report Results:")
        print("=" * 60)
        print(json.dumps(report, indent=2, default=str))
        print("=" * 60)
        
        # Close connection
        onepager.close()
        print("\n✓ Test completed successfully")
        
    except ValueError as e:
        print(f"\n✗ Configuration Error: {e}")
        print("\nMake sure you have set up your .env file with:")
        print("  - MONGODB_URI=your_mongodb_connection_string")
        print("  - MONGODB_DATABASE=your_database_name (optional)")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_user_lookup():
    """Test user lookup by email"""
    
    print("\n" + "=" * 60)
    print("Testing User Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMAIL FROM YOUR DATABASE
        test_email = "snehas@tatasky.com"
        
        print(f"\nLooking up user: {test_email}")
        user = onepager.get_user_info(test_email)
        
        if user:
            print("\n✓ User found:")
            print(json.dumps(user, indent=2, default=str))
        else:
            print("\n✗ User not found")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_employee_lookup():
    """Test employee lookup by code"""
    
    print("\n" + "=" * 60)
    print("Testing Employee Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMPLOYEE CODE FROM YOUR DATABASE
        test_code = "1007"
        
        print(f"\nLooking up employee: {test_code}")
        employee = onepager.fetch_employee_basic_info(test_code)
        
        if employee:
            print("\n✓ Employee found:")
            print(json.dumps(employee, indent=2, default=str))
        else:
            print("\n✗ Employee not found")
            print("\nTip: Check the field name in your base_report collection.")
            print("Currently searching for: 'employee code'")
            print("You may need to update the field name in OnePager.py")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_performance_lookup():
    """Test employee performance records lookup"""
    
    print("\n" + "=" * 60)
    print("Testing Performance Records Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMPLOYEE CODE FROM YOUR DATABASE
        test_code = "1252"
        
        print(f"\nLooking up performance records for employee: {test_code}")
        performance = onepager.fetch_employee_performance_education_work_experience(test_code)
        
        if performance:
            print(f"\n✓ Found {len(performance)} performance record(s):")
            print(json.dumps(performance, indent=2, default=str))
        else:
            print("\n✗ No performance records found")
            print("\nTip: Check if the employee has records in historical_ratings_and_other_information collection")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_goal_reports_lookup():
    """Test employee goal reports lookup"""
    
    print("\n" + "=" * 60)
    print("Testing Goal Reports Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMPLOYEE CODE FROM YOUR DATABASE
        test_code = "1034"
        
        print(f"\nLooking up goal reports for employee: {test_code}")
        goals = onepager.fetch_employee_goal_reports(test_code)
        
        if goals:
            print(f"\n✓ Found {len(goals)} goal report(s):")
            print(json.dumps(goals, indent=2, default=str))
        else:
            print("\n✗ No goal reports found")
            print("\nTip: Check if the employee has records in performance_goal_report_2025_2026 collection")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_attendance_lookup():
    """Test employee attendance records lookup"""
    
    print("\n" + "=" * 60)
    print("Testing Attendance Records Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMPLOYEE CODE FROM YOUR DATABASE
        test_code = "2461"
        
        print(f"\nLooking up attendance records for employee: {test_code}")
        attendance = onepager.fetch_employee_attendance(test_code)
        
        if attendance:
            print(f"\n✓ Found {len(attendance)} attendance record(s):")
            print(json.dumps(attendance, indent=2, default=str))
        else:
            print("\n✗ No attendance records found")
            print("\nTip: Check if the employee has records in leave_transaction_with_balance_report collection")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_rewards_and_recognition_lookup():
    """Test employee rewards and recognition records lookup"""
    
    print("\n" + "=" * 60)
    print("Testing Rewards & Recognition Records Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMPLOYEE CODE FROM YOUR DATABASE
        test_code = "6356"
        
        print(f"\nLooking up rewards and recognition records for employee: {test_code}")
        rewards = onepager.fetch_employee_rewards_and_recognition(test_code)
        
        if rewards:
            print(f"\n✓ Found {len(rewards)} reward(s) and recognition record(s):")
            print(json.dumps(rewards, indent=2, default=str))
        else:
            print("\n✗ No rewards and recognition records found")
            print("\nTip: Check if the employee has records in rewards_and_recognition collection")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_pip_details_lookup():
    """Test employee PIP details lookup"""
    
    print("\n" + "=" * 60)
    print("Testing PIP Details Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMPLOYEE CODE FROM YOUR DATABASE
        test_code = "6689"
        
        print(f"\nLooking up PIP details for employee: {test_code}")
        pip_details = onepager.fetch_employee_pip_details(test_code)
        
        if pip_details:
            print(f"\n✓ Found {len(pip_details)} PIP record(s):")
            print(json.dumps(pip_details, indent=2, default=str))
        else:
            print("\n✗ No PIP records found")
            print("\nTip: Check if the employee has records in pip_transaction_report collection")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_assignment_details_lookup():
    """Test employee assignment details lookup"""
    
    print("\n" + "=" * 60)
    print("Testing Assignment Details Lookup")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THIS WITH ACTUAL EMPLOYEE CODE FROM YOUR DATABASE
        test_code = "1007"
        
        print(f"\nLooking up assignment details for employee: {test_code}")
        assignment_details = onepager.fetch_employee_assignment_details(test_code)
        
        if assignment_details:
            print(f"\n✓ Found {len(assignment_details)} assignment record(s):")
            print(json.dumps(assignment_details, indent=2, default=str))
        else:
            print("\n✗ No assignment records found")
            print("\nTip: Check if the employee has records in assignment_details collection")
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def test_aggregation_report():
    """Test the OnePager report generation using aggregation pipeline"""
    
    print("\n" + "=" * 60)
    print("Testing OnePager Report (Aggregation Method)")
    print("=" * 60)
    
    try:
        onepager = OnePager()
        
        # UPDATE THESE WITH ACTUAL VALUES FROM YOUR DATABASE
        employee_code = "4013"
        hr_email = "snehas@tatasky.com"
        
        print(f"\nGenerating aggregation report for employee: {employee_code}")
        print(f"Requested by: {hr_email}")
        
        report = onepager.generate_report_aggregation(employee_code, hr_email)
        
        print(f"\n✓ Report generated successfully:")
        print(json.dumps(report, indent=2, default=str))
        
        onepager.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    print("\nOnePager Test Suite")
    print("=" * 60)
    print("\nBefore running, update the test values in this file:")
    print("  - employee_code (line 20)")
    print("  - hr_email (line 21)")
    print("  - test_email (line 59)")
    print("  - test_code (line 82)")
    print("\n" + "=" * 60)
    
    choice = input("\nWhich test do you want to run?\n1. Full OnePager Report\n2. User Lookup\n3. Employee Lookup\n4. Performance Lookup\n5. Goal Reports Lookup\n6. Attendance Lookup\n7. Rewards & Recognition Lookup\n8. PIP Details Lookup\n9. Assignment Details Lookup\n10. Full OnePager Report (Aggregation)\n11. All tests\n\nEnter choice (1-11): ")
    
    if choice == "1":
        test_onepager()
    elif choice == "2":
        test_user_lookup()
    elif choice == "3":
        test_employee_lookup()
    elif choice == "4":
        test_performance_lookup()
    elif choice == "5":
        test_goal_reports_lookup()
    elif choice == "6":
        test_attendance_lookup()
    elif choice == "7":
        test_rewards_and_recognition_lookup()
    elif choice == "8":
        test_pip_details_lookup()
    elif choice == "9":
        test_assignment_details_lookup()
    elif choice == "10":
        test_aggregation_report()
    elif choice == "11":
        test_user_lookup()
        test_employee_lookup()
        test_performance_lookup()
        test_goal_reports_lookup()
        test_attendance_lookup()
        test_rewards_and_recognition_lookup()
        test_pip_details_lookup()
        test_assignment_details_lookup()
        test_onepager()
        test_aggregation_report()
    else:
        print("Invalid choice. Running all tests...")
        test_user_lookup()
        test_employee_lookup()
        test_performance_lookup()
        test_goal_reports_lookup()
        test_attendance_lookup()
        test_rewards_and_recognition_lookup()
        test_pip_details_lookup()
        test_assignment_details_lookup()
        test_onepager()
        test_aggregation_report()
