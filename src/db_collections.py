"""
Database Collection Mapper
Centralized mapping of MongoDB collection names
"""

# Collection name mappings - Update these based on your actual collections
COLLECTIONS = {
    "base_report": "base_report",
    "assignment_details": "assignment_report",
    "goal_detail_report": "goal_detail_report",
    "goal_setting_status": "goal_setting_status",
    "historical_ratings_and_other_information": "historical_ratings_and_other_information",
    "historical_ratings_and_other_information_old": "historical_ratings_and_other_information_old",
    "leave_transaction_with_balance_report": "leave_transaction_with_balance_report",
    "offboarding_checklist": "offboarding_checklist",
    "performance_360_degree_feedback_participants_status_all": "performance_360_degree_feedback_participants_status_all",
    "performance_goal_report_2025_2026": "performance_goal_report_2025_2026",
    "performance_rating_report_year_2025_2026": "performormance_rating_report_year_2025_2026",
    "pip_transaction_report": "pip_transaction_report",
    "pms_task_status_report_all": "pms_task_status_report_all",
    "r&r_ceo_of_the_quarter": "r&r_ceo_of the_quarter",
    "r&r_cross_functional": "r&r_cross_functional",
    "r&r_debutant_of_the_qtr": "r&r_debutant_of_the_qtr",
    "r&r_intrafunctional": "r&r_intrafunctional",
    "r&r_job_well_done": "r&r_job_well_done",
    "r&r_thank_you": "r&r_thank_you",
}


def get_collection(name: str) -> str:
    """Get collection name from mapping"""
    return COLLECTIONS.get(name, name)
