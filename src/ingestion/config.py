from enum import Enum

# ---------------------------
# Enum for STRICT report names
# ---------------------------

class ReportName(Enum):
    base_report = "base_report"                                                     # 1.DatabaseReport_Rpt_Data base Report_for Kreeda Labs.xlsx
    goal_setting_status = "goal_setting_status"                                     # Goal Status Report 2025-26 All.xlsx
    performance_goal_report_2025_2026 = "performance_goal_report_2025_2026"         # Performance Goal Report 25-26.xlsx
    permormance_rating_report_year_2025_2026 = "permormance_rating_report_year_2025_2026"

    # extended report types
    historical_ratings_and_other_information = "historical_ratings_and_other_information"
    performance_360_feedback_participants_status_all = "performance_360_degree_feedback_participants_status_all"
    pip_transaction_report = "pip_transaction_report"
    pms_q2_25_26_rating_report_all = "pms_q2_25_26_rating_report_all"
    pms_task_status_report_all = "pms_task_status_report_all"
    goal_detail_report="goal_detail_report"
    leave_transaction_with_balance_report_leave_transaction_with_balance_report="leave_transaction_with_balance_report_leave_transaction_with_balance_report"
    offboarding_checklist="offboarding_checklist"


# ---------------------------
# REPORT CONFIG DICTIONARY
# ---------------------------


