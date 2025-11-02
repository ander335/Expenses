"""
Simple test runner for the Expenses Bot.
Run this from the project root to execute all tests.
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    """Run the test suite."""
    
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("Running Expenses Bot Test Suite")
    print("=" * 50)
    
    # Run pytest on the tests directory
    command = [sys.executable, "-m", "pytest", "tests/", "-v"]
    
    print(f"Command: {' '.join(command)}")
    print("-" * 50)
    
    result = subprocess.run(command)
    
    print("\n" + "=" * 50)
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
        print("Check the output above for details.")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())