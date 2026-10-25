#!/usr/bin/env python3
"""Plan life-science research lanes for a question without the MCP server.

Pass the question as one or more words (quoting is optional) or with --question TEXT;
items are joined with a single space and each item's text is passed unchanged to the
planner, which strips and validates it exactly as the MCP tool does. Prints the JSON plan.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.life_science import plan_life_science_research  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("words", nargs="*", metavar="question", help="question words; items are joined with a single space, text within an item is unchanged")
    parser.add_argument("--question", action="append", default=[], metavar="TEXT", help="alternative spelling of the question; combined with any positional words")
    args = parser.parse_args()
    question = " ".join([*args.question, *args.words])
    if not question.strip() or len(question) > 500:
        parser.error("Question must contain 1 to 500 characters (positional words or --question TEXT)")
    try:
        plan = plan_life_science_research(question)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(plan, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
