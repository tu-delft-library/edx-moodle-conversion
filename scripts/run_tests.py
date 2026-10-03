import subprocess
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "all"

paths = {
    "all":         ["tests/unit", "tests/integration"],
    "unit":        ["tests/unit"],
    "integration": ["tests/integration"],
    "live":        ["tests/live_moodle"],
}

if mode not in paths:
    print("usage: scripts/run_tests.py [all|unit|integration|live]")
    sys.exit(1)

sys.exit(subprocess.run(["pytest"] + paths[mode] + ["-v"]).returncode)
