#!/usr/bin/env python3
"""Save an NLTK parse tree as an SVG image (headless alternative to t.draw())."""
# Usage:
#   python scripts/save_tree_image.py <input.txt> <output.svg> [options]
#
# Example:
#   python scripts/save_tree_image.py scripts/sample_tree.txt scripts/output.svg
#
# Options:
#   --font-family  SVG font family (default: "DejaVu Sans Mono")
#   --font-size    Font size in px (default: 12)
#   --x-scale      Horizontal stretch factor (default: 1.0)
#   --all-black    Render all labels in black
#   --italicize-red Italicize leaf labels (red in default NLTK SVG)
#   --bold-labels   Comma-separated labels to bold (default: INTJ,PRN,EDITED)

import argparse
import re
from pathlib import Path

from nltk.tree import Tree
from nltk.tree.prettyprinter import TreePrettyPrinter


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


def apply_font(svg: str, font_family: str, font_size: int) -> str:
    svg = re.sub(r"font-size:\s*\d+px;", f"font-size: {font_size}px;", svg)

    def _add_font_family(match: re.Match[str]) -> str:
        style = match.group(1)
        if "font-family:" in style:
            return match.group(0)
        return f'<text style="{style} font-family: {font_family};"'

    return re.sub(r'<text style="([^"]*)"', _add_font_family, svg)


def apply_text_styling(
    svg: str, all_black: bool, italicize_red: bool, bold_labels: set[str] | None = None
) -> str:
    def _style_text(match: re.Match[str]) -> str:
        full = match.group(0)
        style = match.group(1)
        # Extract the text content that follows the tag
        rest_start = match.end()
        rest = svg[rest_start:]
        # Get the label text between > and </text>
        label_match = re.match(r'[^>]*>([^<]*)', rest)
        label = label_match.group(1).strip() if label_match else ""

        was_red = bool(re.search(r"fill:\s*red\s*;", style))

        if all_black:
            if re.search(r"fill:\s*[^;]+;", style):
                style = re.sub(r"fill:\s*[^;]+;", "fill: black;", style)
            else:
                style = style + " fill: black;"

        if italicize_red and was_red and "font-style:" not in style:
            style = style + " font-style: italic;"

        if bold_labels and label in bold_labels and "font-weight:" not in style:
            style = style + " font-weight: bold;"

        return f'<text style="{style}"'

    return re.sub(r'<text style="([^"]*)"', _style_text, svg)


def stretch_x(svg: str, x_scale: float) -> str:
    if x_scale == 1.0:
        return svg

    def _scale_num(num: str) -> str:
        return f"{float(num) * x_scale:.2f}".rstrip("0").rstrip(".")

    def _scale_viewbox(match: re.Match[str]) -> str:
        values = match.group(1).split()
        if len(values) != 4:
            return match.group(0)
        values[0] = _scale_num(values[0])  # min-x
        values[2] = _scale_num(values[2])  # width
        return f'viewBox="{" ".join(values)}"'

    def _scale_width(match: re.Match[str]) -> str:
        value = float(match.group(1))
        return f'width="{_scale_num(str(value))}em"'

    def _scale_x_attr(match: re.Match[str]) -> str:
        return f'x="{_scale_num(match.group(1))}"'

    def _scale_points(match: re.Match[str]) -> str:
        chunks = match.group(1).split()
        scaled = []
        for chunk in chunks:
            if "," not in chunk:
                scaled.append(chunk)
                continue
            x, y = chunk.split(",", 1)
            scaled.append(f"{_scale_num(x)},{y}")
        return f'points="{" ".join(scaled)}"'

    svg = re.sub(r'viewBox="([^"]+)"', _scale_viewbox, svg, count=1)
    svg = re.sub(r'width="([0-9.]+)em"', _scale_width, svg, count=1)
    svg = re.sub(r'x="([0-9.\-]+)"', _scale_x_attr, svg)
    svg = re.sub(r'points="([^"]+)"', _scale_points, svg)
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Save a bracketed tree as SVG.")
    parser.add_argument("input", help="Path to tree text file")
    parser.add_argument("output", help="Output SVG file path")
    parser.add_argument(
        "--font-family",
        default="Avenir Next",
        help="SVG font family for node labels (default: Avenir Next).",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=14,
        help="SVG font size in pixels (default: 14).",
    )
    parser.add_argument(
        "--x-scale",
        type=float,
        default=1.3,
        help="Horizontal stretch factor for spacing labels (default: 1.3).",
    )
    parser.add_argument(
        "--all-black",
        action="store_true",
        default=True,
        help="Render all text labels in black (default: True).",
    )
    parser.add_argument(
        "--italicize-red",
        action="store_true",
        default=True,
        help="Italicize labels that are red in the default NLTK SVG, typically leaves (default: True).",
    )
    parser.add_argument(
        "--bold-labels",
        default="INTJ,PRN,EDITED",
        help="Comma-separated list of labels to render in bold (default: INTJ,PRN,EDITED).",
    )
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    tree_text = normalize_tree_string(text)
    tree = Tree.fromstring(tree_text)

    svg = TreePrettyPrinter(tree).svg()
    svg = stretch_x(svg, args.x_scale)
    svg = apply_font(svg, args.font_family, args.font_size)
    bold_set = set(args.bold_labels.split(",")) if args.bold_labels else None
    svg = apply_text_styling(svg, all_black=args.all_black, italicize_red=args.italicize_red, bold_labels=bold_set)
    Path(args.output).write_text(svg, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
