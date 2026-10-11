# agents-md-runbook

Turn an AGENTS.md-style runbook from prose into a machine-checkable checklist. Lint it for the three properties agents need — numbered steps, explicit shell command blocks, and idempotency/verify markers — and track progress in a sidecar state file. If your agents follow written setup runbooks, this makes "did the runbook actually get followed" answerable; if your runbooks are one-liners, a checklist is overkill.

<p align="center"><img src="docs/demo.gif" alt="demo" width="720"></p>

## Problem

The best local-first projects ship an `AGENTS.md` that reads like an executable script: numbered steps, exact commands, verifiable outcomes — installation documentation written so an agent can follow it. That pattern is powerful but unguarded: nothing stops a runbook from drifting into prose, missing commands, or steps with no observable success check. An agent mid-runbook after a crash has no idea which steps it already did.

The overlooked angle: a runbook is software. It deserves a linter and a progress state — not faith.

## How it works

- **Parser**: `## Step N: Title` headings become structured steps; fenced code blocks become commands (shell dialects only); `- idempotent: yes|no` and `- verify: <observable check>` metadata lines attach to their step.
- **Linter** (`runbook lint`): flags missing command blocks, non-shell code languages, duplicate or non-increasing step numbers, missing/invalid idempotency markers, missing or empty verify lines, over-long titles. Metadata is checked even when the command block is absent — a step can fail lint in multiple independent ways.
- **Progress state** (`runbook next` / `done N`): a `<file>.state.json` sidecar records completed step numbers; `next` always prints the first incomplete step with its verify hint, so a restarted agent resumes exactly where it stopped.

Quickstart (~5 min):

```bash
# 1. Self-test (~3 s)
python self_test.py

# 2. Lint your runbook (~1 s)
python runbook.py lint AGENTS.md
# -> 6 steps, 0 issues   (or a list of ISSUE lines)

# 3. Execute with progress tracking (as long as the runbook takes)
python runbook.py next AGENTS.md        # first incomplete step + verify hint
python runbook.py done AGENTS.md 1      # after confirming step 1 worked
python runbook.py next AGENTS.md        # resumes at step 2
```

## Why not X

| Alternative | Why not |
|---|---|
| Just markdown + human review | Humans skim; the whole point is that agents execute verbatim. A linter catches drift mechanically on every edit. |
| Makefile / justfile | Great for commands, but no idempotency markers, no verify semantics, and target syntax is hostile to step prose. Different tool for a different job. |
| Notebooks (Jupyter) | Executable, but state lives in kernel memory and ordering discipline is weak; runbook + state file is diff-able text an agent can follow from cold. |
| CI pipelines | Only run in CI; local-first setup ("install this on my machine") needs something the agent runs interactively, checkpoint by checkpoint. |

## Minimal Fallback

No Python? Keep the discipline, drop the tool:

- Require three things per step in plain markdown: a numbered heading, exactly one shell block, and a sentence starting with "Verify:". Then `grep -c '^## Step' AGENTS.md` for completeness and eyeball the rest.
- For progress: a plain `done.txt` with one step number per line — `sort -n` it and compare against `grep -o '^## Step [0-9]*'`.

## Design Trade-offs

Priorities: **correctness of the gate > simplicity > expressiveness > coverage.**

- Lint is conservative: a step without a command block is an issue even if the step is genuinely informational. Split such steps out of the runbook instead of weakening the rule.
- Progress state is a sidecar file, not in-document checkboxes: documents stay clean and diff-able; state is disposable and rebuildable.
- Shell dialects only (`bash`/`sh`/`shell`): the tool refuses to bless Python/JS blocks as "commands" because it never executes anything — it checks structure, so execution semantics must stay in the caller's hands.

## Limits & Second-order Effects

- The linter checks structure, not semantics: `idempotent: yes` is an author's claim, and `verify:` is only as good as the check it names. A linted runbook can still be wrong.
- Second-order effect: once runbooks carry state, teams may **skip verify steps under time pressure** and mark them done anyway — the tool cannot see that. Pair `done` with the verify output pasted into a log if this becomes a habit.
- Widespread adoption may push authors to write runbooks *for the linter* (gaming the markers) rather than for the executing agent. The verify line is the anti-gaming anchor: keep it observable and specific.

## FAQ

**Does it execute the commands?**
No — deliberately. It parses, lints, and tracks. Execution belongs to the agent (or you), with the verify line as the checkpoint contract.

**When should you NOT use this tool?**
One-step or two-step setups (a checklist adds ceremony without value), and runbooks whose steps are inherently non-idempotent one-time actions with no observable check — lint will fight you, correctly, but you will both lose.

**Why a sidecar state file instead of checkboxes in the markdown?**
Checkbox edits create noisy diffs and merge conflicts in the very document you want stable. State is per-machine and disposable.

## Core Assumptions

1. Runbooks worth tracking are executed by an agent or human step-by-step, top to bottom, with possible interruptions.
2. A step's success has at least one *observable* check — steps that cannot be verified should not be in a runbook at all.
3. Markdown structure (`## Step N:` + fenced blocks) is a stable enough convention to lint against; exotic formatting is out of scope.
4. One machine, one active executor per runbook state file (no concurrent `done` writes).

Confidence: **High** that lint + state tracking catches the most common runbook failure modes (all six lint classes are covered by tests that reproduce them — run `python self_test.py`). Confidence: **Medium** that the idempotency marker improves real-world rerun safety — it forces authors to think, but the marker itself is unverifiable [estimated].

Parser constants (title limit, accepted dialects) current **as of 2026-10-11**.

Source inspiration (structural restatement only): https://github.com/HelixDB/helix-foundry — local-first workspaces whose README runbooks are written for agent execution.

License: MIT. Contact: hcac4735@agent.qq.com
