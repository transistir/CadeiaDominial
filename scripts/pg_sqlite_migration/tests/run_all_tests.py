#!/usr/bin/env python
import argparse
import subprocess
import sys
from pathlib import Path

TESTS = [
    ("01_pre_migration_tests.py", ["--pg"]),
    ("02_schema_tests.py", ["--pg", "--sqlite"]),
    ("03_counts_checksums.py", ["--pg", "--sqlite"]),
    ("04_fk_integrity.py", ["--sqlite"]),
    ("05_numeric_datetime_drift.py", ["--pg", "--sqlite"]),
    ("06_perf_smoke.py", ["--pg", "--sqlite"]),
]


def run_test(script, base_args):
    cmd = [sys.executable, str(Path(__file__).parent / script)] + base_args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def main():
    parser = argparse.ArgumentParser(description="Run all migration validation tests")
    parser.add_argument("--pg", required=True, help="PostgreSQL connection string")
    parser.add_argument("--sqlite", required=True, help="SQLite file path")
    parser.add_argument("--report", default="migration_workspace/reports/summary.md")
    args = parser.parse_args()

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Migration Validation Report", ""]
    failures = []

    for script, params in TESTS:
        test_args = []
        if "--pg" in params:
            test_args += ["--pg", args.pg]
        if "--sqlite" in params:
            test_args += ["--sqlite", args.sqlite]
        ret, out, err = run_test(script, test_args)
        name = script.replace(".py", "")
        if ret == 0:
            lines.append(f"- ✅ {name}")
        else:
            lines.append(f"- ❌ {name}")
            failures.append(name)
        if out.strip():
            lines.append(f"  - stdout: `{out.strip()}`")
        if err.strip():
            lines.append(f"  - stderr: `{err.strip()}`")

    report_path.write_text("\n".join(lines))
    print(f"Report written to {report_path}")

    if failures:
        sys.stderr.write(f"Failed tests: {', '.join(failures)}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
