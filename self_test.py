#!/usr/bin/env python3
"""Self-test for agents-md-runbook (ALIGNMENT rule 97 three families).

Run:  python self_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runbook as rb  # noqa: E402

GOOD = """# Setup runbook

Intro text that should be ignored.

## Step 1: install toolchain
- idempotent: yes
- verify: `tool --version` prints 1.x

```bash
tool --install
```

## Step 2: write config
- idempotent: no
- verify: config file exists and parses

```bash
echo "{}" > config.json
```
"""

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


def write(tmp, name, text):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


# ------------------------------------------------------------- functional ---
def test_functional(tmp):
    steps = rb.parse_runbook(GOOD)
    record("functional: parses 2 steps with numbers 1,2",
           [s.number for s in steps] == [1, 2])
    record("functional: command + lang captured",
           steps[0].command == "tool --install" and steps[0].command_lang == "bash")
    record("functional: metadata captured",
           steps[1].idempotent == "no" and steps[1].verify.startswith("config file"))
    record("functional: lint clean on good runbook", rb.lint(steps) == [])

    path = write(tmp, "good.md", GOOD)
    state = rb.load_state(path)
    rb.mark_done(path, steps, 1)
    s = rb.next_step(steps, rb.load_state(path))
    record("functional: after done(1), next is 2", s and s.number == 2)
    rb.mark_done(path, steps, 2)
    record("functional: all done -> None",
           rb.next_step(steps, rb.load_state(path)) is None)


# ----------------------------------------------------------- error paths ---
def test_errors(tmp):
    bad = """## Step 1: missing things
```python
print("not a shell")
```
## Step 1: duplicate number
- idempotent: maybe
## Step 0: backwards number
"""
    issues = rb.lint(rb.parse_runbook(bad))
    joined = " | ".join(issues)
    record("error: lint catches missing command", "no command code block" in joined)
    record("error: lint catches non-shell lang", "not a shell dialect" in joined)
    record("error: lint catches duplicate number", "duplicate step number" in joined)
    record("error: lint catches bad idempotent", "must be yes|no" in joined)
    record("error: lint catches missing verify", "missing '- verify" in joined)
    record("error: lint catches non-increasing numbers", "not increasing" in joined)

    path = write(tmp, "bad.md", bad)
    try:
        rb.mark_done(path, rb.parse_runbook(bad), 99)
        record("error: mark_done unknown step raises", False)
    except rb.RunbookError:
        record("error: mark_done unknown step raises", True)

    # Corrupted state file
    path2 = write(tmp, "corrupt.md", GOOD)
    with open(path2 + ".state.json", "w", encoding="utf-8") as fh:
        fh.write('{"done": "not-a-list"}')
    try:
        rb.load_state(path2)
        record("error: corrupted state raises", False)
    except rb.RunbookError:
        record("error: corrupted state raises", True)


# ------------------------------------------------------------ edge cases ---
def test_edges(tmp):
    record("edge: empty runbook -> [] and lint issue",
           rb.parse_runbook("") == [] and
           len(rb.lint(rb.parse_runbook(""))) == 1)

    long_title = "x" * 300
    long = f"## Step 1: {long_title}\n- idempotent: yes\n- verify: ok\n```bash\necho hi\n```\n"
    issues = rb.lint(rb.parse_runbook(long))
    record("edge: 300-char title flagged", any("longer than" in i for i in issues))

    no_fences = "## Step 1: a\n## Step 2: b\n"
    steps = rb.parse_runbook(no_fences)
    record("edge: steps without commands lint as issues",
           all(s.command is None for s in steps) and len(rb.lint(steps)) >= 2)

    weird = "## Step 1: ```\ncode\n```\n"  # fence marker inside title
    steps_w = rb.parse_runbook(weird)
    record("edge: backticks in title do not break parsing",
           len(steps_w) == 1 and "```" in steps_w[0].title)

    crlf = GOOD.replace("\n", "\r\n")
    steps_c = rb.parse_runbook(crlf)
    record("edge: CRLF line endings parse",
           len(steps_c) == 2 and steps_c[0].command == "tool --install")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        test_functional(tmp)
        test_errors(tmp)
        test_edges(tmp)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
