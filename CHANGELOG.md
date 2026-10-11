# Changelog

## v0.1.1 — 2026-10-11 (self-review revision, iteration 2)

### Fixed
- **Lint blind spot**: idempotency and verify checks were nested inside the
  "has command block" branch, so a step with metadata but no command was only
  reported once (missing command) and its invalid `idempotent: maybe` marker
  went unreported. Checks are now independent — one malformed step can (and
  should) fail lint in multiple ways. Caught by round-2 self-review when the
  "bad idempotent" test failed against v0.1.0.

### Improved (correctness dimension)
- Test count 19 total; added explicit coverage that metadata checks fire
  independently of command presence (the failing case above is now PASS).
- README: Minimal Fallback rewritten to be fully tool-free (grep/sort one-liners);
  added the "runbooks written for the linter" second-order effect.

## v0.1.0 — 2026-10-11 (initial draft)

- Parser: `## Step N: title` headings, fenced command blocks (shell dialects),
  `- idempotent:` / `- verify:` metadata lines.
- Linter: 6 issue classes (missing command, non-shell lang, duplicate/non-
  increasing numbers, invalid idempotent marker, missing/empty verify, long titles).
- Progress tracking: `<file>.state.json` sidecar with `next` / `done N`.
- CLI: lint / next / done (argparse).
- `self_test.py`: 19 tests across functional / error-path / extreme-edge
  (empty runbook, 300-char title, backticks in title, CRLF endings) — 18/19 on
  first run, exposing the nested-check bug fixed in v0.1.1.
- README, LICENSE (MIT), initial alignment audit.
