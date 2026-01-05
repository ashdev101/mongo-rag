#!/usr/bin/env python3
"""
Simple MongoDB Connection Test (Windows-compatible, no emojis)
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


def test_mongodb():
    """Test MongoDB connection and list databases/collections"""

    mongodb_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME", "hr-cleaned")

    print("=" * 80)
    print("MongoDB Connection Test")
    print("=" * 80)
    print(f"Database: {db_name}")
    print()

    if not mongodb_uri:
        print("ERROR: MONGODB_URI not set in .env file")
        return False

    try:
        print("Step 1: Connecting to MongoDB...")
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)

        # Test connection
        client.admin.command("ping")
        print("SUCCESS: Connected to MongoDB!")

        # List databases
        print("\nStep 2: Listing all databases...")
        databases = client.list_database_names()
        print(f"Found {len(databases)} databases:")
        for i, db in enumerate(databases, 1):
            print(f"  {i}. {db}")

        # Check target database
        print(f"\nStep 3: Checking database '{db_name}'...")
        if db_name not in databases:
            print(f"WARNING: Database '{db_name}' not found!")
            print("\nAvailable databases:")
            for db in databases:
                print(f"  - {db}")
            print("\nPlease update DB_NAME in .env to match one of the above.")
            return False

        print(f"SUCCESS: Database '{db_name}' exists!")

        # List collections
        print(f"\nStep 4: Listing collections in '{db_name}'...")
        db = client[db_name]
        collections = db.list_collection_names()

        if not collections:
            print(f"WARNING: No collections found in '{db_name}'")
            print("\nThis database exists but is empty.")
            return False

        print(f"SUCCESS: Found {len(collections)} collections:")
        for i, coll in enumerate(collections, 1):
            count = db[coll].count_documents({})
            print(f"  {i}. {coll} ({count:,} documents)")

        # Test aggregation
        print("\nStep 5: Testing aggregation query...")
        test_coll = collections[0]
        pipeline = [{"$count": "total"}]
        result = list(db[test_coll].aggregate(pipeline))

        if result:
            total = result[0].get("total", 0)
            print(
                f"SUCCESS: Aggregation works! Counted {total:,} documents in '{test_coll}'"
            )
        else:
            print("WARNING: Aggregation returned no results")

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print("Connection: OK")
        print(f"Database '{db_name}': OK")
        print(f"Collections: {len(collections)}")
        print("Aggregation: OK")
        print("=" * 80)
        print("\nMongoDB is ready for use with cqa.py!")

        client.close()
        return True

    except Exception as e:
        print("\nERROR: Connection failed!")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check MONGODB_URI in .env file")
        print("2. Verify username/password are correct")
        print("3. Check IP whitelist in MongoDB Atlas (add 0.0.0.0/0 for all IPs)")
        print("4. Ensure cluster is running (not paused)")
        return False


if __name__ == "__main__":
    success = test_mongodb()

    if success:
        print("\nNext step: Run test_bedrock_connection.py")

    exit(0 if success else 1)
