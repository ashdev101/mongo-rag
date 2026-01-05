#!/usr/bin/env python3
"""
Check all HR-related databases to find which has the most complete data
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

mongodb_uri = os.getenv("MONGODB_URI")
client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)

# Find all HR databases
hr_databases = [db for db in client.list_database_names() if "hr" in db.lower()]

print("=" * 80)
print("Checking all HR databases for collections...")
print("=" * 80)

for db_name in hr_databases:
    db = client[db_name]
    collections = db.list_collection_names()

    print(f"\nDatabase: {db_name}")
    print(f"Collections: {len(collections)}")

    if collections:
        total_docs = 0
        for coll in collections:
            count = db[coll].count_documents({})
            total_docs += count
            print(f"  - {coll}: {count:,} documents")
        print(f"Total documents: {total_docs:,}")
    else:
        print("  (empty)")

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)

# Find the database with most collections
best_db = max(hr_databases, key=lambda d: len(client[d].list_collection_names()))
best_collections = len(client[best_db].list_collection_names())

print(f"Use database: {best_db}")
print(f"It has the most collections: {best_collections}")
print("\nUpdate your .env file:")
print(f"DB_NAME={best_db}")

client.close()
