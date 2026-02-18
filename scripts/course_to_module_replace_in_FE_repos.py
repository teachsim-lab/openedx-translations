#!/usr/bin/env python3
"""
Replace course/courses/Course/Courses with module/modules/Module/Modules
in JSON translation files. Never modifies text inside {} (ICU/FormatJS
placeholders and message blocks - {siteName}, {Course Work}, etc.).
"""
import argparse
import json
import sys
from pathlib import Path


REPLACEMENTS = [
    # Order matters: longer forms first to avoid double-replacement
    ("courses", "modules"),
    ("course", "module"),
    ("Courses", "Modules"),
    ("Course", "Module"),
]

# python scripts/course-to-module-replace.py --all-frontend # for all frontend-* folders
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "translations/frontend-app-account/src/i18n/transifex_input.json"


def _find_frontend_transifex_files():
    """Find all transifex_input.json in frontend-* folders (excludes node_modules)."""
    results = []
    for path in (REPO_ROOT / "translations").rglob("transifex_input.json"):
        if "node_modules" in path.parts:
            continue
        if "frontend-" in str(path):
            results.append(path)
    return sorted(results)


def _find_brace_contents(text: str):
    """
    Find all (start, end) ranges of content inside {...}.
    Handles nested braces; treats {{ and }} as escaped (ICU format).
    Returns ranges of the *content* only (between { and }), not including the braces.
    """
    ranges = []
    i = 0
    depth = 0
    content_start = None
    while i < len(text):
        if i < len(text) - 1 and text[i : i + 2] in ("{{", "}}"):
            i += 2
            continue
        if text[i] == "{":
            depth += 1
            if depth == 1:
                content_start = i + 1
            i += 1
            continue
        if text[i] == "}":
            if depth == 1 and content_start is not None:
                ranges.append((content_start, i))
            depth = max(0, depth - 1)
            i += 1
            continue
        i += 1
    return ranges


def replace_in_string(text: str) -> str:
    """Apply course->module replacements, never touching content inside {}."""
    if not isinstance(text, str):
        return text
    ranges = _find_brace_contents(text)
    # Build result by processing only the parts outside {...}
    result = []
    pos = 0
    for start, end in ranges:
        # Process from pos to start (before this block)
        segment = text[pos:start]
        for old, new in REPLACEMENTS:
            segment = segment.replace(old, new)
        result.append(segment)
        # Keep content inside braces unchanged
        result.append(text[start:end])
        pos = end
    # Process the tail after last block
    segment = text[pos:]
    for old, new in REPLACEMENTS:
        segment = segment.replace(old, new)
    result.append(segment)
    return "".join(result)


def replace_in_obj(obj, in_place: bool = True):
    """Recursively replace in JSON-serializable objects. Only modifies string values."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                new_val = replace_in_string(value)
                if new_val != value:
                    obj[key] = new_val
            else:
                replace_in_obj(value, in_place=True)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str):
                new_val = replace_in_string(item)
                if new_val != item:
                    obj[i] = new_val
            else:
                replace_in_obj(item, in_place=True)
    return obj


def main():
    parser = argparse.ArgumentParser(description="Replace course->module in translation JSON")
    parser.add_argument(
        "files",
        nargs="*",
        default=None,
        help="JSON file(s) to process",
    )
    parser.add_argument(
        "--all-frontend",
        action="store_true",
        help="Process all transifex_input.json in translations/frontend-* (excludes node_modules)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print changes without writing",
    )
    args = parser.parse_args()

    if args.all_frontend:
        files = [str(p) for p in _find_frontend_transifex_files()]
    elif args.files:
        files = args.files
    else:
        files = [str(DEFAULT_INPUT)]

    for path_str in files:
        path = Path(path_str)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(1)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        original = json.dumps(data, ensure_ascii=False, indent=2)
        replace_in_obj(data)
        updated = json.dumps(data, ensure_ascii=False, indent=2)

        if original != updated:
            if args.dry_run:
                print(f"[dry-run] Would update {path}")
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(updated)
                print(f"Updated {path}")
        else:
            print(f"No changes in {path}")

        # Copy to messages/en.json (same content as transifex_input.json)
        en_path = path.parent / "messages" / "en.json"
        if args.dry_run:
            print(f"[dry-run] Would write {en_path}")
        else:
            en_path.parent.mkdir(parents=True, exist_ok=True)
            with open(en_path, "w", encoding="utf-8") as f:
                f.write(updated)
            print(f"Wrote {en_path}")


if __name__ == "__main__":
    main()
