#!/usr/bin/env python3
import subprocess
import sys

# Use the first 5000 log entries so common patterns have a chance to repeat.
with open('error.log', 'r', encoding='utf-8', errors='replace') as f:
    lines = []
    count = 0
    for line in f:
        if line[:4].isdigit():
            count += 1
            if count > 5000:
                break
        lines.append(line)

with open('error_sample.log', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"sample log entries written: {count} (physical lines: {len(lines)})")

cmds = [
    ["python3", "error_processor.py", "error_sample.log", "-u", "-c", "-t", "5", "-n"],
    ["python3", "error_processor.py", "error_sample.log", "-u", "-c", "-t", "5"],
    ["python3", "error_processor.py", "error_sample.log", "-u", "-c", "-b", "3", "-n"],
]

for cmd in cmds:
    print("\n===", " ".join(cmd), "===")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        sys.exit(result.returncode)
    print(result.stdout)
