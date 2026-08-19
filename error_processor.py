#!/usr/bin/env python3
"""error_processor.py - CLI tool for processing nginx/error logs.

Supports sorting, deduplication, frequency counting, top-N/bottom-N output,
regex-based filtering, multi-line log entry grouping, normalization, and
processing statistics.
"""

import argparse
import collections
import re
import sys
import time
from pathlib import Path


# Nginx error lines start with a timestamp like "2026/08/18 11:41:22 [error] ..."
LOG_START_RE = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}")

# Normalization patterns (applied in order)
NORMALIZATION_PATTERNS = [
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<IP>"),
    (re.compile(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}"), "<DATE>"),
    (re.compile(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}"), "<DATE>"),
    (re.compile(r"\b\d+#\d+\b"), "<PID>"),
    (re.compile(r"\*\d+\b"), "<REQ>"),
    (re.compile(r"on line \d+"), "<LINE>"),
    (re.compile(r"in /[^\s]*\.php"), "in <PATH>"),
    (re.compile(r"server: [^,]+"), "server: <HOST>"),
    (re.compile(r"host: \"[^\"]+\""), "host: \"<HOST>\""),
    (re.compile(r"referrer: \"[^\"]+\""), "referrer: \"<REF>\""),
    (re.compile(r"request: \"[^\"]+\""), "request: \"<REQUEST>\""),
    (re.compile(r"upstream: \"[^\"]+\""), "upstream: \"<UPSTREAM>\""),
    (re.compile(r"client: <IP>"), "client: <IP>"),
]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Process log files: sort, deduplicate, count, search, normalize, stats."
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
    parser.add_argument(
        "-t",
        "--top",
        type=int,
        metavar="N",
        help="When using --count, show only the top N most frequent entries",
    )
    parser.add_argument(
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
    parser.add_argument(
        "-n",
        "--normalize",
        action="store_true",
        help="Mask variable parts (IPs, dates, paths, line numbers, hosts, etc.) for super-unique grouping",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display processing statistics at the end",
    )
    return parser.parse_args(argv)


def compile_search(pattern):
    """Compile a regex pattern, raising a clean error on invalid input."""
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex pattern: {exc}") from exc


def normalize_entry(entry):
    """Mask variable parts of a log entry to improve grouping."""
    for pattern, replacement in NORMALIZATION_PATTERNS:
        entry = pattern.sub(replacement, entry)
    return entry


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
    normalize=False,
):
    """Process a log file according to the requested options."""
    compiled = None
    if search is not None:
        compiled = compile_search(search)

    stats = {
        "total_read": 0,
        "matched": 0,
        "normalized": 0,
        "output": 0,
        "start_time": time.perf_counter(),
    }

    entries = read_entries(log_file_path)

    for entry in entries:
        stats["total_read"] += 1
        if compiled is not None and not compiled.search(entry):
            continue
        stats["matched"] += 1
        if normalize:
            original = entry
            entry = normalize_entry(entry)
            if entry != original:
                stats["normalized"] += 1
        yield entry, stats

    stats["elapsed"] = time.perf_counter() - stats["start_time"]


def collect_and_format(
    entries_iter,
    sort=False,
    unique=False,
    count=False,
    top=None,
    bottom=None,
):
    """Collect generator entries and apply sort/unique/count/top/bottom."""
    entries = []
    stats = None
    for entry, stats in entries_iter:
        entries.append(entry)

    if sort:
        entries = sorted(entries)

    if unique:
        if sort:
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
        counted = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        if top is not None and bottom is not None:
            print(
                "Warning: --top and --bottom cannot both be used; ignoring --bottom",
                file=sys.stderr,
            )
            bottom = None
        if top is not None:
            if top < 0:
                print("Warning: --top value must be non-negative; ignoring", file=sys.stderr)
            else:
                counted = counted[:top]
        if bottom is not None:
            if bottom < 0:
                print("Warning: --bottom value must be non-negative; ignoring", file=sys.stderr)
            else:
                counted = counted[-bottom:]
        stats["output"] = len(counted)
        return counted, stats

    if top is not None and not count:
        print(
            "Warning: --top is only meaningful with --count; ignoring --top",
            file=sys.stderr,
        )
    if bottom is not None and not count:
        print(
            "Warning: --bottom is only meaningful with --count; ignoring --bottom",
            file=sys.stderr,
        )

    stats["output"] = len(entries)
    return entries, stats


def format_counted(items):
    """Format counted entries with right-aligned counts in an 8-char field."""
    formatted = []
    for entry, count in items:
        lines = entry.split("\n")
        formatted.append(f"{count:>8}    {lines[0]}")
        for continuation in lines[1:]:
            formatted.append(f"{'':>8}    {continuation}")
    return formatted


def format_stats(stats):
    """Format processing statistics for display."""
    lines = []
    lines.append("--- stats ---")
    lines.append(f"Total entries read:     {stats['total_read']}")
    lines.append(f"Entries after search:   {stats['matched']}")
    lines.append(f"Entries normalized:     {stats['normalized']}")
    lines.append(f"Output entries:         {stats['output']}")
    lines.append(f"Elapsed time:           {stats['elapsed']:.4f}s")
    return lines


def main(argv=None):
    args = parse_args(argv)

    entries_iter = process_log(
        args.log_file_path,
        sort=args.sort,
        unique=args.unique,
        count=args.count,
        top=args.top,
        bottom=args.bottom,
        search=args.search,
        normalize=args.normalize,
    )

    result, stats = collect_and_format(
        entries_iter,
        sort=args.sort,
        unique=args.unique,
        count=args.count,
        top=args.top,
        bottom=args.bottom,
    )

    if not result:
        if args.stats:
            print("\n".join(format_stats(stats)))
        return

    if args.count:
        output = format_counted(result)
    else:
        output = result

    print("\n".join(output))

    if args.stats:
        print("\n" + "\n".join(format_stats(stats)))


if __name__ == "__main__":
    main()
