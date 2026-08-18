#!/usr/bin/env python3
"""
error_processor.py

Process an error log file with optional sorting and unique filtering.

Usage:
    ./error_processor.py <log_file_path> [--sort] [--unique]
    ./error_processor.py -h | --help

Arguments:
    log_file_path    Path to the error log file to process.
    --sort, -s       Sort the output lines alphabetically.
    --unique, -u     Remove duplicate adjacent lines (or all duplicates if combined with --sort).
"""

import argparse
import sys


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Process an error log file with optional sorting and unique filtering.",
        epilog="Example: ./error_processor.py error.log --sort --unique",
    )
    parser.add_argument(
        "log_file_path",
        nargs="?",
        help="Path to the error log file to process.",
    )
    parser.add_argument(
        "--sort",
        "-s",
        action="store_true",
        help="Sort the output lines alphabetically.",
    )
    parser.add_argument(
        "--unique",
        "-u",
        action="store_true",
        help="Remove duplicate lines from the output.",
    )

    args = parser.parse_args()

    if args.log_file_path is None:
        parser.print_help()
        sys.exit(1)

    return args


def process_log(log_file_path, sort_output=False, unique_output=False):
    try:
        with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File not found: {log_file_path}", file=sys.stderr)
        sys.exit(2)
    except PermissionError:
        print(f"Error: Permission denied: {log_file_path}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"Error reading file {log_file_path}: {e}", file=sys.stderr)
        sys.exit(4)

    if sort_output:
        lines.sort()

    if unique_output:
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        lines = unique_lines

    return lines


def main():
    args = parse_arguments()
    lines = process_log(args.log_file_path, args.sort, args.unique)
    try:
        sys.stdout.writelines(lines)
    except BrokenPipeError:
        # Handle early pipe close gracefully (e.g., piped to `head`)
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
