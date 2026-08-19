#!/usr/bin/env python3
"""
error_processor.py

Process an error log file with optional sorting, unique filtering, and frequency counting.

Usage:
    ./error_processor.py <log_file_path> [--sort] [--unique] [--count] [--top N]
    ./error_processor.py -h | --help

Arguments:
    log_file_path    Path to the error log file to process.
    --sort, -s       Sort the output lines alphabetically.
    --unique, -u     Remove duplicate lines from the output.
    --count, -c      Count occurrences of each unique line (sorted by count descending).
    --top N, -t N    Show only the top N most frequent entries (requires --count).
"""

import argparse
import sys
from collections import Counter


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Process an error log file with optional sorting, unique filtering, and frequency counting.",
        epilog="Examples:\n  ./error_processor.py error.log --sort --unique\n  ./error_processor.py error.log --count --top 20",
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
    parser.add_argument(
        "--count",
        "-c",
        action="store_true",
        help="Count occurrences of each unique line and print results sorted by count descending.",
    )
    parser.add_argument(
        "--top",
        "-t",
        type=int,
        metavar="N",
        help="When used with --count, show only the top N most frequent lines (N >= 0).",
    )

    args = parser.parse_args()

    if args.log_file_path is None:
        parser.print_help()
        sys.exit(1)

    return args


def count_lines(lines):
    """Return (line, count) pairs sorted by count descending, then alphabetically."""
    counter = Counter(lines)
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def process_log(log_file_path, sort_output=False, unique_output=False, count_output=False):
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

    if count_output:
        return count_lines(lines)

    return lines


def main():
    args = parse_arguments()
    result = process_log(
        args.log_file_path,
        sort_output=args.sort,
        unique_output=args.unique,
        count_output=args.count,
    )
    try:
        if args.count:
            top_n = args.top
            if top_n is not None and top_n < 0:
                top_n = 0
            if top_n is not None:
                result = result[:top_n]
            for line, count in result:
                sys.stdout.write(f"{count:>8}  {line}")
        else:
            if args.top is not None:
                print("Warning: --top is ignored unless --count is used.", file=sys.stderr)
            sys.stdout.writelines(result)
    except BrokenPipeError:
        # Handle early pipe close gracefully (e.g., piped to `head`)
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
