#!/usr/bin/env python3
"""
MongoDB Connection Test
Verifies MongoDB connection and database structure before running cqa.py
"""

import os
from pymongo import MongoClient
from bson.json_util import dumps
from dotenv import load_dotenv

load_dotenv()


def test_mongodb_connection():
    """Test MongoDB connection and verify database structure"""

    mongodb_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME", "hr-cleaned")

    print("=" * 80)
    print("MongoDB Connection Test")
    print("=" * 80)
    print(f"Database: {db_name}")
    print(
        f"URI: {mongodb_uri[:50]}..."
        if mongodb_uri and len(mongodb_uri) > 50
        else f"URI: {mongodb_uri}"
    )
    print()

    if not mongodb_uri:
        print("❌ Error: MONGODB_URI not set in .env file")
        print("\nPlease set MONGODB_URI in your .env file:")
        print("MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/")
        return False

    try:
        # Test 1: Connect to MongoDB
        print("🔄 Test 1: Connecting to MongoDB...")
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)

        # Force connection attempt
        client.admin.command("ping")
        print("✅ Successfully connected to MongoDB!")

        # Test 2: List all databases
        print("\n🔄 Test 2: Listing databases...")
        databases = client.list_database_names()
        print(f"✅ Found {len(databases)} databases:")
        for db in databases:
            print(f"   - {db}")

        # Test 3: Check if target database exists
        print(f"\n🔄 Test 3: Checking if '{db_name}' database exists...")
        if db_name in databases:
            print(f"✅ Database '{db_name}' exists!")
        else:
            print(f"⚠️  Database '{db_name}' not found!")
            print(f"   Available databases: {', '.join(databases)}")
            print("\n   You may need to update DB_NAME in .env file")

        # Test 4: List collections in target database
        print(f"\n🔄 Test 4: Listing collections in '{db_name}'...")
        db = client[db_name]
        collections = db.list_collection_names()

        if not collections:
            print(f"⚠️  No collections found in '{db_name}'")
            return False

        print(f"✅ Found {len(collections)} collections:")
        for i, coll in enumerate(collections, 1):
            count = db[coll].count_documents({})
            print(f"   {i}. {coll} ({count:,} documents)")

        # Test 5: Sample data from key collections
        print("\n🔄 Test 5: Checking key collections and sample data...")

        key_collections = ["base_report", "leave_transaction", "offboarding"]
        found_collections = []

        for coll_name in key_collections:
            if coll_name in collections:
                found_collections.append(coll_name)
                collection = db[coll_name]

                # Get one sample document
                sample = collection.find_one({})

                if sample:
                    print(f"\n   ✅ Collection: {coll_name}")
                    print(f"      Document count: {collection.count_documents({}):,}")

                    # Show field names
                    fields = list(sample.keys())
                    print(f"      Fields ({len(fields)}): {', '.join(fields[:10])}")
                    if len(fields) > 10:
                        print(f"                      ... and {len(fields) - 10} more")

                    # Show sample document (first 500 chars)
                    sample_str = dumps(sample, indent=2)
                    if len(sample_str) > 500:
                        sample_str = sample_str[:500] + "\n      ... (truncated)"
                    print("\n      Sample document:")
                    for line in sample_str.split("\n"):
                        print(f"      {line}")
                else:
                    print(f"   ⚠️  Collection '{coll_name}' is empty")
            else:
                print(f"   ⚠️  Expected collection '{coll_name}' not found")

        # Test 6: Test aggregation capability
        print("\n🔄 Test 6: Testing aggregation query capability...")

        # Try a simple aggregation on base_report (or first available collection)
        test_coll = "base_report" if "base_report" in collections else collections[0]
        collection = db[test_coll]

        try:
            # Simple aggregation: count documents
            pipeline = [{"$count": "total"}]
            result = list(collection.aggregate(pipeline))

            if result:
                total = result[0].get("total", 0)
                print("✅ Aggregation test successful!")
                print(
                    f"   Counted {total:,} documents in '{test_coll}' using aggregation"
                )
            else:
                print("⚠️  Aggregation returned no results")
        except Exception as e:
            print(f"❌ Aggregation test failed: {e}")
            return False

        # Test 7: Test field access patterns
        print("\n🔄 Test 7: Checking field name patterns...")

        if "base_report" in collections:
            sample = db["base_report"].find_one({})

            if sample:
                # Check for common field name variations
                field_patterns = {
                    "email": ["primary email", "Primary Email", "email", "Email"],
                    "department": ["department", "Department", "DEPARTMENT"],
                    "employee_code": [
                        "employee code",
                        "Employee Code",
                        "employee_code",
                    ],
                }

                print("   Field name variations found:")
                for field_type, variations in field_patterns.items():
                    found = [v for v in variations if v in sample]
                    if found:
                        print(f"   ✅ {field_type}: {found[0]}")
                    else:
                        print(f"   ⚠️  {field_type}: Not found in sample")

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print("✅ MongoDB Connection: Working")
        print("✅ Database Access: Working")
        print(f"✅ Collections Found: {len(collections)}")
        print(f"✅ Key Collections: {len(found_collections)}/{len(key_collections)}")
        print("✅ Aggregation Queries: Working")
        print("=" * 80)

        if len(found_collections) < len(key_collections):
            print("\n⚠️  WARNING: Some expected collections are missing")
            missing = set(key_collections) - set(found_collections)
            print(f"   Missing: {', '.join(missing)}")
            print("   The QnA system will still work with available collections.")

        print("\n✅ MongoDB is ready for use with cqa.py!")
        print("\nNext steps:")
        print("  1. Run: python test_bedrock_connection.py  (test Claude)")
        print("  2. Run: python test_cqa.py                (interactive QnA)")
        print("  3. Run: python cqa.py                     (test suite)")

        client.close()
        return True

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting steps:")
        print("1. Verify MONGODB_URI in .env file")
        print("   - Check username and password")
        print("   - Ensure IP whitelist allows your IP (0.0.0.0/0 for all IPs)")
        print("   - Verify cluster URL is correct")
        print("\n2. Test connection with mongosh:")
        print(f'   mongosh "{mongodb_uri}"')
        print("\n3. Check MongoDB Atlas:")
        print("   - Database Access: User has read permissions")
        print("   - Network Access: IP is whitelisted")
        print("   - Cluster is running (not paused)")
        print("\n4. Verify database name:")
        print(f"   Current DB_NAME={db_name}")
        print("   Update in .env if different")

        return False


