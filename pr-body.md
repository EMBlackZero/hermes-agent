## What does this PR do?

Desktop only polled `process.list` after a background row already existed. A job started through another gateway process (for example Telegram while Desktop was open) wrote to the shared process checkpoint but emitted no event to the Desktop gateway, so the first row was never discovered.

This change makes peer-gateway background work discoverable without exposing processes from unrelated conversations. It also preserves the existing dead-runtime polling guard.

## Related Issue

Related to #48339. This addresses the separate cross-gateway discovery/session-lineage path and keeps process rows owner-scoped.

## Type of Change

- [x] 🐛 Bug fix (non-breaking change that fixes an issue)
- [x] ✅ Tests (adding or improving test coverage)

## Changes Made

- Persist a redacted rolling output tail in the shared process checkpoint and import live peer-owned processes after PID/start-time validation.
- Resolve `process.list`/`process.kill` through a durable conversation scope when a messaging runtime is no longer mounted.
- Match ownership by routing key, durable owner task, or parent session while keeping unrelated conversations isolated.
- Poll mounted Desktop sessions at a slow idle cadence so a later external process is discovered; retain fast liveness polling for visible running rows.
- Keep the dead-runtime latch, timer cleanup, and single-timer behavior covered by renderer tests.

## How to Test

1. Open a Desktop conversation and leave its Background stack empty.
2. Start `terminal(background=true, notify=true)` for the same conversation through Telegram or another gateway process.
3. Confirm the Desktop row appears without remounting and shows the redacted live output tail; confirm another conversation cannot list or stop it.

Automated coverage:

- New Python checkpoint/scope tests: 9 passed.
- Existing process registry suite on Windows: 71 passed, 6 pre-existing platform failures, 30 skipped; the same 6 failures reproduce on clean upstream `main`.
- Desktop targeted tests: 27 passed.
- Desktop TypeScript typecheck: passed.
- Touched-file ESLint: passed.

## Checklist

### Code

- [x] I've read the Contributing Guide
- [x] My commit messages follow Conventional Commits
- [x] I searched open and closed PRs/issues for duplicates
- [x] My PR contains only changes related to this fix
- [x] I've added tests for the bug
- [x] I've tested on Windows 11

### Documentation & Housekeeping

- [x] Documentation update: N/A
- [x] Config example update: N/A
- [x] CONTRIBUTING/AGENTS update: N/A
- [x] Cross-platform impact considered
- [x] Tool schema update: N/A

## Screenshots / Logs

Focused automated test results are listed above. A real Desktop/Telegram cross-gateway probe will be attached if available.
