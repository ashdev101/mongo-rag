import os
from typing import Optional
from pymongo import MongoClient

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv("MONGODB_DATABASE")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
employees = db["base_report"]

def findUser(email: Optional[str] , employee_code: Optional[int]) -> dict:
    record = employees.find_one({"email": email , "assignment status type": "ACTIVE"}, {"_id": 0, "employee code" : 1 , "designation": 1 , "region":1 , "department" : 1 , "grade":1}) if email else employees.find_one({"employee code": employee_code , "assignment status type": "ACTIVE"}, {"_id": 0, "employee code" : 1 , "designation": 1 , "region":1 , "department" : 1 , "grade":1})

    if not record:
        # this can happen if the user email address is stored in all lower case then as expected in db 
        record = employees.find_one({"email": email.lower() , "assignment status type": "ACTIVE"}, {"_id": 0, "employee code" : 1 , "designation": 1 , "region":1 , "department" : 1 , "grade":1}) if email else employees.find_one({"employee code": employee_code , "assignment status type": "ACTIVE"}, {"_id": 0, "employee code" : 1 , "designation": 1 , "region":1 , "department" : 1 , "grade":1})

    return record