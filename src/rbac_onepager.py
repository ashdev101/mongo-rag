import os
from typing import Optional
from pymongo import MongoClient
import databse_dsitcint_values
import json
from dotenv import load_dotenv
from langgraph_sample import checkisSpecialHRUser
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))
from db.common_operations import findUser

access_record = json.load(open("./json_repo/access_record.json", "r"))

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv("MONGODB_DATABASE")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
employees = db["base_report"]

def fetch_user(email: Optional[str] , employee_code: Optional[int]) -> dict:
    record = findUser(email, employee_code)
    
    if record and "designation" in record:
        role = record["designation"].lower()
        region = record["region"]
        department = record["department"]
        region_access = [region] if record["department"] == "Human Resources" else [] #instantiate with single region by default
        department_exception = [] if record["department"] == "Human Resources" else databse_dsitcint_values.CANONICAL_DEPARTMENTS #no exception by default
        grade_allowed = databse_dsitcint_values.CANONICAL_GRADES if record["department"] == "Human Resources" else [] #all grades by default
        employees_code = record["employee code"]
        grade = record["grade"]
        special_hr_user = False

        #look if we have the relevant record into the access_record.json
        for rec in access_record:
            # print(rec["Emp Code"], record["employee_code"])
            if rec["Emp Code"] == record["employee code"]:
                # print("Found access record for", email)
                # print(rec)
                region_access = rec["Region"]
                department_exception = rec["Department_exception"]
                grade_allowed = rec["Grade"]
                special_hr_user = True
                break
    else:
        role = "unknown"
        region = "unknown"
        department = "unknown"
        employees_code = 0
        region_access = []
        department_exception = []
        grade_allowed = []
        grade = "unknown"

    print(f"Fetched role for {email}: {role}")
    return {"designation": role  , "employee code" : employees_code, "region": region , "department" : department , "region_access": region_access , "department_exception": department_exception , "grade_allowed": grade_allowed , "grade": grade} 

def rbac_onepager(hremail : str , employee_code: str) -> bool:
    print(f"RBAC check for {hremail} to access onepager of employee code {employee_code}")
    #get the users info from database
    role_info = fetch_user(hremail , None)

    if role_info["department"] != "Human Resources" or checkisSpecialHRUser(role_info):
        return False

    #fetch info about the employee from database
    employee_info = fetch_user(None , int(employee_code))

    # check for the department condition
    if employee_info["department"] in role_info["department_exception"]:
        return False

    # check for the region condition
    if employee_info["region"] not in role_info["region_access"]:
        return False

    # check for the grade condition
    if employee_info["grade"] not in role_info["grade_allowed"]:
        return False

    return True


if __name__ == "__main__":
    # Example usage
    print(rbac_onepager("Pallavi.Kaushik@tataplay.com" , "7011"))
