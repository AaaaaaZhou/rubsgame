"""
Test runner for rubsgame
"""
import sys
import os
import subprocess

def run_tests():
    unittest_dir = os.path.dirname(__file__)
    src_dir = os.path.join(unittest_dir, '..', 'src')
    sys.path.insert(0, src_dir)

    print(f"\n{'='*60}")
    print("Running Rubsgame Tests")
    print(f"{'='*60}\n")

    tests_passed = 0
    tests_failed = 0

    for root, dirs, files in os.walk(unittest_dir):
        if '__pycache__' in root:
            continue
        for file in files:
            if file.startswith('test_') and file.endswith('.py'):
                test_path = os.path.join(root, file)
                print(f"\nRunning: {test_path}")

                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_path, "-v"],
                    capture_output=False
                )

                if result.returncode == 0:
                    tests_passed += 1
                else:
                    tests_failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print(f"{'='*60}\n")

    return tests_failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