def show_collection_details(db, collection_name):
    """Show detailed information about a specific collection"""

    print("\n" + "=" * 80)
    print(f"Collection Details: {collection_name}")
    print("=" * 80)

    try:
        collection = db[collection_name]

        # Count
        count = collection.count_documents({})
        print(f"Total documents: {count:,}")

        # Sample documents
        samples = list(collection.find({}).limit(3))

        if samples:
            print(f"\nSample documents ({min(3, len(samples))}):")
            for i, doc in enumerate(samples, 1):
                print(f"\n--- Document {i} ---")
                print(dumps(doc, indent=2)[:500])
                if len(dumps(doc, indent=2)) > 500:
                    print("... (truncated)")
        else:
            print("\n⚠️  No documents found")

        # Field analysis
        if samples:
            all_fields = set()
            for doc in samples:
                all_fields.update(doc.keys())

            print(f"\nUnique fields ({len(all_fields)}):")
            for field in sorted(all_fields):
                print(f"  - {field}")

    except Exception as e:
        print(f"❌ Error accessing collection: {e}")


if __name__ == "__main__":
    success = test_mongodb_connection()

    # Optional: Interactive mode to explore specific collections
    if success:
        mongodb_uri = os.getenv("MONGODB_URI")
        db_name = os.getenv("DB_NAME", "hr-cleaned")

        print("\n" + "=" * 80)
        choice = (
            input("\nWould you like to explore a specific collection? (y/n): ")
            .strip()
            .lower()
        )

        if choice == "y":
            client = MongoClient(mongodb_uri)
            db = client[db_name]
            collections = db.list_collection_names()

            print("\nAvailable collections:")
            for i, coll in enumerate(collections, 1):
                print(f"{i}. {coll}")

            try:
                choice_num = int(input("\nEnter collection number (or 0 to skip): "))
                if 0 < choice_num <= len(collections):
                    show_collection_details(db, collections[choice_num - 1])
            except (ValueError, IndexError):
                print("Invalid choice")

            client.close()

    exit(0 if success else 1)
