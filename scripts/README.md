# Testing & Debugging Scripts

This directory contains various testing and debugging scripts for the Claude QnA system.

## Scripts

### Connection Testing

- **`test_bedrock_connection.py`** - Test AWS Bedrock and Claude API connectivity
  ```bash
  python scripts/test_bedrock_connection.py
  ```
  Verifies:
  - AWS credentials
  - Bedrock model access
  - Tool calling capability

### MongoDB Testing

- **`test_mongodb_simple.py`** - Simple MongoDB connection test (Windows-compatible, no emojis)
  ```bash
  python scripts/test_mongodb_simple.py
  ```
  Quick test to verify MongoDB connectivity and basic operations.

- **`test_mongodb_connection.py`** - Comprehensive MongoDB test with detailed output
  ```bash
  python scripts/test_mongodb_connection.py
  ```
  Performs extensive testing including schema inspection and aggregation tests.

### Database Discovery

- **`check_all_hr_dbs.py`** - Compare all HR databases to find the best one
  ```bash
  python scripts/check_all_hr_dbs.py
  ```
  Lists all HR-related databases and their collection counts to help identify which database to use.

- **`debug_mongo.py`** - Debug MongoDB connection issues
  ```bash
  python scripts/debug_mongo.py
  ```
  Runs multiple connection patterns to troubleshoot MongoDB issues.

## Main Application

The main application files are in the root directory:
- `cqa.py` - Core Claude QnA implementation
- `test_cqa.py` - Interactive testing interface

## Usage

All scripts read configuration from the `.env` file in the root directory. Make sure your `.env` file is properly configured before running any scripts.
