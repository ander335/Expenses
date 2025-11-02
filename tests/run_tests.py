"""
Test runner script for the Expenses Bot.
Run this to execute all tests with appropriate configuration.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_tests():
    """Run the test suite with proper configuration."""
    
    # Ensure we're in the project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("Running Expenses Bot Test Suite")
    print("=" * 50)
    
    # Check if test requirements are installed
    try:
        import pytest
        print("✓ pytest is available")
    except ImportError:
        print("❌ pytest not found. Installing test requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"])
        print("✓ Test requirements installed")
    
    # Run different test categories
    test_commands = {
        "Unit Tests": ["python", "-m", "pytest", "tests/", "-m", "not integration", "-v"],
        "Integration Tests": ["python", "-m", "pytest", "tests/", "-m", "integration", "-v"],
        "All Tests": ["python", "-m", "pytest", "tests/", "-v"],
        "All Tests with Coverage": ["python", "-m", "pytest", "tests/", "--cov=.", "--cov-report=html", "--cov-report=term-missing"],
    }
    
    # Interactive mode - let user choose what to run
    print("\nAvailable test options:")
    for i, option in enumerate(test_commands.keys(), 1):
        print(f"{i}. {option}")
    
    try:
        choice = input("\nSelect test option (1-4) or press Enter for all tests: ").strip()
        
        if not choice:
            choice = "3"  # Default to all tests
        
        choice_map = {
            "1": "Unit Tests",
            "2": "Integration Tests", 
            "3": "All Tests",
            "4": "All Tests with Coverage"
        }
        
        selected_option = choice_map.get(choice, "All Tests")
        command = test_commands[selected_option]
        
        print(f"\n🚀 Running {selected_option}...")
        print(f"Command: {' '.join(command)}")
        print("-" * 50)
        
        # Run the tests
        result = subprocess.run(command, capture_output=False)
        
        print("\n" + "=" * 50)
        if result.returncode == 0:
            print("✅ All tests passed!")
            
            # If coverage was run, show where to find the report
            if "coverage" in selected_option.lower():
                print("📊 Coverage report generated in 'htmlcov/index.html'")
        else:
            print("❌ Some tests failed!")
            print("Check the output above for details.")
        
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n\n❌ Tests cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return 1


def run_specific_test():
    """Run a specific test file or test function."""
    
    print("\nRunning specific test...")
    test_path = input("Enter test file or test path (e.g., tests/test_receipt_processing.py::TestReceiptImageProcessing::test_process_receipt_image_success): ")
    
    if not test_path:
        print("No test path provided")
        return 1
    
    command = ["python", "-m", "pytest", test_path, "-v", "-s"]
    print(f"Running: {' '.join(command)}")
    
    result = subprocess.run(command)
    return result.returncode


def main():
    """Main entry point."""
    
    if len(sys.argv) > 1 and sys.argv[1] == "--specific":
        return run_specific_test()
    else:
        return run_tests()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)