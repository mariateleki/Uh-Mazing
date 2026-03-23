#!/usr/bin/env python3
"""Print bracketed constituency trees using NLTK pretty_print()."""

import argparse
import sys

from nltk.tree import Tree


def read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _find_matching_paren(text: str, start: int) -> int:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def normalize_tree_string(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("("):
        return stripped

    second = 1
    while second < len(stripped) and stripped[second].isspace():
        second += 1
    if second >= len(stripped) or stripped[second] != "(":
        return stripped

    end = _find_matching_paren(stripped, 0)
    if end == len(stripped) - 1:
        return stripped[1:end].strip()
    return stripped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print bracketed parse trees using NLTK."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input file path. Defaults to stdin.",
    )
    args = parser.parse_args()

    tree_text = normalize_tree_string(read_input(args.input))
    if not tree_text:
        print("No tree found in input.", file=sys.stderr)
        return 1

    tree = Tree.fromstring(tree_text)
    print(tree)
    tree.pretty_print()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImportError:
        print("Missing dependency: nltk. Install with: pip install nltk", file=sys.stderr)
        raise SystemExit(3)
    except ValueError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        raise SystemExit(2)
