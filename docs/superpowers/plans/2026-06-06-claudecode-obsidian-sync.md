# Scheduled Claude Code → Obsidian Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the existing `convert_jsonl.py` converter automatically every 6 hours (four fixed daily slots) via a macOS LaunchAgent, so new Claude Code sessions are archived into `~/ObsidianVault/Chats/ClaudeCode/` without manual runs.

**Architecture:** A thin Bash wrapper (`run_sync.sh`) invokes the existing, idempotent Python converter and writes status/errors to the existing `_logs/` files. A user LaunchAgent plist fires the wrapper at 01:00, 07:00, 13:00, 19:00 local time. No LLM/agent is involved at run time, so scheduled runs do not create new transcripts that would re-import as noise.

**Tech Stack:** macOS `launchd` (LaunchAgent plist), Bash, system `/usr/bin/python3` (3.9.6), existing `convert_jsonl.py`.

---

## Environment facts (verified 2026-06-06)

- Python: `/usr/bin/python3` → Python 3.9.6 (handles the converter's `from __future__ import annotations` typing fine).
- User id: `501` → launchd domain target is `gui/501`.
- `~/Library/LaunchAgents/` exists.
- Converter: `/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/convert_jsonl.py` (idempotent; flags `--quiet`, `--force`).
- Logs already exist: `/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_logs/sync.log` and `sync.err.log`.

## File Structure

- Create: `/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh` — wrapper; sole responsibility is "run the converter and log a start/finish line".
- Create: `~/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist` — schedule definition.
- Touch (no edit): `convert_jsonl.py`, `_logs/sync.log`, `_logs/sync.err.log`.

---

## Task 1: Create the wrapper script

**Files:**
- Create: `/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh`

- [ ] **Step 1: Write the wrapper script**

Write exactly this content to `/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh`:

```bash
#!/bin/bash
# run_sync.sh — run the Claude Code → Obsidian converter (scheduled or manual).
# Manual run and launchd run behave identically; all output goes to _logs/.
set -u

SCRIPT_DIR="/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts"
LOG_DIR="/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_logs"
PYTHON="/usr/bin/python3"

mkdir -p "$LOG_DIR"
ts() { date "+%Y-%m-%dT%H:%M:%S%z"; }

echo "[$(ts)] run_sync start" >> "$LOG_DIR/sync.log"
"$PYTHON" "$SCRIPT_DIR/convert_jsonl.py" --quiet \
    >> "$LOG_DIR/sync.log" 2>> "$LOG_DIR/sync.err.log"
rc=$?
echo "[$(ts)] run_sync finish rc=$rc" >> "$LOG_DIR/sync.log"
exit "$rc"
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh`
Expected: no output, exit 0.

- [ ] **Step 3: Syntax-check the wrapper**

Run: `bash -n /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh`
Expected: no output, exit 0 (no syntax errors).

---

## Task 2: Verify the converter and wrapper run correctly (idempotency)

**Files:**
- Touch: `convert_jsonl.py`, `_logs/sync.log`, `_logs/sync.err.log`

- [ ] **Step 1: Syntax-check the converter**

Run: `/usr/bin/python3 -m py_compile /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/convert_jsonl.py`
Expected: no output, exit 0.

- [ ] **Step 2: Count notes before first run**

Run: `ls /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/*.md | wc -l`
Expected: a number (e.g. `52`). Record it as N0.

- [ ] **Step 3: First manual run via the wrapper**

Run: `bash /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh; echo "rc=$?"`
Expected: `rc=0`.

- [ ] **Step 4: Confirm log got start/finish lines**

Run: `tail -n 4 /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_logs/sync.log`
Expected: a `run_sync start` line and a `run_sync finish rc=0` line with current timestamps, plus the converter's own `Done. wrote=… skipped=… empty=…` summary line.

- [ ] **Step 5: Count notes after first run**

Run: `ls /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/*.md | wc -l`
Expected: N1 ≥ N0 (any not-yet-imported sessions were added; may equal N0 if already current).

- [ ] **Step 6: Second run proves idempotency**

Run: `bash /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh; ls /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/*.md | wc -l`
Expected: count equals N1 (no new notes written on the second run).

- [ ] **Step 7: Confirm no errors were logged**

Run: `tail -n 5 /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_logs/sync.err.log`
Expected: empty, or only pre-existing content with no new traceback from this run.

---

## Task 3: Create the LaunchAgent plist

**Files:**
- Create: `~/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist`

- [ ] **Step 1: Write the plist**

Write exactly this content to `/Users/llmmkkooii/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.llmmkkooii.claudecode-obsidian-sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/run_sync.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>1</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
    </array>

    <key>RunAtLoad</key>
    <false/>

    <key>ProcessType</key>
    <string>Background</string>

    <key>StandardOutPath</key>
    <string>/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_logs/sync.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_logs/sync.err.log</string>
</dict>
</plist>
```

Note: the wrapper already redirects all converter output to the log files explicitly, so `StandardOutPath`/`StandardErrorPath` here act only as a safety net for launchd-level failures (e.g. bash missing). No output is double-written.

- [ ] **Step 2: Lint the plist**

Run: `plutil -lint /Users/llmmkkooii/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist`
Expected: `… : OK`.

---

## Task 4: Load and smoke-test the LaunchAgent

**Files:** none (launchctl operations only)

- [ ] **Step 1: Bootstrap (load) the agent**

Run: `launchctl bootstrap gui/501 /Users/llmmkkooii/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist`
Expected: no output, exit 0.
If it reports "service already loaded", first run:
`launchctl bootout gui/501/com.llmmkkooii.claudecode-obsidian-sync`
then bootstrap again.

- [ ] **Step 2: Confirm the agent is registered**

Run: `launchctl print gui/501/com.llmmkkooii.claudecode-obsidian-sync | grep -E "state|program|runs" | head`
Expected: shows the service with its program path (`run_sync.sh`); state is `not running` (waiting for next scheduled slot) which is correct.

- [ ] **Step 3: Force one immediate run**

Run: `launchctl kickstart -k gui/501/com.llmmkkooii.claudecode-obsidian-sync; echo "rc=$?"`
Expected: `rc=0`.

- [ ] **Step 4: Confirm the forced run logged**

Run: `tail -n 3 /Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_logs/sync.log`
Expected: a fresh `run_sync start` / `run_sync finish rc=0` pair with a timestamp from the last few seconds.

- [ ] **Step 5: Verify the next scheduled run is set**

Run: `launchctl print gui/501/com.llmmkkooii.claudecode-obsidian-sync | grep -iA4 "next"`
Expected: launchd lists upcoming calendar-interval fire times (the next of 01/07/13/19:00).

---

## Task 5: Document and finalize

**Files:**
- Create: `/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/README.md`

- [ ] **Step 1: Write a short operations README**

Write exactly this content to `/Users/llmmkkooii/ObsidianVault/Chats/ClaudeCode/_scripts/README.md`:

```markdown
# ClaudeCode → Obsidian sync

Converts `~/.claude/projects/**/*.jsonl` Claude Code sessions into Markdown notes
in this folder's parent (`Chats/ClaudeCode/`).

## Pieces
- `convert_jsonl.py` — idempotent converter (skips already-imported session_ids).
- `run_sync.sh` — wrapper used by both manual and scheduled runs; logs to `_logs/`.
- LaunchAgent `~/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist`
  — fires `run_sync.sh` at 01:00, 07:00, 13:00, 19:00 local time.

## Manual run
    bash run_sync.sh        # same behavior as the scheduled run

## Logs
- `_logs/sync.log` — start/finish + converter summary per run
- `_logs/sync.err.log` — errors only

## Manage the schedule
    launchctl print    gui/501/com.llmmkkooii.claudecode-obsidian-sync   # status
    launchctl kickstart -k gui/501/com.llmmkkooii.claudecode-obsidian-sync  # run now
    launchctl bootout  gui/501/com.llmmkkooii.claudecode-obsidian-sync   # disable
    launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.llmmkkooii.claudecode-obsidian-sync.plist  # re-enable
```

- [ ] **Step 2: Final end-to-end confirmation**

Run: `launchctl print gui/501/com.llmmkkooii.claudecode-obsidian-sync >/dev/null && echo LOADED`
Expected: `LOADED`.

- [ ] **Step 3 (optional): Commit the spec, plan, and any repo-tracked artifacts**

Only if the user asks to commit. The scripts/plist live outside this repo (in the
vault and `~/Library`), so a repo commit would cover only `docs/superpowers/`.
If requested:

```bash
git add docs/superpowers/specs/2026-06-06-claudecode-obsidian-sync-design.md \
        docs/superpowers/plans/2026-06-06-claudecode-obsidian-sync.md
git commit -m "docs: add ClaudeCode→Obsidian scheduled-sync spec and plan"
```

---

## Notes for the implementer

- The scripts and plist live **outside** this git repo (in `~/ObsidianVault/` and
  `~/Library/LaunchAgents/`). Do not try to `git add` them.
- If `launchctl bootstrap` errors with code `5` (Input/output) on a re-run, the
  service is already loaded — `bootout` then `bootstrap` again.
- No Full Disk Access grant is needed: both source (`~/.claude`) and destination
  (`~/ObsidianVault`) are under the user's home directory.
- Deferred (not in this plan): `find_existing_session()` is O(n²) across runs; fine at
  ~50 notes, revisit only if the archive reaches thousands.
```
