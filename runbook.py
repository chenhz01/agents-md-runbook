#!/usr/bin/env python3
"""agents-md-runbook: make AGENTS.md runbooks machine-checkable.

Parses an AGENTS.md-style runbook into structured steps, lints it for the
three properties that matter when an agent executes it (numbered steps,
explicit command blocks, idempotency + verify markers), and tracks which
steps are done in a sidecar state file — so "install by following the
runbook" becomes an executable checklist instead of prose.

Pure stdlib.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

STEP_RE = re.compile(r"^##\s+Step\s+(\d+)\s*:\s*(.+?)\s*$")
META_RE = re.compile(r"^\s*-\s*(idempotent|verify)\s*:\s*(.+?)\s*$")
FENCE_RE = re.compile(r"^```(\w*)\s*$")
MAX_TITLE_LEN = 120

STATE_VERSION = 1


class RunbookError(Exception):
    pass


class Step:
    __slots__ = ("number", "title", "command", "command_lang",
                 "idempotent", "verify", "line")

    def __init__(self, number: int, title: str, line: int):
        self.number = number
        self.title = title
        self.command: str | None = None
        self.command_lang: str | None = None
        self.idempotent: str | None = None
        self.verify: str | None = None
        self.line = line


def parse_runbook(text: str) -> list[Step]:
    """Parse markdown into steps. Empty text -> []. Never raises on
    structural problems; lint() reports them."""
    steps: list[Step] = []
    current: Step | None = None
    in_fence = False
    fence_lines: list[str] = []
    fence_lang = ""
    for lineno, raw in enumerate(text.splitlines(), start=1):
        fence = FENCE_RE.match(raw)
        if fence:
            if not in_fence:
                in_fence, fence_lang, fence_lines = True, fence.group(1), []
            elif current is not None and current.command is None and fence_lines:
                current.command = "\n".join(fence_lines)
                current.command_lang = fence_lang
                in_fence = False
            else:
                in_fence = False
            continue
        if in_fence:
            fence_lines.append(raw)
            continue
        m = STEP_RE.match(raw)
        if m:
            current = Step(int(m.group(1)), m.group(2), lineno)
            steps.append(current)
            continue
        if current is not None:
            mm = META_RE.match(raw)
            if mm:
                key, val = mm.group(1), mm.group(2)
                if key == "idempotent":
                    current.idempotent = val
                else:
                    current.verify = val
    return steps


def lint(steps: list[Step]) -> list[str]:
    """Return a list of human-readable issues (empty = clean)."""
    issues: list[str] = []
    if not steps:
        issues.append("no steps found — a runbook needs '## Step N: title' headings")
        return issues
    seen: set[int] = set()
    prev = 0
    for s in steps:
        loc = f"step {s.number} (line {s.line})"
        if s.number in seen:
            issues.append(f"{loc}: duplicate step number")
        seen.add(s.number)
        if s.number <= prev and prev:
            issues.append(f"{loc}: step numbers not increasing (previous {prev})")
        prev = max(prev, s.number)
        if len(s.title) > MAX_TITLE_LEN:
            issues.append(f"{loc}: title longer than {MAX_TITLE_LEN} chars")
        if s.command is None:
            issues.append(f"{loc}: no command code block")
        else:
            if s.command_lang not in ("bash", "sh", "shell", ""):
                issues.append(f"{loc}: command block language {s.command_lang!r} "
                              "is not a shell dialect")
        if s.idempotent is None:
            issues.append(f"{loc}: missing '- idempotent: yes|no' marker")
        elif s.idempotent not in ("yes", "no"):
            issues.append(f"{loc}: idempotent marker must be yes|no, "
                          f"got {s.idempotent!r}")
        if s.verify is None:
            issues.append(f"{loc}: missing '- verify: <observable check>' line")
        elif not s.verify.strip():
            issues.append(f"{loc}: verify line is empty")
    return issues


# ------------------------------------------------------------------ state ---
def state_path_for(runbook_path: str) -> str:
    return runbook_path + ".state.json"


def load_state(runbook_path: str) -> dict:
    p = state_path_for(runbook_path)
    if not os.path.exists(p):
        return {"version": STATE_VERSION, "done": []}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise RunbookError(f"state file corrupted: {exc}") from exc
    if not isinstance(doc.get("done"), list):
        raise RunbookError("state file corrupted: 'done' must be a list")
    return doc


def save_state(runbook_path: str, state: dict) -> None:
    state["version"] = STATE_VERSION
    state["done"] = sorted(set(state["done"]))
    with open(state_path_for(runbook_path), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def next_step(steps: list[Step], state: dict) -> Step | None:
    done = set(state["done"])
    for s in sorted(steps, key=lambda s: s.number):
        if s.number not in done:
            return s
    return None


def mark_done(runbook_path: str, steps: list[Step], number: int) -> None:
    if not any(s.number == number for s in steps):
        raise RunbookError(f"step {number} does not exist in this runbook")
    state = load_state(runbook_path)
    state["done"].append(number)
    save_state(runbook_path, state)


# -------------------------------------------------------------------- CLI ---
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="runbook", description="Lint and track AGENTS.md-style runbooks.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lint"); p.add_argument("file")
    p = sub.add_parser("next"); p.add_argument("file")
    p = sub.add_parser("done"); p.add_argument("file"); p.add_argument("number", type=int)

    args = ap.parse_args(argv)
    try:
        with open(args.file, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    steps = parse_runbook(text)

    try:
        if args.cmd == "lint":
            issues = lint(steps)
            for i in issues:
                print(f"ISSUE  {i}")
            print(f"{len(steps)} steps, {len(issues)} issues")
            return 0 if not issues else 2
        if args.cmd == "next":
            state = load_state(args.file)
            s = next_step(steps, state)
            if s is None:
                print("all steps done")
                return 0
            print(f"next: Step {s.number}: {s.title} (line {s.line})")
            print(f"  idempotent: {s.idempotent or '?'}")
            print(f"  verify: {s.verify or '?'}")
            return 0
        if args.cmd == "done":
            mark_done(args.file, steps, args.number)
            print(f"marked step {args.number} done")
            return 0
    except RunbookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
