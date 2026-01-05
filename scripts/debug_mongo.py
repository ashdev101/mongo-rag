#!/usr/bin/env python3
"""
Debug MongoDB connection in cqa.py context
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "hr-cleaned")

print("Environment Variables:")
print(f"MONGODB_URI: {MONGODB_URI}")
print(f"DB_NAME: {DB_NAME}")
print()

print("Test 1: Direct connection (like test_mongodb_simple.py)")
client1 = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db1 = client1[DB_NAME]
collections1 = db1.list_collection_names()
print(f"Collections found: {len(collections1)}")
if collections1:
    print(f"Collections: {collections1}")
client1.close()

print("\nTest 2: Using MongoDBToolExecutor pattern (like cqa.py)")
client2 = MongoClient(MONGODB_URI)
db2 = client2[DB_NAME]
collections2 = db2.list_collection_names()
print(f"Collections found: {len(collections2)}")
if collections2:
    print(f"Collections: {collections2}")
client2.close()

print("\nTest 3: Check all databases")
client3 = MongoClient(MONGODB_URI)
all_dbs = client3.list_database_names()
print(f"All databases: {all_dbs}")
print(f"Is '{DB_NAME}' in databases? {DB_NAME in all_dbs}")
client3.close()
