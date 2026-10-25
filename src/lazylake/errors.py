"""Extracts the meaningful error from a Spark / Glue log.

A failed Glue log is often thousands of lines long, 95% of it noise
(INFO, WARN, Spark-internal stack traces). This module isolates the lines that
actually explain the problem: the main exception and its "Caused by" chain.
"""

from __future__ import annotations

import re

ERROR_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"\b[\w.]+(Exception|Error)\b[:\s]"),
    re.compile(r"^\s*Caused by:"),
    re.compile(r"\bERROR\b"),
    re.compile(r"AnalysisException|Py4JJavaError|FileNotFoundException|AccessDenied"),
]

# Spark/Hadoop-internal Java stack frames: hidden, they don't help.
NOISE = re.compile(r"^\s*at (org\.apache\.|scala\.|java\.|sun\.|py4j\.|com\.amazonaws\.)")


def extract_error(lines: list[str], context: int = 3, max_lines: int = 40) -> list[str]:
    """Returns the relevant error lines, with a little context around them.

    - context: number of lines kept after each error line
    - max_lines: output is truncated to stay readable in a terminal
    """
    keep: set[int] = set()
    for i, line in enumerate(lines):
        if any(p.search(line) for p in ERROR_PATTERNS):
            for j in range(i, min(i + context + 1, len(lines))):
                if not NOISE.match(lines[j]):
                    keep.add(j)

    result: list[str] = []
    previous = -2
    for i in sorted(keep):
        if i != previous + 1 and result:
            result.append("…")
        result.append(lines[i].rstrip())
        previous = i

    if len(result) > max_lines:
        result = result[:max_lines] + [f"… ({len(result) - max_lines} more lines, press f for the full log)"]
    return result
