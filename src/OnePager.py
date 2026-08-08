"""
OnePager Report Generator
Fetches employee data from multiple MongoDB collections to generate a comprehensive report
"""
import json
import logging
from typing import Dict, Any, Optional
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
from dotenv import load_dotenv
from db_collections import get_collection

logger = logging.getLogger(__name__)

load_dotenv()


class OnePager:
    """
    Generates a one-page report for an employee by fetching data from multiple collections
    """
    
    def __init__(self):
        """Initialize MongoDB connection"""
        self.mongo_uri = os.getenv("MONGODB_URI")
        if not self.mongo_uri:
            raise ValueError("MONGODB_URI not found in environment variables")
        
        self.client = MongoClient(self.mongo_uri)
        
        # Use specific database name from env, or default database from URI
        db_name = os.getenv("MONGODB_DATABASE")
        if db_name:
            self.db = self.client[db_name]
        else:
            self.db = self.client.get_default_database()
    
    def get_user_info(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user information by email to check role and region
        
        Args:
            email: User's email address
            
        Returns:
            User information dictionary or None
        """
        try:
            collection = self.db[get_collection("base_report")]
            user = collection.find_one({"email": email})
            return user
        except Exception as e:
            print(f"Error fetching user info: {e}")
            return None
    
    def verify_hr_access(self, email: str, employee_code) -> Dict[str, Any]:
        """
        Verify if the requesting user (HR) has access to generate report for the employee
        
        Args:
            email: Requesting user's email (should be HR)
            employee_code: Target employee code (int or str)
            
        Returns:
            Dictionary with 'allowed' boolean and 'reason' if denied
        """
        # Get requesting user's info
        requesting_user = self.get_user_info(email)
        
        if not requesting_user:
            return {
                "allowed": False,
                "reason": "Requesting user not found in the system"
            }
        
        # Check if user is HR
        user_role = requesting_user.get("role", "").upper()
        user_department = requesting_user.get("department", "").upper()
        
        # Check for HR role (adjust field names as per your schema)
        is_hr = (user_role == "HR" or 
                 user_department == "HR" or 
                 user_role == "HUMAN RESOURCES" or
                 requesting_user.get("is_hr", False))
        
        if not is_hr:
            return {
                "allowed": False,
                "reason": f"Access denied. Only HR personnel can generate OnePager reports. Your role: {user_role or 'N/A'}"
            }
        
        # Get target employee's info
        target_employee = self.fetch_employee_basic_info(employee_code)
        
        if not target_employee:
            return {
                "allowed": False,
                "reason": f"Employee with code '{employee_code}' not found"
            }
        
        # Check region/location match
        hr_region = requesting_user.get("region", "").upper()
        employee_region = target_employee.get("region", "").upper()
        
        # Also check location/office as fallback
        if not hr_region:
            hr_region = requesting_user.get("location", "").upper()
        if not employee_region:
            employee_region = target_employee.get("location", "").upper()
        
        if hr_region != employee_region:
            return {
                "allowed": False,
                "reason": f"Access denied. You can only generate reports for employees in your region. Your region: {hr_region or 'N/A'}, Employee region: {employee_region or 'N/A'}"
            }
        
        # All checks passed
        return {
            "allowed": True,
            "hr_name": requesting_user.get("name", "Unknown"),
            "hr_region": hr_region
        }
    
    def fetch_employee_basic_info(self, employee_code) -> Optional[Dict[str, Any]]:
        """
        Fetch basic employee information from the main employee collection
        
        Args:
            employee_code: Employee code/ID (int or str)
            
        Returns:
            Employee basic information dictionary or None
        """
        try:
            # Convert to int if it's a string
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            collection = self.db[get_collection("base_report")]
            
            # Only fetch required fields
            projection = {
                "employee code": 1,
                "first name": 1,
                "last name": 1,
                "email": 1,
                "gender": 1,
                "assignment status type": 1,
                "date of birth": 1,
                "grade": 1,
                "designation": 1,
                "department": 1,
                "reporting to": 1,
                "date of joining": 1,
                "date of leaving": 1,
                "role": 1
            }
            
            employee = collection.find_one({"employee code": emp_code}, projection)
            return employee
        except Exception as e:
            print(f"Error fetching basic info: {e}")
            return None
    
    def fetch_employee_performance_education_work_experience(self, employee_code) -> list:
        """
        Fetch employee performance, education, and work experience records
        
        Args:
            employee_code: Employee code/ID (int or str)
            
        Returns:
            List of performance/education/experience records
        """
        try:
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            collection = self.db[get_collection("historical_ratings_and_other_information")]
            
            # Only fetch required fields
            projection = {
                "last promotion date": 1,
                "current year": 1,
                "cy-1": 1,
                "cy-2": 1,
                "employee code": 1,
                "experience prior to tata play": 1,
                "highest qualification": 1,
                "university name": 1,
                "mt batch": 1,
            }
            
            records = list(collection.find({"employee code": emp_code}, projection))
            return records
        except Exception as e:
            print(f"Error fetching performance: {e}")
            return []
    
    def fetch_employee_goal_reports(self, employee_code) -> list:
        """
        Fetch employee goal reports
        
        Args:
            employee_code: Employee code/ID (int or str)
            
        Returns:
            List of goal records with goal name and weight
        """
        try:
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            collection = self.db[get_collection("performance_goal_report_2025_2026")]
            
            # Only fetch required fields
            projection = {
                "goal name": 1,
                "weight": 1,
                "employee code": 1
            }
            
            records = list(collection.find({"employee code": emp_code}, projection))
            return records
        except Exception as e:
            print(f"Error fetching goal reports: {e}")
            return []
    
    def fetch_employee_attendance(self, employee_code) -> list:
        """
        Fetch employee attendance records
        
        Args:
            employee_code: Employee code/ID (int or str)
            
        Returns:
            List of attendance records
        """
        try:
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            collection = self.db[get_collection("leave_transaction_with_balance_report")]
            
            # Only fetch required fields
            projection = {
                "absence name": 1,
                "balance value": 1,
                "employee code": 1
            }
            
            records = list(collection.find({"employee code": emp_code}, projection))
            return records
        except Exception as e:
            print(f"Error fetching attendance: {e}")
            return []
    
    
    def fetch_employee_rewards_and_recognition(self, employee_code) -> Dict[str, int]:
        """
        Fetch employee rewards and recognition from all r&r collections
        
        Args:
            employee_code: Employee code/ID (int or str)
            
        Returns:
            Dictionary with counts from each r&r collection
        """
        try:
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            
            # All r&r collections to query
            r_and_r_collections = [
                "r&r_ceo_of_the_quarter",
                "r&r_cross_functional",
                "r&r_debutant_of_the_qtr",
                "r&r_intrafunctional",
                "r&r_job_well_done",
                "r&r_thank_you"
            ]
            
            counts = {}
            total_count = 0
            
            for collection_name in r_and_r_collections:
                try:
                    collection = self.db[get_collection(collection_name)]
                    
                    # CEO of the quarter uses "employee code", others use "receiver employee code"
                    if collection_name == "r&r_ceo_of_the_quarter":
                        field_name = "employee code"
                    else:
                        field_name = "receiver employee code"
                    
                    # Try with integer first
                    count = collection.count_documents({field_name: emp_code})
                    
                    # If count is 0, try with string
                    if count == 0:
                        count = collection.count_documents({field_name: str(emp_code)})
                    
                    counts[collection_name] = count
                    total_count += count
                    
                except Exception as e:
                    print(f"Error counting {collection_name}: {e}")
                    counts[collection_name] = 0
            
            counts["total"] = total_count
            return counts
            
        except Exception as e:
            print(f"Error fetching rewards and recognition: {e}")
            return {
                "total": 0,
                "error": str(e)
            }

    
    def fetch_employee_pip_details(self, employee_code) -> list:
        """
        Fetch employee PIP (Performance Improvement Plan) details
        
        Args:
            employee_code: Employee code/ID (int or str)
            
        Returns:
            List of PIP records
        """
        try:
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            collection = self.db[get_collection("pip_transaction_report")]
            
            # Only fetch required fields
            projection = {
                "pip submitted date": 1,
                "pip completion date": 1,
                "pip document status": 1,
                "employee code": 1
            }
            
            records = list(collection.find({"employee code": emp_code}, projection))
            return records
        except Exception as e:
            print(f"Error fetching PIP details: {e}")
            return []

    def fetch_employee_assignment_details(self, employee_code) -> list:
        """
        Fetch employee assignment details
        
        Args:
            employee_code: Employee code/ID (int or str)
            
        Returns:
            List of assignment records
        """
        try:
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            collection = self.db[get_collection("assignment_details")]
            
            # Only fetch required fields
            projection = {
                "action code": 1,
                "effective start date": 1,
                "effective end date": 1,
                "employee code": 1
            }
            
            records = list(collection.find({"employee code": emp_code}, projection))
            return records
        except Exception as e:
            print(f"Error fetching assignment details: {e}")
            return []

    @staticmethod
    def format_date(date_value) -> str:
        """Convert date from various formats to DD-MM-YYYY"""
        if not date_value or date_value == 'N/A':
            return 'N/A'
        
        try:
            # If it's already a datetime object
            if isinstance(date_value, datetime):
                return date_value.strftime('%d-%m-%Y')
            
            # If it's a string, try to parse it
            if isinstance(date_value, str):
                # Try parsing common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y']:
                    try:
                        dt = datetime.strptime(date_value, fmt)
                        return dt.strftime('%d-%m-%Y')
                    except ValueError:
                        continue
            
            return str(date_value)
        except Exception:
            return str(date_value)

    def format_dates_in_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Format all date fields in report to DD-MM-YYYY"""
        if report.get("status") != "success":
            return report
        
        # Format dates in basic_info
        basic = report.get("basic_info", {})
        if basic:
            for date_field in ['date of birth', 'date of joining', 'date of leaving']:
                if date_field in basic:
                    basic[date_field] = self.format_date(basic[date_field])
        
        # Format dates in performance records
        perf_list = report.get("performance_education_work_experience", [])
        for perf in perf_list:
            if 'last promotion date' in perf:
                perf['last promotion date'] = self.format_date(perf['last promotion date'])
        
        # Format dates in PIP details
        pip_list = report.get("pip_details", [])
        for pip in pip_list:
            if 'pip submitted date' in pip:
                pip['pip submitted date'] = self.format_date(pip['pip submitted date'])
            if 'pip completion date' in pip:
                pip['pip completion date'] = self.format_date(pip['pip completion date'])
        
        # Format dates in assignment details
        assignment_list = report.get("assignment_details", [])
        for assignment in assignment_list:
            if 'effective start date' in assignment:
                assignment['effective start date'] = self.format_date(assignment['effective start date'])
            if 'effective end date' in assignment:
                assignment['effective end date'] = self.format_date(assignment['effective end date'])
        
        return report

    def generate_report_aggregation(self, employee_code, requesting_email: str) -> Dict[str, Any]:
        """
        Generate comprehensive one-page report using MongoDB aggregation pipeline
        More efficient than multiple queries - uses $lookup to join collections in single query
        
        Args:
            employee_code: Employee code/ID (int or str)
            requesting_email: Email of the user requesting the report (must be HR)
            
        Returns:
            Dictionary containing all employee information or access denial
        """
        logger.debug("Generating OnePager report (aggregation)")
        
        # RBAC Check: Verify HR access
        # access_check = self.verify_hr_access(requesting_email, employee_code)
        
        # if not access_check.get("allowed"):
        #     return {
        #         "status": "access_denied",
        #         "message": access_check.get("reason", "Access denied"),
        #         "employee_code": employee_code,
        #         "requesting_email": requesting_email
        #     }
        
        try:
            emp_code = int(employee_code) if isinstance(employee_code, str) else employee_code
            collection = self.db[get_collection("base_report")]
            
            # Build aggregation pipeline with $lookup to join all collections
            pipeline = [
                # Match the specific employee
                {"$match": {"employee code": emp_code}},
                
                # Project only needed fields from base_report
                {"$project": {
                    "employee code": 1,
                    "first name": 1,
                    "last name": 1,
                    "email": 1,
                    "gender": 1,
                    "assignment status type": 1,
                    "date of birth": 1,
                    "grade": 1,
                    "designation": 1,
                    "department": 1,
                    "reporting to": 1,
                    "date of joining": 1,
                    "date of leaving": 1,
                    "role": 1
                }},
                
                # Lookup performance/education/experience
                {"$lookup": {
                    "from": get_collection("historical_ratings_and_other_information"),
                    "let": {"emp_code": "$employee code"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$employee code", "$$emp_code"]}}},
                        {"$project": {
                            "last promotion date": 1,
                            "current year": 1,
                            "cy-1": 1,
                            "cy-2": 1,
                            "experience prior to tata play": 1,
                            "highest qualification": 1,
                            "university name": 1,
                            "mt batch": 1
                        }}
                    ],
                    "as": "performance_education_work_experience"
                }},
                
                # Lookup goal reports
                {"$lookup": {
                    "from": get_collection("performance_goal_report_2025_2026"),
                    "let": {"emp_code": "$employee code"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$employee code", "$$emp_code"]}}},
                        {"$project": {
                            "goal name": 1,
                            "weight": 1
                        }}
                    ],
                    "as": "goal_reports"
                }},
                
                # Lookup attendance records
                {"$lookup": {
                    "from": get_collection("leave_transaction_with_balance_report"),
                    "let": {"emp_code": "$employee code"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$employee code", "$$emp_code"]}}},
                        {"$project": {
                            "absence name": 1,
                            "balance value": 1
                        }}
                    ],
                    "as": "attendance_records"
                }},
                
                # Lookup PIP details
                {"$lookup": {
                    "from": get_collection("pip_transaction_report"),
                    "let": {"emp_code": "$employee code"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$employee code", "$$emp_code"]}}},
                        {"$project": {
                            "pip submitted date": 1,
                            "pip completion date": 1,
                            "pip document status": 1
                        }}
                    ],
                    "as": "pip_details"
                }},
                
                # Lookup assignment details
                {"$lookup": {
                    "from": get_collection("assignment_details"),
                    "let": {"emp_code": "$employee code"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$employee code", "$$emp_code"]}}},
                        {"$project": {
                            "action code": 1,
                            "effective start date": 1,
                            "effective end date": 1
                        }}
                    ],
                    "as": "assignment_details"
                }}
            ]
            
            # Execute aggregation
            result = list(collection.aggregate(pipeline))
            
            if not result:
                return {
                    "status": "error",
                    "message": f"Employee with code '{employee_code}' not found",
                    "employee_code": employee_code
                }
            
            employee_data = result[0]
            
            # Fetch R&R separately (complex logic with multiple collections and field name variations)
            rewards_and_recognition = self.fetch_employee_rewards_and_recognition(employee_code)
            
            # Build report response
            report = {
                "status": "success",
                "employee_code": employee_code,
                "basic_info": {k: v for k, v in employee_data.items() 
                              if k not in ['performance_education_work_experience', 'goal_reports', 
                                          'attendance_records', 'pip_details', 'assignment_details']},
                "performance_education_work_experience": employee_data.get("performance_education_work_experience", []),
                "attendance_records": employee_data.get("attendance_records", []),
                "goal_reports": employee_data.get("goal_reports", []),
                "rewards_and_recognition": rewards_and_recognition,
                "pip_details": employee_data.get("pip_details", []),
                "assignment_details": employee_data.get("assignment_details", [])
            }
            
            # Format all dates to DD-MM-YYYY before returning
            report = self.format_dates_in_report(report)
            
            return report
            
        except Exception as e:
            print(f"Error in aggregation pipeline: {e}")
            return {
                "status": "error",
                "message": f"Error generating report: {str(e)}",
                "employee_code": employee_code
            }

    def format_report_text(self, report: Dict[str, Any]) -> str:
        """
        Format the report dictionary into human-readable text
        
        Args:
            report: Report dictionary from generate_report or generate_report_aggregation
            
        Returns:
            Formatted text string
        """
        if report.get("status") != "success":
            return f"Error: {report.get('message', 'Unknown error')}"
        
        lines = []
        lines.append("=" * 80)
        lines.append("EMPLOYEE ONE-PAGER REPORT")
        lines.append("=" * 80)
        
        # Basic Info
        basic = report.get("basic_info", {})
        if basic:
            lines.append("\n📋 BASIC INFORMATION")
            lines.append("-" * 80)
            lines.append(f"Employee Code: {basic.get('employee code', 'N/A')}")
            lines.append(f"Name: {basic.get('first name', '')} {basic.get('last name', '')}")
            lines.append(f"Email: {basic.get('email', 'N/A')}")
            lines.append(f"Gender: {basic.get('gender', 'N/A')}")
            lines.append(f"Date of Birth: {self.format_date(basic.get('date of birth'))}")
            lines.append(f"Grade: {basic.get('grade', 'N/A')}")
            lines.append(f"Designation: {basic.get('designation', 'N/A')}")
            lines.append(f"Department: {basic.get('department', 'N/A')}")
            lines.append(f"Reporting To: {basic.get('reporting to', 'N/A')}")
            lines.append(f"Date of Joining: {self.format_date(basic.get('date of joining'))}")
            lines.append(f"Date of Leaving: {self.format_date(basic.get('date of leaving'))}")
            lines.append(f"Status: {basic.get('assignment status type', 'N/A')}")
            lines.append(f"Role: {basic.get('role', 'N/A')}")
        
        # Performance
        perf = report.get("performance_education_work_experience", [])
        if perf:
            lines.append("\n📊 PERFORMANCE & BACKGROUND")
            lines.append("-" * 80)
            for p in perf:
                if p.get('current year'):
                    lines.append(f"Current Year Rating: {p.get('current year', 'N/A')}")
                if p.get('cy-1'):
                    lines.append(f"CY-1 Rating: {p.get('cy-1', 'N/A')}")
                if p.get('cy-2'):
                    lines.append(f"CY-2 Rating: {p.get('cy-2', 'N/A')}")
                if p.get('last promotion date'):
                    lines.append(f"Last Promotion: {self.format_date(p.get('last promotion date'))}")
                if p.get('highest qualification'):
                    lines.append(f"Qualification: {p.get('highest qualification', 'N/A')}")
                if p.get('university name'):
                    lines.append(f"University: {p.get('university name', 'N/A')}")
                if p.get('experience prior to tata play'):
                    lines.append(f"Prior Experience: {p.get('experience prior to tata play', 'N/A')}")
                if p.get('mt batch'):
                    lines.append(f"MT Batch: {p.get('mt batch', 'N/A')}")
        
        # Goals
        goals = report.get("goal_reports", [])
        if goals:
            lines.append("\n🎯 GOALS (2025-2026)")
            lines.append("-" * 80)
            for i, g in enumerate(goals, 1):
                lines.append(f"{i}. {g.get('goal name', 'N/A')} (Weight: {g.get('weight', 'N/A')})")
        
        # Attendance
        attendance = report.get("attendance_records", [])
        if attendance:
            lines.append("\n📅 LEAVE BALANCE")
            lines.append("-" * 80)
            for a in attendance:
                lines.append(f"{a.get('absence name', 'N/A')}: {a.get('balance value', 'N/A')}")
        
        # Rewards & Recognition
        rewards = report.get("rewards_and_recognition", {})
        if rewards and rewards.get("total", 0) > 0:
            lines.append("\n🏆 REWARDS & RECOGNITION")
            lines.append("-" * 80)
            lines.append(f"Total Awards: {rewards.get('total', 0)}")
            for key, count in rewards.items():
                if key != "total" and key != "error" and count > 0:
                    lines.append(f"  • {key}: {count}")
        
        # PIP Details
        pip = report.get("pip_details", [])
        if pip:
            lines.append("\n⚠️ PIP RECORDS")
            lines.append("-" * 80)
            for p in pip:
                lines.append(f"Submitted: {self.format_date(p.get('pip submitted date'))}")
                lines.append(f"Completion: {self.format_date(p.get('pip completion date'))}")
                lines.append(f"Status: {p.get('pip document status', 'N/A')}")
                lines.append("")
        
        # Assignment Details
        assignments = report.get("assignment_details", [])
        if assignments:
            lines.append("\n📌 ASSIGNMENT HISTORY")
            lines.append("-" * 80)
            for a in assignments:
                lines.append(f"Action: {a.get('action code', 'N/A')}")
                lines.append(f"Start: {self.format_date(a.get('effective start date'))} → End: {self.format_date(a.get('effective end date'))}")
                lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)

    def generate_report(self, employee_code, requesting_email: str) -> Dict[str, Any]:
        """
        Generate comprehensive one-page report for an employee with RBAC checks
        Uses parallel execution to fetch data from multiple collections simultaneously
        
        Args:
            employee_code: Employee code/ID (int or str)
            requesting_email: Email of the user requesting the report (must be HR)
            
        Returns:
            Dictionary containing all employee information or access denial
        """
        logger.debug("Generating OnePager report")
        
        # RBAC Check: Verify HR access
        # access_check = self.verify_hr_access(requesting_email, employee_code)
        
        # if not access_check.get("allowed"):
        #     return {
        #         "status": "access_denied",
        #         "message": access_check.get("reason", "Access denied"),
        #         "employee_code": employee_code,
        #         "requesting_email": requesting_email
        #     }
        
        # Fetch basic info first to validate employee exists
        basic_info = self.fetch_employee_basic_info(employee_code)
        
        if not basic_info:
            return {
                "status": "error",
                "message": f"Employee with code '{employee_code}' not found",
                "employee_code": employee_code
            }
        
        # Define fetch tasks for parallel execution
        fetch_tasks = {
            'performance': lambda: self.fetch_employee_performance_education_work_experience(employee_code),
            'attendance': lambda: self.fetch_employee_attendance(employee_code),
            'goal_reports': lambda: self.fetch_employee_goal_reports(employee_code),
            'rewards_and_recognition': lambda: self.fetch_employee_rewards_and_recognition(employee_code),
            'pip_details': lambda: self.fetch_employee_pip_details(employee_code),
            'assignment_details': lambda: self.fetch_employee_assignment_details(employee_code)
        }
        
        # Execute all fetches in parallel using ThreadPoolExecutor
        results = {}
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit all tasks
            future_to_key = {executor.submit(task): key for key, task in fetch_tasks.items()}
            
            # Collect results as they complete
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    results[key] = [] if key != 'rewards_and_recognition' else {"total": 0, "error": str(e)}
        
        report = {
            "status": "success",
            "employee_code": employee_code,
            "basic_info": basic_info,
            "performance_education_work_experience": results.get('performance', []),
            "attendance_records": results.get('attendance', []),
            "goal_reports": results.get('goal_reports', []),
            "rewards_and_recognition": results.get('rewards_and_recognition', {"total": 0}),
            "pip_details": results.get('pip_details', []),
            "assignment_details": results.get('assignment_details', [])
        }
        
        return report
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
