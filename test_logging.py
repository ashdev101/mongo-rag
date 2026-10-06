"""
Test script to demonstrate the logging system.
Run this to see how different log levels and formats work.
"""
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from backend.logging_config import setup_logging, get_logger, log_with_context
import logging
import time


def test_basic_logging():
    """Test basic logging at different levels."""
    logger = get_logger("test.basic")
    
    print("\n" + "="*60)
    print("Testing Basic Logging")
    print("="*60)
    
    logger.debug("This is a DEBUG message - detailed diagnostic info")
    logger.info("This is an INFO message - general information")
    logger.warning("This is a WARNING message - something unusual happened")
    logger.error("This is an ERROR message - an error occurred")
    logger.critical("This is a CRITICAL message - serious problem")


def test_logging_with_context():
    """Test structured logging with context."""
    logger = get_logger("test.context")
    
    print("\n" + "="*60)
    print("Testing Logging with Context")
    print("="*60)
    
    log_with_context(
        logger,
        logging.INFO,
        "User action performed",
        user_id="user123",
        action="login",
        ip_address="192.168.1.1",
        duration_ms=145
    )
    
    log_with_context(
        logger,
        logging.WARNING,
        "API rate limit approaching",
        user_id="user456",
        requests_count=95,
        limit=100,
        reset_time="60s"
    )


def test_exception_logging():
    """Test exception logging."""
    logger = get_logger("test.exception")
    
    print("\n" + "="*60)
    print("Testing Exception Logging")
    print("="*60)
    
    try:
        # Simulate an error
        result = 1 / 0
    except Exception as e:
        logger.error("An error occurred in calculation", exc_info=True)
        
        log_with_context(
            logger,
            logging.ERROR,
            f"Division error: {str(e)}",
            operation="divide",
            numerator=1,
            denominator=0
        )


def test_access_logging():
    """Test access logging simulation."""
    access_logger = get_logger("access")
    
    print("\n" + "="*60)
    print("Testing Access Logging")
    print("="*60)
    
    # Simulate some HTTP requests
    requests = [
        ("POST", "/api/messages", 200, 0.123),
        ("GET", "/api/health", 200, 0.012),
        ("POST", "/api/secure-query", 200, 1.456),
        ("POST", "/api/messages", 500, 0.234),
    ]
    
    for method, endpoint, status, duration in requests:
        access_logger.info(
            f"Request: {method} {endpoint} - Status: {status}",
            extra={
                "request_id": f"req-{int(time.time()*1000)}",
                "method": method,
                "endpoint": endpoint,
                "status_code": status,
                "duration": duration,
                "user_email": "test@example.com"
            }
        )


def test_performance_logging():
    """Test performance logging."""
    logger = get_logger("test.performance")
    
    print("\n" + "="*60)
    print("Testing Performance Logging")
    print("="*60)
    
    # Simulate some operations with timing
    operations = [
        ("Database query", 0.045),
        ("API call", 0.312),
        ("Data processing", 0.156),
        ("Response generation", 0.089),
    ]
    
    total_start = time.time()
    
    for operation, duration in operations:
        time.sleep(duration)  # Simulate work
        actual_duration = time.time() - total_start
        
        log_with_context(
            logger,
            logging.INFO,
            f"{operation} completed",
            operation=operation,
            duration=round(actual_duration, 3)
        )
        
        total_start = time.time()


def main():
    """Run all logging tests."""
    print("\n" + "="*60)
    print("PRODUCTION-READY LOGGING SYSTEM TEST")
    print("="*60)
    
    # Setup logging in development mode
    print("\n🔧 Setting up logging system (development mode)...")
    setup_logging(
        environment="development",
        log_level="DEBUG",
        log_dir="logs",
        app_name="tataplay_test"
    )
    
    print("\n✅ Logging system initialized!")
    print(f"📁 Log files will be created in: logs/")
    print(f"   - tataplay_test_app.log (all logs)")
    print(f"   - tataplay_test_error.log (errors only)")
    print(f"   - tataplay_test_access.log (access logs)")
    
    # Run tests
    test_basic_logging()
    test_logging_with_context()
    test_exception_logging()
    test_access_logging()
    test_performance_logging()
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
    print("\n📊 Check the log files in the 'logs/' directory to see the output.")
    print("💡 Try running with ENVIRONMENT=production to see JSON format:")
    print("   python test_logging.py")
    print("\n")


if __name__ == "__main__":
    main()
