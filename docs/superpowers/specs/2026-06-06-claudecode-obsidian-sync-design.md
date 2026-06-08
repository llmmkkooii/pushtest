# Scheduled Claude Code → Obsidian Import — Design

- **Date**: 2026-06-06
- **Status**: Approved (ready for implementation plan)
- **Owner**: llmmkkooii

## Problem

Claude Code CLI writes session transcripts as JSONL under `~/.claude/projects/**/*.jsonl`.
An existing converter, `~/ObsidianVault/Chats/ClaudeCode/_scripts/convert_jsonl.py`,
turns those into Markdown notes in `~/ObsidianVault/Chats/ClaudeCode/`. Today it is
run by hand. The goal is to run it automatically a few times per day so new sessions
are archived without manual intervention.

## Scope

In scope:
- Schedule the existing converter to run every 6 hours (4 fixed clock slots/day).
- A thin wrapper script for consistent manual/scheduled invocation and logging.
- A macOS LaunchAgent to drive the schedule.
- Verification steps (idempotency, scheduled-run smoke test).

Out of scope:
- claude.ai web conversations and Claude Desktop "cowork" sessions (different,
  cloud-only sources; not addressed here).
- Rewriting `convert_jsonl.py`'s conversion logic.
- Performance refactor of `find_existing_session()` (flagged below, deferred).

## Source of truth

- **Source**: `~/.claude/projects/**/*.jsonl` (local, written by Claude Code CLI).
- **Converter**: `~/ObsidianVault/Chats/ClaudeCode/_scripts/convert_jsonl.py`
  - Idempotent: skips any session whose `session_id` already appears in an existing
    note's frontmatter.
  - Flags: `--force` (overwrite), `--quiet` (suppress non-error output).
- **Output**: `~/ObsidianVault/Chats/ClaudeCode/YYYYMMDD-HHMMSS-<shortid>-<slug>.md`
- **Logs**: `~/ObsidianVault/Chats/ClaudeCode/_logs/sync.log` and `sync.err.log`
  (both already exist).

## Components

### 1. Wrapper script
`~/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh`

- Resolves a stable `python3` interpreter (absolute path; not reliant on launchd's
  minimal PATH).
- Runs `convert_jsonl.py --quiet`.
- Appends a timestamped start and finish line to `_logs/sync.log`; Python stderr
  flows to `_logs/sync.err.log` via the LaunchAgent redirect.
- Makes a manual run (`bash run_sync.sh`) behave identically to a scheduled run.
- Exits non-zero only on interpreter/script invocation failure (the converter itself
  is non-fatal on bad data).

### 2. LaunchAgent
`~/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist`

- `ProgramArguments`: `/bin/bash <path>/run_sync.sh`.
- `StartCalendarInterval`: four entries at 01:00, 07:00, 13:00, 19:00 (local time).
  Fixed clock slots (not a rolling `StartInterval`) so launchd coalesces runs missed
  during sleep into a single catch-up run on wake, without schedule drift.
- `StandardOutPath` → `_logs/sync.log`; `StandardErrorPath` → `_logs/sync.err.log`.
- `RunAtLoad`: `false` (the four daily slots are sufficient; avoid a run on every login).

## Data flow

```
~/.claude/projects/**/*.jsonl
        │  (launchd fires run_sync.sh every 6h)
        ▼
convert_jsonl.py --quiet      (idempotent; skips known session_id)
        ▼
~/ObsidianVault/Chats/ClaudeCode/<note>.md   (+ append to _logs/sync.log)
```

## Why launchd (not the scheduled-tasks MCP)

- The job is a deterministic local file transform; it needs no LLM.
- The MCP runs a full Claude agent per fire, which itself writes a new transcript into
  `~/.claude/projects/`, which the importer would then convert into a
  "scheduled-task…" note — recurring self-referential noise on every run. The
  ClaudeCode folder already shows this pattern from other MCP scheduled tasks.
- launchd is free, native, survives reboots, and coalesces missed runs.
- Trade-off accepted: the job is not visible in `list_scheduled_tasks`; status is
  observed via the two log files instead.

## Error handling

- `convert_jsonl.py` already swallows malformed JSON lines and empty sessions
  (non-fatal by design).
- launchd surfaces wrapper/interpreter failures via `sync.err.log`.
- No additional alerting (YAGNI for a personal archive job).

## Testing / verification

1. `python3 -m py_compile convert_jsonl.py` — syntax sanity.
2. Manual `bash run_sync.sh`:
   - First run writes new notes for any not-yet-imported sessions.
   - Immediate second run writes nothing (idempotency holds).
   - `_logs/sync.log` gains timestamped entries.
3. `plutil -lint` the plist; `launchctl bootstrap gui/$(id -u) <plist>`.
4. `launchctl kickstart -k gui/$(id -u)/com.llmmkkooii.claudecode-obsidian-sync` to
   force one immediate run; confirm a fresh log entry and expected note output.
5. Confirm `launchctl print` shows the agent loaded with the correct next-run schedule.

## Deferred / known limitations

- **O(n²) existence check**: `find_existing_session()` re-globs and reads every
  existing note for each candidate JSONL on each run. Fine at the current ~50 notes;
  if the archive reaches thousands, replace with a one-time in-memory index of seen
  `session_id`s. Not addressed now.
- Only the four fixed slots are covered; sessions created and the Mac shut down before
  the next slot are imported at the following wake/slot, not instantly.
