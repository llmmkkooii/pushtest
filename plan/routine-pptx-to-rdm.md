# Routine: Weekly student PPTX → RDM Drive

Status: **Live — registered as scheduled-task `sync-pptx-to-rdm`**
Owner: hyamada@kuhp.kyoto-u.ac.jp
Created: 2026-05-21
First scheduled run: 2026-05-22 19:00 JST (Friday)

---

## 1. Goal

Each week, medical students rotating through 初期診療・救急科 email their case-presentation PPTX files to the user's institutional Gmail (`hyamada@kuhp.kyoto-u.ac.jp`). The user currently moves those files by hand into the corresponding `ポリクリ<N>班` folder on Kyoto University's RDM Drive. This routine automates that move.

**Non-goals:**

- Reading or summarising slide contents (PHI stays out of any LLM context window).
- Replying to students.
- Modifying the roster Excel.

---

## 2. Inputs

| Input | Value / Source | Notes |
|---|---|---|
| Roster Excel | `~/Downloads/1．初期診療・救急科_2026年臨床実習学生名簿.xlsx` | Sheet `診療科<評価票>`, headers in row 7. Per-student email is column **J** ("メール"). 班番号 is column **A/B**, 開始日/終了日 are C/D. |
| Gmail account | `hyamada@kuhp.kyoto-u.ac.jp` (institutional) | Read-only access through Gmail MCP. PHI guardrail honored — file bytes never sent to any LLM. |
| RDM Drive account | `yamada.hiroyuki.4a@kyoto-u.ac.jp` | Different account from Gmail. Stored as `RDM_USER` in `.env`. |
| RDM Drive credential | Nextcloud **App Password** (not yet generated) | Stored as `RDM_APP_PASSWORD` in `.env`. **Never** the SPS-ID password. |
| Destination root | `/rd10154_救急部/ポリクリ症例発表/<年度>/ポリクリ<N>班/` | Pre-created in RDM Drive. Existing files are not touched. |

---

## 3. Folder mapping logic

The Excel spans two Japanese academic years. The mapping is:

```
if 開始日 < 2026-04-01:  年度 = "2025年度"   # Groups 1–12
else:                    年度 = "2026年度"   # Groups 13–27
```

Per-week destination:

```
/remote.php/dav/files/<RDM_USER>/rd10154_救急部/ポリクリ症例発表/<年度>/ポリクリ<班番号>班/<filename>
```

Filename convention (proposal — confirm with user before going live):

```
<学籍番号>_<原ファイル名 sanitized>.pptx
```

Rationale: 学籍番号 (column K = PHS) prefix makes files sortable by student even if originals share names like `症例発表.pptx`.

---

## 4. Algorithm (single weekly invocation)

```
1. Load Excel roster (sheet "診療科<評価票>", from row 8).
2. Determine "this week's group":
   target = first row where  開始日 <= TODAY <= 終了日 + grace_days
   grace_days = 3   (PPTs often arrive on the Friday/weekend after rotation ends)
3. Collect (email, 学籍番号) for the 3–4 students in that group.
4. Gmail search (one query, OR over the student emails):
   from:(a@... OR b@... OR c@... OR d@...)
   has:attachment filename:pptx
   newer_than:14d
5. For each matching message:
   a. Download .pptx attachment(s) to /tmp/rdm-inbox/Week<NN>/<学籍番号>/
   b. Verify size > 0 and magic bytes start with PK\x03\x04 (zip → pptx)
6. Resolve destination folder URL.
   MKCOL each ancestor that does not exist (idempotent; ignore 405 "already exists").
7. For each downloaded file: PUT to WebDAV. On 201/204 success, mark done.
   On non-2xx, retry once with exponential backoff (2s, 8s).
8. Build summary:
   Week <NN> (<開始日>-<終了日>):
     received <k>/<n>:
       ✓ 学籍番号 6041  (filename, size)
       ✓ 学籍番号 6043  ...
       ✗ 学籍番号 6044  — no PPTX found in window
   Upload errors: <list or "none">
9. Emit summary as scheduled-task notification AND as a draft email to self.
10. Clean /tmp/rdm-inbox/Week<NN>/ on success.
```

**Idempotency.** If the job is re-run mid-week, it will re-download and overwrite (Nextcloud versioning keeps previous copies). To prevent useless re-uploads, the script also reads back the destination folder via PROPFIND and skips files where the size + last-modified match.

---

## 5. Implementation files

```
~/github/pushtest/
├── plan/
│   └── routine-pptx-to-rdm.md          ← this document
├── scripts/
│   ├── sync_pptx_to_rdm.py             ← main routine (single-file, ~250 lines)
│   ├── roster.py                       ← Excel parsing helpers
│   ├── gmail_fetch.py                  ← Gmail MCP wrapper (search + download attachment)
│   └── rdm_webdav.py                   ← MKCOL / PROPFIND / PUT helpers
├── temp/
│   └── rdm-inbox/                      ← transient .pptx staging, cleaned per run
└── .env                                ← NOT committed; gitignored
```

`.env` shape:

```
RDM_USER=yamada.hiroyuki.4a@kyoto-u.ac.jp
RDM_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx-xxxx
ROSTER_XLSX=/Users/llmmkkooii/Downloads/1．初期診療・救急科_2026年臨床実習学生名簿.xlsx
RDM_BASE_PATH=/rd10154_救急部/ポリクリ症例発表
```

---

## 6. Schedule

