#!/usr/bin/env python3
"""error_processor.py - CLI tool for processing nginx/error logs.

Supports sorting, deduplication, frequency counting, top-N and bottom-N output,
regex-based filtering, and grouping of multi-line log entries.
"""

import argparse
import collections
import re
import sys
from pathlib import Path


# Nginx error lines start with a timestamp like "2026/08/18 11:41:22 [error] ..."
LOG_START_RE = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Process log files: sort, deduplicate, count, search."
    )
    parser.add_argument("log_file_path", help="Path to the log file to process")
    parser.add_argument(
        "-s", "--sort", action="store_true", help="Sort output alphabetically"
    )
    parser.add_argument(
        "-u", "--unique", action="store_true", help="Remove duplicate entries"
    )
    parser.add_argument(
        "-c", "--count", action="store_true", help="Count occurrences of each entry"
    )
    limit_group = parser.add_mutually_exclusive_group()
    limit_group.add_argument(
        "-t",
        "--top",
        type=int,
        metavar="N",
        help="When using --count, show only the top N most frequent entries",
    )
    limit_group.add_argument(
        "-b",
        "--bottom",
        type=int,
        metavar="N",
        help="When using --count, show only the bottom N least frequent entries",
    )
    parser.add_argument(
        "-e",
        "--search",
        metavar="PATTERN",
        help="Filter entries by regex pattern (case-sensitive by default)",
    )
    return parser.parse_args(argv)


def compile_search(pattern):
    """Compile a regex pattern, raising a clean error on invalid input."""
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex pattern: {exc}") from exc


def read_entries(path):
    """Read a text file and yield multi-line log entries as single strings."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            buffer = []
            for raw in fh:
                # Remove line ending characters and embedded carriage returns.
                line = raw.rstrip("\n\r").replace("\r", "")
                if not line:
                    continue
                if LOG_START_RE.match(line):
                    if buffer:
                        yield "\n".join(buffer)
                    buffer = [line]
                else:
                    buffer.append(line)
            if buffer:
                yield "\n".join(buffer)
    except FileNotFoundError:
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: permission denied: {path}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error reading {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def process_log(
    log_file_path,
    sort=False,
    unique=False,
    count=False,
    top=None,
    bottom=None,
    search=None,
):
    """Process a log file according to the requested options."""
    compiled = None
    if search is not None:
        compiled = compile_search(search)

    entries = read_entries(log_file_path)

    if compiled is not None:
        entries = (entry for entry in entries if compiled.search(entry))

    if sort:
        entries = sorted(entries)

    if unique:
        if sort:
            # sorted output: use itertools-like dedup for efficiency
            def dedup_sorted(seq):
                prev = object()
                for item in seq:
                    if item != prev:
                        yield item
                        prev = item
            entries = list(dedup_sorted(entries))
        else:
            entries = list(dict.fromkeys(entries))

    if count:
        counter = collections.Counter(entries)
        if bottom is not None:
            # Sort by count ascending, then alphabetically for stable tie-breaking
            counted = sorted(counter.items(), key=lambda kv: (kv[1], kv[0]))
            if bottom < 0:
                print("Warning: --bottom value must be non-negative; ignoring", file=sys.stderr)
            else:
                counted = counted[:bottom]
        else:
            # Sort by count descending, then alphabetically for stable tie-breaking
            counted = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
            if top is not None:
                if top < 0:
                    print("Warning: --top value must be non-negative; ignoring", file=sys.stderr)
                    top = None
                else:
                    counted = counted[:top]
        return counted

    if top is not None or bottom is not None:
        print(
            "Warning: --top/--bottom are only meaningful with --count; ignoring limit",
            file=sys.stderr,
        )

    return list(entries)


def format_counted(items):
    """Format counted entries with right-aligned counts in an 8-char field."""
    formatted = []
    for entry, count in items:
        lines = entry.split("\n")
        formatted.append(f"{count:>8}    {lines[0]}")
        for continuation in lines[1:]:
            formatted.append(f"{'':>8}    {continuation}")
    return formatted


def main(argv=None):
    args = parse_args(argv)

    result = process_log(
        args.log_file_path,
        sort=args.sort,
        unique=args.unique,
        count=args.count,
        top=args.top,
        bottom=args.bottom,
        search=args.search,
    )

    if not result:
        return

    if args.count:
        output = format_counted(result)
    else:
        output = result

    print("\n".join(output))


if __name__ == "__main__":
    main()