REPORT_CONFIG = {
    "base_report": {
        "FIELDS": ['Employee Code', 'FIRST NAME', 'LAST NAME', 'GRADE', 'Grade Level',
            'Designation', 'DEPARTMENT', 'SUB-DEPT', 'Location', 'Office', 'Region',
            'DOJ', 'Manager Code', 'Reporting To', 'State', 'Circle', 'DOB', 'M/F',
            'Primary Email', 'Assignment Status Type', 'DOR', 'DOL', 'Role',
            'Last year Rating', 'Reason for Resignation'],

        "KEY_RENAMES": {
            "Employee Code" : "employee code",
            "FIRST NAME" : "first name",
            "LAST NAME" : "last name",
            "GRADE" : "grade",
            "Grade Level" : "grade level",
            "Designation" : "Designation",
            "DEPARTMENT" : "department",
            "SUB-DEPT" : "sub department",
            "Location" : "location",
            "Office" : "office",
            "Region" : "region",
            "DOJ" : "date of joining",
            "Manager Code" : "manager employee code",
            "Reporting To" : "reporting to",
            "State" : "state",
            "Circle" : "circle",
            "DOB" : "date of birth",
            "M/F" : "gender",
            "Primary Email" : "email",
            "Assignment Status Type" : "assignment status type",
            "DOR" : "date of resignation",
            "DOL" : "date of leaving",
            "Role" : "role",
            "Last year Rating" : "last year rating",
            "Reason for Resignation" : "reason for resignation"
    },

        "NUMERIC_FIELDS": [
            "employee code",
            "manager employee code",
            "last year rating"  
        ],

        "DATE_FIELDS": [
            "date of birth",
            "date of joining",
            "date of leaving",
            "date of resignation"
        ],

        "TARGET_COLLECTION": "base_report"
    },

    "goal_setting_status": {
        "FIELDS": [
            'PERSON_NUMBER', 
            'EMP_NAME', 
            'Department', 
            'SUB_DEPARTMENT',
            'Designation', 
            'Office_Location', 
            'Work_location', 
            'Parent_Grade',
            'Sub_grade', 
            'Region', 
            'DOJ', 
            'Manager_Number',
            'Reporting_To',
            'REVIEWER_NUMBER', 
            'REVIEWER_NAME', 
            'STATUS'
        ],

        "KEY_RENAMES": {
            "PERSON_NUMBER" : "employee code", 
            "EMP_NAME" : "employee name", 
            "Department" : "department", 
            "SUB_DEPARTMENT" : "sub department",
            "Designation" : "designation", 
            "Office_Location" : "office", 
            "Work_location" : "location", 
            "Parent_Grade" : "grade",
            "Sub_grade" : "grade level", 
            "Region" : "region", 
            "DOJ" : "date of joining", 
            "Manager_Number" : "manager employee code",
            "Reporting_To" : "reporting to",
            "REVIEWER_NUMBER" : "reviewer employee code", 
            "REVIEWER_NAME" : "reviewer name", 
            "STATUS":"status"
        },

        "NUMERIC_FIELDS": [
            "employee code",
            "manager employee code",
            "reviewer employee code"
        ],

        "DATE_FIELDS": [
            "date of joining"
        ],

        "TARGET_COLLECTION": "goal_setting_status"
    },

    "performance_goal_report_2025_2026": {
        "FIELDS": ['Person Number', 'Name', 'Department', 'Sub Department', 'Grade',
                    'Sub Grade', 'Region', 'Review Period Name', 'Goal Plan Name',
                    'Goal Name', 'Weight', 'Description'],

        "KEY_RENAMES": {
            "Person Number" : "employee code",
            "Name" : "employee name",
            "Department" : "Department",
            "Sub Department" : "sub department",
            "Grade" : "grade",
            "Sub Grade" : "grade level",
            "Region" : "region",
            "Review Period Name" : "review period name",
            "Goal Plan Name" : "goal plan name",
            "Goal Name" : "goal name",
            "Weight" : "weight",
            "Description" : "description"
        },

        "NUMERIC_FIELDS": [
            "employee code",
            "weight"
        ],
        "DATE_FIELDS": [],
        "TARGET_COLLECTION": "performance_goal_report_2025_2026"
    },

    "performance_rating_report_2025_2026": {
        "FIELDS": [
            "business unit name",
            "department",
            "employee e mail address",
            "employee name",
            "employee person number",
            "final status",
            "grade",
            "job",
            "location name",
            "manager e mail address",
            "manager name",
            "manager person number",
            "manager rating",
            "parent department",
            "parent grade",
            "performance document name",
            "self rating"
        ],

        "KEY_RENAMES": {
            "employee e mail address": "email",
            "employee person number": "employee code",
            "business unit name": "region",
            "job": "designation",
            "parent grade": "grade",
            "grade": "grade level",
            "parent department": "department",
            "department": "sub department",
            "manager person number": "manager employee code",
            "manager e mail address": "manager email",
            "location name": "office"
        },

        "NUMERIC_FIELDS": [
            "self rating",
            "manager rating",
            "employee code",
            "manager employee code"
        ],

        "DATE_FIELDS": [],
        
        "TARGET_COLLECTION": "permormance_rating_report_year_2025_2026"
    },

    # Additional configs (skeleton — you can fill later)
    "historical_ratings_and_other_information": {
        "FIELDS": [
            "Employee Code",
            "FIRST NAME",
            "LAST NAME",
            "GRADE",
            "Grade Level",
            "Designation",
            "DEPARTMENT",
            "SUB-DEPT",
            "Location",
            "Office",
            "Region",
            "DOJ",
            "Assignment Status Type",
            "Final Rating  20-21",
            "Final Rating  21-22",
            "Final Rating  22-23",
            "Final Rating  23-24",
            "Last Promotion date",
            "Rating 24-25",
            "Experience Prior to Tata Play",
            "Tata Play Experience",
            "Total Yrs Exp",
            "Previous company",
            "MT Batch",
            "Highest Qualification",
            "University Name"
        ],
        "KEY_RENAMES": {
            "Employee Code": "employee code",
            "FIRST NAME": "first name",
            "LAST NAME": "last name",
            "GRADE": "grade",
            "Grade Level": "grade level",
            "Designation": "designation",
            "DEPARTMENT": "department",
            "SUB-DEPT": "sub department",
            "Location": "location",
            "Office": "office",
            "Region": "region",
            "DOJ": "date of joining",
            "Assignment Status Type": "assignment status type",
            "Final Rating  20-21": "final rating 20-21",
            "Final Rating  21-22": "final rating 21-22",
            "Final Rating  22-23": "final rating 22-23",
            "Final Rating  23-24": "final rating 23-24",
            "Last Promotion date": "last promotion date",
            "Rating 24-25": "rating 24-25",
            "Experience Prior to Tata Play": "experience prior to tata play",
            "Tata Play Experience": "tata play experience",
            "Total Yrs Exp": "total years experience",
            "Previous company": "previous company",
            "MT Batch": "mt batch",
            "Highest Qualification": "highest qualification",
            "University Name": "university name"
        },
        "NUMERIC_FIELDS":  [
            "employee code",
            "final rating 20-21",
            "final rating 21-22",
            "final rating 22-23",
            "final rating 23-24",
            "rating 24-25",
            "experience prior to tata play",
            "tata play experience",
            "total years experience",
            "mt batch"
        ],
        "DATE_FIELDS": [
            "date of joining",
            "last promotion date"
        ],
        "TARGET_COLLECTION": "historical_ratings_and_other_information"
    },

    "performance_360_feedback_participants_status_all": {
        "FIELDS": [
            "Person Number",
            "Name",
            "Parent Grade",
            "Business Unit Name",
            "Parent Department",
            "Department Name",
            "Performance Document Name",
            "Participant Name",
            "Role",
            "Role Status",
            "Participation Status"
    ],
    "KEY_RENAMES": {
        "Person Number": "employee code",
        "Name": "employee name",
        "Parent Grade": "grade",
        "Business Unit Name": "region",
        "Parent Department": "department",
        "Department Name": "sub department",
        "Performance Document Name": "performance document name",
        "Participant Name": "participant name",
        "Role": "role",
        "Role Status": "role status",
        "Participation Status": "participation status"
    },
        "NUMERIC_FIELDS": ["employee code"],
        "DATE_FIELDS": [],
        "TARGET_COLLECTION": "performance_360_feedback_participants_status_all"
    },

    "pip_transaction_report": {
        "FIELDS": [
            "PERSON_NUMBER",
        "First_Name",
        "Last_Name",
        "Employee_Email_ID",
        "Parent_Grade",
        "Sub_grade",
        "Designation",
        "SUB_DEPARTMENT",
        "Office_Location",
        "Region",
        "DOJ",
        "Manager_Number",
        "MAN_EMAIL",
        "PIP Submitted Date",
        "PIP Completion Date",
        "RHR_NAME",
        "RHR_Number",
        "RHR_EMAIL",
        "Reviewer_NAME",
        "Reviewer_Number",
        "Reviewer_EMAIL",
        "Assigned Date",
        "Assigned To",
        "\t\nTask status",
        "PIP Doc status"
        ],
        "KEY_RENAMES": {
            "PERSON_NUMBER": "employee code",
        "First_Name": "first name",
        "Last_Name": "last name",
        "Employee_Email_ID": "employee email",
        "Parent_Grade": "grade",
        "Sub_grade": "grade level",
        "Designation": "designation",
        "SUB_DEPARTMENT": "sub department",
        "Office_Location": "office",
        "Region": "region",
        "DOJ": "date of joining",
        "Manager_Number": "manager employee code",
        "MAN_EMAIL": "manager email",
        "PIP Submitted Date": "pip submitted date",
        "PIP Completion Date": "pip completion date",
        "RHR_NAME": "rhr name",
        "RHR_Number": "rhr employee code",
        "RHR_EMAIL": "rhr email",
        "Reviewer_NAME": "reviewer name",
        "Reviewer_Number": "reviewer employee code",
        "Reviewer_EMAIL": "reviewer email",
        "Assigned Date": "assigned date",
        "Assigned To": "assigned to",
        "\t\nTask status": "task status",
        "PIP Doc status": "pip document status"
        },
        "NUMERIC_FIELDS": [
            "employee code",
            "manager employee code",
            "rhr employee code",
            "reviewer employee code"
        ],
        "DATE_FIELDS": ["assigned date", "pip submitted date", "pip completion date"],
        "TARGET_COLLECTION": "pip_transaction_report"
    },

    "pms_q2_25_26_rating_report_all": {
        "FIELDS": [
            "Employee Person Number",
            "Employee Name",
            "Employee E-Mail Address",
            "Manager Person Number",
            "Manager Name",
            "Manager E-Mail Address",
            "Business Unit Name",
            "Department",
            "Parent Department",
            "Grade",
            "Parent Grade",
            "Job",
            "Location Name",
            "Performance Document Name",
            "Overall Manager Rating",
            "Overall Employee Rating",
            "Performance Document Status"
        ],
        "KEY_RENAMES": {
            "Employee Person Number": "employee code",
            "Employee Name": "employee name",
            "Employee E-Mail Address": "email",

            "Manager Person Number": "manager employee code",
            "Manager Name": "manager name",
            "Manager E-Mail Address": "manager email",

            "Business Unit Name": "region",
            "Department": "sub department",
            "Parent Department": "department",
            
            "Grade": "grade level",
            "Parent Grade": "grade",

            "Job": "designation",

            "Location Name": "location",
            "Performance Document Name": "performance document name",
            "Overall Manager Rating": "overall manager rating",
            "Overall Employee Rating": "overall employee rating",
            "Performance Document Status": "performance document status"
        },
        "NUMERIC_FIELDS": ["employee code",
                        "manager employee code",
                        "overall manager rating",
                        "overall employee rating"],
        "DATE_FIELDS": [],
        "TARGET_COLLECTION": "pms_q2_25_26_rating_report"
    },

    "pms_task_status_report_all": {
        "FIELDS": [
            "Perosn Number",
            "Name",
            "Employee Email ID",
            "Manager Person Number",
            "Manager Name",
            "Manager Email Address",
            "Reviewer Number",
            "Reviewer Name",
            "Business Unit",
            "Parent Department",
            "Sub Department",
            "Grade",
            "Sub Grade",
            "Employee Evaluation",
            "Employee Evaluation Status",
            "Manager Evaluation",
            "Manager Evaluation Status",
            "Initiate Approval",
            "Initiate Approval Status",
            "Share Document",
            "Share Document Status",
            "Final Status"
        ],
        "KEY_RENAMES": {
            "Perosn Number": "employee code",
            "Name": "employee name",
            "Employee Email ID": "email",
            "Manager Person Number": "manager employee code",
            "Manager Name": "manager name",
            "Manager Email Address": "manager email",
            "Reviewer Number": "reviewer employee code",
            "Reviewer Name": "reviewer name",
            "Business Unit": "region",
            "Parent Department": "department",
            "Sub Department": "sub department",
            "Grade": "grade",
            "Sub Grade": "grade level",
            "Employee Evaluation": "employee evaluation",
            "Employee Evaluation Status": "employee evaluation status",
            "Manager Evaluation": "manager evaluation",
            "Manager Evaluation Status": "manager evaluation status",
            "Initiate Approval": "initiate approval",
            "Initiate Approval Status": "initiate approval status",
            "Share Document": "share document",
            "Share Document Status": "share document status",
            "Final Status": "final status"
        },
        "NUMERIC_FIELDS": ["employee code",
                        "manager employee code",
                        "reviewer employee code"],
        "DATE_FIELDS": [],
        "TARGET_COLLECTION": "pms_task_status_report_all"
    },

    "leave_transaction_with_balance_report_leave_transaction_with_balance_report": {
        "FIELDS": [
            "EMPLOYEE_CODE",
            "NAME",
            "EMPLOYEE_EMAIL_ADDRESS",
            "ABSENCE_NAME",
            "START_DATE",
            "END_DATE",
            "DURATION",
            "STATUS_OF_LEAVE",
            "APPROVAL_STATUS",
            "MANAGER_EMAIL",
            "BALANCE_VAL"
        ],
        "KEY_RENAMES": {
            "EMPLOYEE_CODE": "employee code",
            "NAME": "employee name",
            "EMPLOYEE_EMAIL_ADDRESS": "email",
            "ABSENCE_NAME": "absence name",
            "START_DATE": "start date",
            "END_DATE": "end date",
            "DURATION": "duration",
            "STATUS_OF_LEAVE": "status of leave",
            "APPROVAL_STATUS": "approval status",
            "MANAGER_EMAIL": "manager email",
            "BALANCE_VAL": "balance value"
        },
        "NUMERIC_FIELDS": [
                "employee code",
                "duration",
                "balance value"
        ],
        "DATE_FIELDS": [
                    "start date",
                    "end date"
        ],
        "TARGET_COLLECTION": "leave_transaction_with_balance_report_leave_transaction_with_balance_report"
    },

    "goal_detail_report": {
        "FIELDS": [
            "Person Number",
            "First Name",
            "Last Name",
            "Department",
            "Sub Department",
            "Grade",
            "Sub Grade",
            "Business Unit",
            "Goal Type",
            "Goal Name",
            "Goal Desciption",
            "Start Date",
            "Target Completion Date",
            "Creation Date",
            "Development Goal Status",
            "Category",
            "Manager_Approval_Date"
        ],
        "KEY_RENAMES": {
            "Person Number": "employee code",
            "First Name": "first name",
            "Last Name": "last name",
            "Department": "department",
            "Sub Department": "sub department",
            "Grade": "grade",
            "Sub Grade": "grade level",
            "Business Unit": "region",
            "Goal Type": "goal type",
            "Goal Name": "goal name",
            "Goal Desciption": "goal description",
            "Start Date": "start date",
            "Target Completion Date": "target completion date",
            "Creation Date": "creation date",
            "Development Goal Status": "development goal status",
            "Category": "category",
            "Manager_Approval_Date": "manager approval date"
        },
        "NUMERIC_FIELDS": [
            "employee code"
        ],
        "DATE_FIELDS": [
            "start date",
            "target completion date",
            "creation date",
            "manager approval date"
        ],
        "TARGET_COLLECTION": "goal_detail_report"
    },


    "offboarding_checklist": {
        "FIELDS": {
            "Core HR": [
                "Employee ID",
                "Employee name",
                "Grade",
                "Grade Level",
                "Designation",
                "Department",
                "Sub Department",
                "Region",
                "Employee Status",
                "Reporting Manager",
                "Date of  Joining",
                "Date of Resignation",
                "Date of Leaving",
            ],

            "Status": [
                " Exit Checklist - Employee",
                "Exit Checklist - Reporting Manager",
                "Exit Checklist - Customer Operations",
                "Exit Checklist - Facilities",
                "Exit Checklist - IT",
                "Exit Checklist - Finance Accounts",
                "Exit Checklist - Finance Assets",
                "Exit Checklist - RHR Ops",
                "Exit Checklist - Payroll",
                "Exit Checklist - RHR",
                "Exit Checklist - CHR Ops",
                "Exit Checklist - CHR",
                "All Task Status",
            ],

            "Exit Checklist - Employee": [
                "Pending Flexi pay Claims sent to payroll",
                "Proof of Investements sent to Payroll",
                "Travel claims raised and Manager has approved it in system",
                "Pending Hotel bills sent to Osource",
                "Personal Email ID/Address",
            ],

            "Exit Checklist - Reporting Manager": [
                "Outstanding matters completed",
                "Material Returned",
                "Password and documents handed over",
                "All expenses and Claims approved",
                "Comments",
            ],

            "Exit Checklist - Customer Operations": [
                "Employee Account Disabled",
            ],

            "Exit Checklist - Facilities": [
                "Employee ID Card returned",
                "Access Card Returned",
                "Mention the Amount in case of recovery for Employee",
                "Stationary Returned",
                "Keys to workstation/locker returned",
                "Business card returned",
                "Corporate CC Returned",
                "COCP Recovery Amount (Mobile)",
                "COCP Recovery Amount (Broadband)",
                "Comments",
            ],

            "Exit Checklist - IT": [
                "PC/Laptop Returned",
                "Amount of Recovery for PC/Laptop",
                "Cosummables/Accossories returned",
                "Amount of recovery for consumables/accessories",
                "Account Ids (login id.,email id.)/SIEBEL/SAP/ESS password disabled",
                "Temp Network folders deleted",
                "CRM(SSO)/PRM/Kenan/VMS/EVD/Victory/BO/SAP IDs Disabled",
                "NAS Folder Name with Access Details/Other disabled",
                "Comments",
            ],

            "Exit Checklist - Finance Accounts": [
                "Outstanding Travel Advance/Imprest amount to be recovered",
                "Outstanding relocation amount to be recovered",
                "Travel claim bill received",
                "Amount of recovery for Travel",
                "Personal Expense",
                "Comments",
            ],

            "Exit Checklist - Finance Assets": [
                "Assets submitted by employee",
                "Amount to be recovered against asset",
                "Comments",
            ],

            "Exit Checklist - RHR Ops": [
                "Notice Period Recovery",
                "Verified all checklist data submitted by respective department",
                "DD received Notice recovery",
                "Any leave without pay not applied in the system",
                "Recovery Amount (except -JB,NP,Relocation)",
                "Comments",
            ],

            "Exit Checklist - RHR": [
                "Employee Status",
                "Comments",
            ],

            "Exit Checklist - CHR Ops": [
                "Amount of Training Cost to be recovered",
                "Notice Buy-Out Reimbursement Cost to be Recovered",
                "Joining Bonus to be recovered",
                "Annual Leave Balance (In days)",
                "Encashable Sick Leave Balance (In days)",
                "Encashable Casual Leave Balance (In days)",
                "Special Leave Deduction",
                "Group Transfer",
                "Group Compnay Name",
                "DoJ in Group Company",
                "Gratuity Processed from the Group Company, if any",
                "Tata Group DoJ (If different from date mentioned earlier)",
                "Name of the Point of Contact  of the new Group Company",
                "Designation of the POC",
                "Department of the POC",
                "Email ID of the POC",
                "Contact Number of the POC",
                "Annual Leave Transfer to new Group Company",
                "Number of days of leaves to be transferred",
            ],

            "Exit Checklist - CHR": [
                "Comments",
            ],

            "Exit Checklist - Payroll": [
                "Gratuity Eligibility",
                "Gratuity Payable",
                "TataPlay Subscription",
                "Performance linked Incentive (Sales Incentive)",
                "Performance Linked Incentive (Bonus)",
                "Any other payout (LTIP / Special allowance /other)",
                "Rewards",
                "Statutory Bonus",
                "Relocation reimbursement",
                "City Compensatory Allowance",
                "MIP Deduct/Refund",
                "MIP Top up Deduction/Refund",
                "NPS Recovery",
                "PF Recovery",
            ]
        },
        "KEY_RENAMES": {
            "Core HR": {
                "Employee ID": "employee code",
                "Employee name": "employee name",
                "Grade": "grade",
                "Grade Level": "grade level",
                "Designation": "designation",
                "Department": "department",
                "Sub Department": "sub department",
                "Region": "region",
                "Employee Status": "employee status",
                "Reporting Manager": "manager name",
                "Date of  Joining": "date of joining",
                "Date of Resignation": "date of resignation",
                "Date of Leaving": "date of leaving",
            },

            "Status": {
                " Exit Checklist - Employee": "exit checklist employee",
                "Exit Checklist - Reporting Manager": "exit checklist reporting manager",
                "Exit Checklist - Customer Operations": "exit checklist customer operations",
                "Exit Checklist - Facilities": "exit checklist facilities",
                "Exit Checklist - IT": "exit checklist it",
                "Exit Checklist - Finance Accounts": "exit checklist finance accounts",
                "Exit Checklist - Finance Assets": "exit checklist finance assets",
                "Exit Checklist - RHR Ops": "exit checklist rhr ops",
                "Exit Checklist - Payroll": "exit checklist payroll",
                "Exit Checklist - RHR": "exit checklist rhr",
                "Exit Checklist - CHR Ops": "exit checklist chr ops",
                "Exit Checklist - CHR": "exit checklist chr",
                "All Task Status": "all task status",
            },

            "Exit Checklist - Employee": {
                "Pending Flexi pay Claims sent to payroll": "pending flexi pay claims sent to payroll",
                "Proof of Investements sent to Payroll": "proof of investments sent to payroll",
                "Travel claims raised and Manager has approved it in system": "travel claims approved by manager",
                "Pending Hotel bills sent to Osource": "pending hotel bills sent to osource",
                "Personal Email ID/Address": "personal email",
            },

            "Exit Checklist - Reporting Manager": {
                "Outstanding matters completed": "outstanding matters completed",
                "Material Returned": "material returned",
                "Password and documents handed over": "password and documents handed over",
                "All expenses and Claims approved": "all expenses and claims approved",
                "Comments": "comments",
            },

            "Exit Checklist - Customer Operations": {
                "Employee Account Disabled": "employee account disabled",
            },

            "Exit Checklist - Facilities": {
                "Employee ID Card returned": "employee id card returned",
                "Access Card Returned": "access card returned",
                "Mention the Amount in case of recovery for Employee": "recovery amount employee",
                "Stationary Returned": "stationary returned",
                "Keys to workstation/locker returned": "keys workstation/locker returned",
                "Business card returned": "business card returned",
                "Corporate CC Returned": "corporate cc returned",
                "COCP Recovery Amount (Mobile)": "cocp recovery amount mobile",
                "COCP Recovery Amount (Broadband)": "cocp recovery amount broadband",
                "Comments": "comments",
            },

            "Exit Checklist - IT": {
                "PC/Laptop Returned": "pc/laptop returned",
                "Amount of Recovery for PC/Laptop": "amount recovery pc/laptop",
                "Cosummables/Accossories returned": "consumables accessories returned",
                "Amount of recovery for consumables/accessories": "amount recovery consumables/accessories",
                "Account Ids (login id.,email id.)/SIEBEL/SAP/ESS password disabled": "account ids (login id.,email id.)/siebel/sap/ess password disabled",
                "Temp Network folders deleted": "temp network folders deleted",
                "CRM(SSO)/PRM/Kenan/VMS/EVD/Victory/BO/SAP IDs Disabled": "crm(sso)/prm/kenan/vms/evd/victory/bo/sap ids disabled",
                "NAS Folder Name with Access Details/Other disabled": "nas folder access disabled",
                "Comments": "comments",
            },

            "Exit Checklist - Finance Accounts": {
                "Outstanding Travel Advance/Imprest amount to be recovered": "outstanding travel advance/imprest recovered",
                "Outstanding relocation amount to be recovered": "outstanding relocation amount recovered",
                "Travel claim bill received": "travel claim bill received",
                "Amount of recovery for Travel": "amount recovery travel",
                "Personal Expense": "personal expense",
                "Comments": "comments",
            },

            "Exit Checklist - Finance Assets": {
                "Assets submitted by employee": "assets submitted employee",
                "Amount to be recovered against asset": "amount to be recovered against asset",
                "Comments": "comments",
            },

            "Exit Checklist - RHR Ops": {
                "Notice Period Recovery": "notice period recovery",
                "Verified all checklist data submitted by respective department": "verified all checklist data submitted by respective department",
                "DD received Notice recovery": "dd received notice recovery",
                "Any leave without pay not applied in the system": "any leave without pay not applied in the system",
                "Recovery Amount (except -JB,NP,Relocation)": "recovery amount general except jb np relocation",
                "Comments": "comments",
            },

            "Exit Checklist - RHR": {
                "Employee Status": "employee status",
                "Comments": "comments",
            },

            "Exit Checklist - CHR Ops": {
                "Amount of Training Cost to be recovered": "training cost recovered",
                "Notice Buy-Out Reimbursement Cost to be Recovered": "notice buyout reimbursement recovered",
                "Joining Bonus to be recovered": "joining bonus recovered",
                "Annual Leave Balance (In days)": "annual leave balance days",
                "Encashable Sick Leave Balance (In days)": "sick leave balance encashable in days",
                "Encashable Casual Leave Balance (In days)": "casual leave balance encashable in days",
                "Special Leave Deduction": "special leave deduction",
                "Group Transfer": "group transfer",
                "Group Compnay Name": "group company name",
                "DoJ in Group Company": "date of joining group company",
                "Gratuity Processed from the Group Company, if any": "gratuity processed group company",
                "Tata Group DoJ (If different from date mentioned earlier)": "tata group date of joining",
                "Name of the Point of Contact  of the new Group Company": "poc name group company",
                "Designation of the POC": "poc designation",
                "Department of the POC": "poc department",
                "Email ID of the POC": "poc email",
                "Contact Number of the POC": "poc contact number",
                "Annual Leave Transfer to new Group Company": "annual leave transfer group company",
                "Number of days of leaves to be transferred": "leave transfer days",
            },

            "Exit Checklist - CHR": {
                "Comments": "comments",
            },

            "Exit Checklist - Payroll": {
                "Gratuity Eligibility": "gratuity eligibility",
                "Gratuity Payable": "gratuity payable",
                "TataPlay Subscription": "tataplay subscription",
                "Performance linked Incentive (Sales Incentive)": "performance linked incentive sales incentive",
                "Performance Linked Incentive (Bonus)": "performance linked incentive bonus incentive",
                "Any other payout (LTIP / Special allowance /other)": "other payout",
                "Rewards": "rewards",
                "Statutory Bonus": "statutory bonus",
                "Relocation reimbursement": "relocation reimbursement",
                "City Compensatory Allowance": "city compensatory allowance",
                "MIP Deduct/Refund": "mip deduct/refund",
                "MIP Top up Deduction/Refund": "mip topup deduct/refund",
                "NPS Recovery": "nps recovery",
                "PF Recovery": "pf recovery",
            }
        },
        "NUMERIC_FIELDS" : {
            "Core HR": ["employee code"],
            "Exit Checklist - Facilities": [
                "cocp recovery amount mobile",
                "cocp recovery amount broadband"
            ],
            "Exit Checklist - IT": [
                "amount recovery pc/laptop",
                "amount recovery consumables/accessories"
            ],
            "Exit Checklist - Finance Accounts": [
                "outstanding travel advance/imprest recovered",
                "outstanding relocation amount recovered",
                "amount recovery travel",
                "personal expense"
            ],
            "Exit Checklist - Finance Assets": [
                "amount to be recovered against asset"
            ],
            "Exit Checklist - RHR Ops": [
                "dd received notice recovery",
                "Recovery Amount (except -JB,NP,Relocation)"
            ],
            "Exit Checklist - CHR Ops": [
                "annual leave balance days",
                "sick leave balance encashable in days",
                "casual leave balance encashable in days",
                "leave transfer days"
            ],
            "Exit Checklist - Payroll": [
                "gratuity payable",
                "tataplay subscription",
                "performance linked incentive sales incentive",
                "performance linked incentive bonus incentive",
                "other payout",
                "rewards",
                "statutory bonus",
                "relocation reimbursement",
                "city compensatory allowance",
                "mip deduct/refund",
                "mip topup deduct/refund",
                "nps recovery",
                "pf recovery",
            ]
        },
        "DATE_FIELDS": {
            "Core HR": [
                "date of joining",
                "date of resignation",
                "date of leaving"
            ],
            "Exit Checklist - CHR Ops": [
                "date of joining group company",
                "tata group date of joining"
            ]
        },
        "TARGET_COLLECTION": "offboarding_checklist"
    }
}