- **Cron:** `0 19 * * 5` (every Friday 19:00 JST). Rotation ends Friday, so Friday evening catches the bulk of submissions in the same week.
- **Mechanism:** `scheduled-tasks` MCP. Task ID `sync-pptx-to-rdm`. SKILL.md at `~/.claude/scheduled-tasks/sync-pptx-to-rdm/SKILL.md` — the full prompt is also archived at `plan/sync-prompt.md` in this repo.
- **Constraint:** runs only when Claude Code is open at fire time; otherwise on next launch. Acceptable for this use case since "delivered late" is recoverable.
- **First-run pre-approval:** the user should click "Run now" in the sidebar's Scheduled section once, so Gmail MCP / Bash tool approvals are cached. Otherwise the first scheduled run pauses on prompts.

**Known limitation — late submissions:** if a student submits Sat/Sun after Friday's run, the next Friday's run won't pick it up (it would be searching for the next week's group, not the previous one). Workaround for now: user manually triggers the routine for that prior week. Future enhancement candidate: process current + previous group in one run.

Alternative scheduling: a `launchd` plist for fully OS-level scheduling, independent of Claude Code. Decide after the script proves stable.

---

## 7. Failure modes & responses

| Failure | Detection | Response |
|---|---|---|
| Student didn't send | Gmail search returns < expected count | Note in summary, do not block other students |
| Attachment is not .pptx | Magic-byte check fails | Skip, note in summary |
| RDM quota exceeded | WebDAV returns 507 Insufficient Storage | Halt uploads, surface to user, leave files in /tmp |
| TOTP / App Password revoked | WebDAV returns 401 | Halt, emit clear "regenerate App Password" message |
| Network timeout | `requests` exception | Retry once; on second failure, leave file in /tmp and exit non-zero |
| Excel moved/renamed | FileNotFoundError | Halt with explicit path message |
| Folder doesn't exist in RDM | MKCOL returns 409 (parent missing) | Halt — implies year/班 mismatch; do not silently create unexpected paths |
| Same file uploaded twice | PROPFIND size+mtime match | Skip silently |

---

## 8. Verification plan (before scheduling)

Phase 1 — **read-only dry run:**

```bash
python scripts/sync_pptx_to_rdm.py --dry-run --week 16
```

Prints what would be downloaded and where it would go. No Gmail downloads, no RDM writes.

Phase 2 — **live run, one week:**

```bash
python scripts/sync_pptx_to_rdm.py --week 16
```

User manually inspects RDM Drive to confirm files appear in `ポリクリ16班/`.

Phase 3 — **enable scheduled task:**

Only after Phase 2 succeeds. Register with `scheduled-tasks` MCP.

---

## 9. Security & PHI

- `.env` is gitignored at the repo level. Confirmed: `~/github/pushtest/.gitignore` will add `.env` if missing.
- App Password is scoped to the `claude-routine-pptx` device label so it can be revoked independently of other Nextcloud clients.
- PPTX bytes are written only to local `/tmp/rdm-inbox/` and then to RDM Drive. **Never read into a Claude prompt, never sent to any external API.**
- Summary text passed to the LLM contains only filenames, sender addresses (already on the Excel roster), success/failure flags, and HTTP status codes — no slide contents, no patient identifiers.
- This deliberately diverges from the NotebookLM memory guardrail (which forbids kuhp + LLM ingestion) because no LLM ingestion occurs here. The guardrail's *spirit* — keep PHI out of LLM context — is upheld.

---

## 10. Open questions for user

1. **Filename convention:** OK to use `<学籍番号>_<original>.pptx`, or do you want a different prefix (e.g., 班番号 + 学籍番号, or 名字)?
2. **Submission grace window:** is 14 days back-search enough, or should it be longer (e.g., 21d) to catch late submitters?
3. **Notification preference:** scheduled-task notification only, or also a draft email saved to your Gmail Drafts as a backup record?
4. **App Password:** please generate one at [drive.rdm.kyoto-u.ac.jp](https://drive.rdm.kyoto-u.ac.jp/) → top-right avatar → 設定 (Settings) → セキュリティ (Security) → 「新しいアプリパスワード」 → label `claude-routine-pptx` → copy the generated password into `.env` (do not paste it into chat).

---

## 11. Implementation log (2026-05-21)

1. ☑ Investigate RDM (= Nextcloud) — confirmed via official manual
2. ☑ Draft this plan
3. ☑ User answered design choices: no rename, 7-day grace window, notification-only, all-deletes-manual
4. ☑ User generated App Password (label `claude-routine-pptx`), populated `.env`
5. ☑ Implement `scripts/roster.py` (Excel parser, JSON output)
6. ☑ Implement `scripts/upload_to_rdm.py` (WebDAV MKCOL/PROPFIND/PUT — **no DELETE method by policy**)
7. ☑ Verify auth (HTTP 207 PROPFIND)
8. ☑ Verify path tree end-to-end (`rd10154_救急部 → ポリクリ症例発表 → 2026年度 → ポリクリ16班`)
9. ☑ Live upload test of synthetic 38-byte file (HTTP 201 Created, visually confirmed in Nextcloud UI by user)
10. ☑ Gmail MCP verified — `mcp__gmail3p__search_emails` finds Group 15 student PPTX submissions correctly
11. ☑ Register scheduled task `sync-pptx-to-rdm` (cron `0 19 * * 5`, Friday 19:00 JST)
12. ☐ User pre-approves tools by clicking "Run now" once (recommended)
13. ☐ Monitor first scheduled run (2026-05-22 19:00 JST, Group 16)
14. ☐ User manually deletes `_test_claude_DELETE_ME.pptx` from `ポリクリ16班/` via UI

### Future enhancements

- Process current AND previous group in one run, to catch weekend-late submitters.
- Migrate to `launchd` plist if/when stable, to remove the "Claude Code must be open" constraint.
- Create `2025年度` folder in RDM Drive only if backfilling Groups 1–12 (currently not needed).
