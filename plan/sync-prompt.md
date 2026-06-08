# Scheduled-task prompt: weekly PPTX sync

This is the prompt that will be registered with the `scheduled-tasks` MCP. Each run
starts fresh — no memory of any prior conversation. The prompt below is fully
self-contained.

---

## Prompt

You are running as a scheduled task. Today is the current date in JST.

**Goal:** for the rotation group whose week covers today, download every PPTX
file the assigned students have emailed to `hyamada@kuhp.kyoto-u.ac.jp`, then
upload each to the corresponding `ポリクリ<N>班` folder on Kyoto University's
RDM Drive. Report a brief summary. Do not read slide contents.

**Steps:**

1. **Resolve this week's group** by running:
   ```bash
   cd ~/github/pushtest
   python3 scripts/roster.py --date $(date +%Y-%m-%d) --json
   ```
   The output is JSON with `week`, `fiscal_year`, `rdm_folder`, and `students`
   (a list of `{phs, email}`). If the script prints nothing (no active group),
   STOP and report "no rotation group active this week — nothing to do".

2. **Search Gmail** using the Gmail MCP. Build one query OR-ing all student
   emails from step 1, limited to PPTX attachments in the last 7 days:
   ```
   from:(EMAIL1 OR EMAIL2 OR EMAIL3 OR EMAIL4) has:attachment filename:pptx newer_than:7d
   ```
   Use the Gmail MCP's email search and attachment-download tools. Save every
   attachment to `~/github/pushtest/temp/rdm-inbox/Week<N>/` preserving the
   original filename (per user preference: no rename).

3. **Upload to RDM Drive** by running:
   ```bash
   python3 scripts/upload_to_rdm.py \
     --src ~/github/pushtest/temp/rdm-inbox/Week<N>/ \
     --dest-folder "/rd10154_救急部/ポリクリ症例発表/<fiscal_year>/<rdm_folder>/"
   ```
   Substitute `<N>`, `<fiscal_year>`, and `<rdm_folder>` from step 1's JSON.
   The script handles MKCOL, PROPFIND-based idempotency, and PUT.

4. **Build summary** with this exact shape:
   ```
   Week <N> (<start> → <end>) — <fiscal_year>
   Destination: /rd10154_救急部/ポリクリ症例発表/<fiscal_year>/<rdm_folder>/

   Received: <k>/<n> students
     ✓ <phs1>  — <filename> (<size> bytes)
     ✓ <phs2>  — <filename> (<size> bytes)
     ✗ <phs3>  — no PPTX found in the last 7 days
     ✗ <phs4>  — upload failed: HTTP <code>

   Action items: <none | "follow up with: phs3, phs4">
   ```

5. **Clean up** the local staging folder if all uploads succeeded:
   ```bash
   rm -rf ~/github/pushtest/temp/rdm-inbox/Week<N>/
   ```
   Leave the folder in place if any upload failed (so a manual rerun can pick
   up where this one left off).

**Constraints:**

- Never read or summarise PPTX content. The files are PHI-bearing — you only
  see filenames, sender addresses, sizes, and HTTP status codes.
- If `upload_to_rdm.py` exits with code 3 (auth) or 4 (quota), surface that
  prominently. The user must take manual action.
- If a student appears in the roster but Gmail returns nothing for them, that
  is *not* an error — just record it in the summary as "no PPTX found".
- Do not modify the roster Excel.
- Do not send any reply to students.

**Output:** print only the summary from step 4. No "I will now do X" narration.
