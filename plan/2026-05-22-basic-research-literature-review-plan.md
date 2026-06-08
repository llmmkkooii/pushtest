# Basic-Research Literature Review Workflow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a reusable basic-research literature-review workflow in Claude Code by adding a `basic-research` profile to `obsidian-literature-workflow`, bootstrap a `synthetic-torpor-review` Obsidian project, then execute scoping → seed → batch-note → snowball → synthesis to produce a synthesis-ready knowledge base for the «体温管理療法から代謝制御療法へ» narrative review.

**Architecture:** Minimal extension of the existing 47-skill ecosystem — one new markdown profile file under `~/.claude/skills/obsidian-literature-workflow/profiles/`, one new Obsidian-bound project under `~/github/manuscripts/synthetic-torpor-review/`, and a 7-step workflow that composes `research-ideation`, `zotero-obsidian-bridge`, `obsidian-literature-workflow`, `citation-verification`, and `obsidian-synthesis-map`. No new top-level skill is created.

**Tech Stack:** Markdown (skill profile + project notes), Obsidian (vault rendering, `.canvas` files), Zotero (paper management + BibTeX), Claude Code MCP integrations (PubMed, Semantic Scholar, bioRxiv via existing search tools), bash for verification grep checks.

**Spec reference:** [`plan/2026-05-22-basic-research-literature-review-design.md`](2026-05-22-basic-research-literature-review-design.md)

**Open prerequisites from spec §10 (user must answer before Task 3):**
1. Target venue (Japanese journal/book chapter)
2. Word count target
3. Reference count cap
4. Deadline
5. Co-authors (if any)

Tasks 1–2 can proceed without these answers. Task 3 blocks on them.

---

## File Structure

```
~/.claude/skills/obsidian-literature-workflow/
└── profiles/
    └── basic-research.md                 # CREATE (Task 1)

~/github/manuscripts/synthetic-torpor-review/
├── .claude/project-memory/registry.yaml  # CREATE via /obsidian-init (Task 2)
├── CLAUDE.md                             # CREATE (Task 3)
├── Papers/                               # POPULATE (Tasks 6, 7)
├── Knowledge/
│   ├── scoping-candidates.md             # CREATE (Task 4), DELETE after Task 5
│   ├── Literature-Overview.md            # CREATE (Task 8)
│   ├── Method-Families.md                # CREATE (Task 8)
│   └── Research-Gaps.md                  # CREATE (Task 8)
├── Maps/
│   └── literature.canvas                 # CREATE (Task 8)
├── Writing/
│   └── draft-outline.md                  # CREATE (Task 8)
└── refs/
    └── zotero-collection.bib             # EXPORT in Task 5
```

**Files NOT to modify (verified in Task 1 Step 4):**
- `~/.claude/skills/obsidian-literature-workflow/SKILL.md` — must remain bytewise identical.

---

## Task 1: Create the `basic-research` profile

**Files:**
- Create: `~/.claude/skills/obsidian-literature-workflow/profiles/basic-research.md`
- Read (do not modify): `~/.claude/skills/obsidian-literature-workflow/SKILL.md`

- [ ] **Step 1: Capture pre-state hash of the parent skill**

Run:

```bash
shasum -a 256 ~/.claude/skills/obsidian-literature-workflow/SKILL.md \
  > ~/github/pushtest/temp/skill-md.sha256.before
cat ~/github/pushtest/temp/skill-md.sha256.before
```

Expected: a 64-character SHA-256 hash followed by the file path. Note the hash for use in Step 4.

- [ ] **Step 2: Create the `profiles/` directory**

Run:

```bash
mkdir -p ~/.claude/skills/obsidian-literature-workflow/profiles
ls -la ~/.claude/skills/obsidian-literature-workflow/profiles
```

Expected: empty directory exists.

- [ ] **Step 3: Write the profile file**

Create `~/.claude/skills/obsidian-literature-workflow/profiles/basic-research.md` with the exact content:

````markdown
---
name: basic-research-profile
description: Extension profile for obsidian-literature-workflow that adds basic-research-specific fields (experimental system, mechanistic evidence strength, data/reagent availability, translational status) to the canonical paper-note schema. Activated by `literature_profile: basic-research` in a project's CLAUDE.md.
parent_skill: obsidian-literature-workflow
version: 0.1.0
---

# Basic-Research Profile

This profile **extends** the canonical paper-note schema defined in
`obsidian-literature-workflow/SKILL.md`. It does **not** replace any
canonical field.

## Activation

Activated when the current project's CLAUDE.md declares:

```yaml
literature_profile: basic-research
```

## Contract

- This profile only ADDS fields; the canonical six (`Claim`, `Method`,
  `Evidence`, `Limitation`, `Direct relevance to repo`,
  `Relation to other papers`) remain unchanged.
- This profile contains NO project-specific vocabulary. Topic-specific
  fields (e.g., torpor context, AKI subtype, kinase isoform) belong in
  the project-local CLAUDE.md, not here.
- Empty fields are recorded as `n/a`, never omitted. This preserves
  cross-paper diffability.

## Extension fields

The following four sections are inserted between the canonical
`Evidence` and `Limitation` sections of each paper note.

### Experimental System

- Type: [in vivo | in vitro | ex vivo | clinical | computational | review]
- Species/strain:
- Genetic manipulation: [global KO | conditional KO | KD | OE | none]
  - Cre driver / inducible system:
  - Controls: [littermate | non-littermate | wild-type unrelated]
- Cell line / primary culture: (include authentication note if applicable)
- Disease/perturbation model: [induction method, severity]

### Mechanistic Evidence Strength

- Level: [correlative | gain-of-function | loss-of-function | rescue-confirmed | structural/biochemical]
- Direct binding shown: [Y/N — method: IP / ChIP / proximity / cryo-EM / ...]
- Off-target controls reported: [Y/N — note]

Record the **highest level demonstrated**, not the level claimed in the
abstract. Ladder: rescue-confirmed > loss-of-function > gain-of-function
> correlative.

### Data & Reagent Availability

- Public datasets: [GEO / SRA / PRIDE / GenBank accession IDs]
- Key reagents: [Addgene plasmid IDs / antibody catalog#s with validation note]
- Code: [GitHub / Zenodo URL]

Use accession IDs only on the datasets line. URLs go on the reagent line.
Never write a bare "yes" or "no"; always provide the identifier when
present.

### Translational Status

- Stage: [basic only | translational candidate | early human | established clinical]
- Distance to clinical: [one sentence, free-text]

## Constraints on additions to this profile

When future edits add fields here, the same contract applies:
- No project topic vocabulary.
- Additive only; never modify canonical fields.
- Empty values must be representable (`n/a` is the convention).
````

- [ ] **Step 4: Verify the parent skill was not modified**

Run:

```bash
shasum -a 256 ~/.claude/skills/obsidian-literature-workflow/SKILL.md \
  > ~/github/pushtest/temp/skill-md.sha256.after
diff ~/github/pushtest/temp/skill-md.sha256.before \
     ~/github/pushtest/temp/skill-md.sha256.after
```

Expected: zero output (files identical). Any difference is a regression — investigate before continuing.

- [ ] **Step 5: Run the negative-content grep check (spec §6.1)**

Run:

```bash
grep -inE "(torpor|hibernation|TTM|hypothermia|AKI|kidney|nephron|sepsis|p38|MAPK)" \
  ~/.claude/skills/obsidian-literature-workflow/profiles/basic-research.md
echo "exit=$?"
```

Expected: zero matching lines, `exit=1` (grep returns 1 when no match found, which is the desired outcome here). If any line matches, edit the profile to remove the topic-specific term and re-run.

- [ ] **Step 6: Verify the profile is well-formed markdown**

Run:

```bash
wc -l ~/.claude/skills/obsidian-literature-workflow/profiles/basic-research.md
head -6 ~/.claude/skills/obsidian-literature-workflow/profiles/basic-research.md
```

Expected: line count ≥ 50 and ≤ 120; the first 6 lines show the YAML frontmatter with `name`, `description`, `parent_skill`, `version`.

- [ ] **Step 7: Stage but do not commit (per user's commit-only-on-request rule)**

Run:

```bash
cd ~/.claude
git status -- skills/obsidian-literature-workflow/profiles/
```

Expected: shows `profiles/basic-research.md` as untracked. Do not run `git add` or `git commit` unless the user explicitly requests it.

---

## Task 2: Bootstrap the `synthetic-torpor-review` Obsidian project

**Files:**
- Create directory: `~/github/manuscripts/synthetic-torpor-review/`
- Create (via `/obsidian-init`): `~/github/manuscripts/synthetic-torpor-review/.claude/project-memory/registry.yaml`

- [ ] **Step 1: Ensure `~/github/manuscripts/` exists**

Run:

```bash
mkdir -p ~/github/manuscripts
ls -la ~/github/manuscripts
```

Expected: directory exists; may contain previous manuscript projects.

- [ ] **Step 2: Create the project root**

Run:

```bash
mkdir -p ~/github/manuscripts/synthetic-torpor-review/{Papers,Knowledge,Maps,Writing,refs}
cd ~/github/manuscripts/synthetic-torpor-review
git init
ls -la
```

Expected: directories `Papers/`, `Knowledge/`, `Maps/`, `Writing/`, `refs/`, plus an empty `.git/`.

- [ ] **Step 3: Invoke `/obsidian-init` against this project**

In a Claude Code session inside `~/github/manuscripts/synthetic-torpor-review/`, run the slash command:

```
/obsidian-init
```

This invokes `obsidian-project-bootstrap`. Accept prompts to bind the repository.

Expected: `obsidian-project-bootstrap` creates `.claude/project-memory/registry.yaml` and emits a daily note + `00-Hub.md` in the bound Obsidian vault.

- [ ] **Step 4: Verify the registry was created**

Run:

```bash
cat ~/github/manuscripts/synthetic-torpor-review/.claude/project-memory/registry.yaml
```

Expected: YAML showing the project slug, vault path, and binding metadata. If the file is missing, re-run `/obsidian-init` and address any error it reports.

- [ ] **Step 5: Sanity-check skill activation**

Re-enter the project directory in a Claude Code session and confirm that `obsidian-project-memory` activates automatically (it should mention the registry on session start per the `session-start.js` hook).

Expected: session start shows the bound project status.

---

## Task 3: Author the project-local CLAUDE.md

> **Blocks on:** answers to spec §10 (venue, word count, reference count, deadline, co-authors). If any are unknown, write `TBD — answered by <date>` and proceed; revisit before Task 5.

**Files:**
- Create: `~/github/manuscripts/synthetic-torpor-review/CLAUDE.md`

- [ ] **Step 1: Capture the answers to §10**

Record answers (or `TBD — answered by <date>`) for:

- target_venue
- target_word_count
- target_reference_count
- deadline
- co-authors

- [ ] **Step 2: Write the CLAUDE.md**

Create `~/github/manuscripts/synthetic-torpor-review/CLAUDE.md` with:

````markdown
# synthetic-torpor-review — Project Rules

## Deliverable

- Title: 「体温管理療法から代謝制御療法へ」
- Host: 「人工冬眠がもたらす次世代医療に向き合う」 special issue
- target_venue: <FROM STEP 1>
- target_word_count: <FROM STEP 1>
- target_reference_count: <FROM STEP 1>
- deadline: <FROM STEP 1>
- co-authors: <FROM STEP 1>

## Literature Workflow Configuration

```yaml
literature_profile: basic-research        # activates obsidian-literature-workflow/profiles/basic-research.md
review_type: narrative
deliverable_language: ja
citation_style: vancouver
```

## Topic-Specific Override Fields

Each paper note in `Papers/` MUST include the following section
**in addition to** the canonical schema and the basic-research profile
extension fields. These are project-specific and live here (not in the
reusable profile).

```markdown
## Torpor / Hibernation Context
- Setting: [natural hibernator | facultative torpor | synthetic torpor | hypothermia-only | not applicable]
- Metabolic vs thermal emphasis: [metabolic-primary | thermal-primary | mixed]
- Bridge to TTM/TH: [explicit | implicit | none]
```

## Inherited Global Rules

- Active voice.
- "Hospital day 3" — Arabic numerals always.
- Prose numbers: spell out 1–9, numerals ≥10; numerals always for
  measurements, doses, lab values, ages, hospital/ICU days, percentages,
  statistics.
- Japanese synthesis prose: である調.
- Direct paper-note quotes: keep English; do not translate.
- All draft prose passes through `writing-anti-ai` before review.

## Reporting Guideline

Not applicable (narrative review, not SR/RCT/observational). See spec
§1.2 for why PRISMA is out of scope.

## Citation Verification

Every reference cited in `Writing/` MUST have a paper note in `Papers/`
whose bibliographic block has been verified by `citation-verification`
against Semantic Scholar, CrossRef, or arXiv. No exceptions.
````

- [ ] **Step 3: Verify the file parses and references the profile**

Run:

```bash
grep -E "literature_profile|citation_style|deliverable_language" \
  ~/github/manuscripts/synthetic-torpor-review/CLAUDE.md
```

Expected: three matching lines showing `literature_profile: basic-research`, `citation_style: vancouver`, `deliverable_language: ja`.

- [ ] **Step 4: Verify topic override fields are present**

Run:

```bash
grep -A3 "Torpor / Hibernation Context" \
  ~/github/manuscripts/synthetic-torpor-review/CLAUDE.md
```

Expected: shows the three bullet lines (Setting, Metabolic vs thermal emphasis, Bridge to TTM/TH).

---

## Task 4: Scoping search

**Files:**
- Create: `~/github/manuscripts/synthetic-torpor-review/Knowledge/scoping-candidates.md`

- [ ] **Step 1: Activate `research-ideation` in the project context**

In a Claude Code session at `~/github/manuscripts/synthetic-torpor-review/`, ask Claude to invoke the `research-ideation` skill for scoping search of the topic.

- [ ] **Step 2: Run the four planned queries**

Have Claude execute these four queries via MCP search tools (PubMed / Semantic Scholar / bioRxiv) and collect candidate papers:

1. PubMed: `("targeted temperature management" OR "therapeutic hypothermia") AND (review[pt] OR meta-analysis[pt])` — filter last 10 years.
2. PubMed: `("synthetic torpor" OR "induced torpor" OR "Qrfp neurons" OR "Q neurons")`
3. bioRxiv (via Semantic Scholar API or direct): same torpor terms, preprints only.
4. Semantic Scholar: citation expansion (citing + cited) from two seed papers — Hrvatin et al. 2020 *Nature* (Qrfp/torpor) and Takahashi et al. 2020 *Nature* (Q neurons).

- [ ] **Step 3: Write `Knowledge/scoping-candidates.md`**

The file should contain a markdown table with these columns:

| # | Source | Year | First author | Title | DOI/PMID/arXiv | Reason kept |

Aim for ~100 candidates total (across all four queries, deduplicated).

- [ ] **Step 4: Mark obvious off-topic items for removal**

Read the candidate list and add a `Drop / Keep / Review` column. Drop obvious off-topic items (e.g., cryotherapy for sports recovery, food-preservation literature).

- [ ] **Step 5: User review checkpoint**

Hand the candidate list to the user for human review. Do NOT proceed to Task 5 until the user signs off on the kept set.

---

## Task 5: Seed selection (human-led)

**Files:**
- Export: `~/github/manuscripts/synthetic-torpor-review/refs/zotero-collection.bib`

- [ ] **Step 1: User selects 15–25 seed papers**

From the Task 4 candidates marked `Keep`, the user selects 15–25 papers as the seed corpus. Record the selection by editing `Knowledge/scoping-candidates.md` to add a `Seed` column with `Y` for chosen rows.

- [ ] **Step 2: Create the Zotero collection**

In Zotero desktop, create a collection named `synthetic-torpor-review` under the user's main library.

- [ ] **Step 3: Import the seed papers into Zotero**

For each seed paper, use Zotero's "Add Item by Identifier" (DOI/PMID/arXiv ID) to import. Attach PDF when available.

Expected: the collection contains 15–25 items, each with PDF attached where openly available.

- [ ] **Step 4: Export BibTeX**

In Zotero, right-click the `synthetic-torpor-review` collection → Export → BibTeX → save as:

```
~/github/manuscripts/synthetic-torpor-review/refs/zotero-collection.bib
```

- [ ] **Step 5: Verify the export**

Run:

```bash
wc -l ~/github/manuscripts/synthetic-torpor-review/refs/zotero-collection.bib
grep -c "^@" ~/github/manuscripts/synthetic-torpor-review/refs/zotero-collection.bib
```

Expected: line count > 100; `@` entry count matches the seed count (15–25).

- [ ] **Step 6: Delete `scoping-candidates.md` after seeds are confirmed (optional)**

Once the seed selection is locked, the scoping candidates file is transient. Either delete it or move to an `archive/` subdirectory. Per spec §2.1, this file is transient.

---

## Task 6: Generate paper notes (batch) + smoke test

**Files:**
- Create: `~/github/manuscripts/synthetic-torpor-review/Papers/{slug}.md` × seed count

- [ ] **Step 1: Designate one paper as the smoke-test paper**

Pick one well-known seed paper (e.g., Hrvatin et al. 2020 *Nature*) as the smoke-test paper. Process it FIRST, alone.

- [ ] **Step 2: Run `/zotero-notes` for the smoke-test paper only**

In Claude Code at the project root:

```
/zotero-notes <hrvatin-2020-paper-id-or-zotero-key>
```

Expected: a `Papers/{slug}.md` is created, populated using:
- canonical schema from `obsidian-literature-workflow`,
- extension fields from `profiles/basic-research.md`,
- topic-override fields from the project CLAUDE.md.

- [ ] **Step 3: Run the smoke-test checklist from spec §6.2**

Open the generated `Papers/{slug}.md` and verify ALL of the following:

| Check | Pass criterion |
|-------|----------------|
| Canonical schema | All six headers present and populated: Claim, Method, Evidence, Limitation, Direct relevance to repo, Relation to other papers |
| Basic-research extension | All four sections present and populated or marked `n/a`: Experimental System, Mechanistic Evidence Strength, Data & Reagent Availability, Translational Status |
| Topic override | "Torpor / Hibernation Context" section present and populated |
| Bibliographic block | Contains at least one programmatic source ID (DOI/PMID/arXiv ID/Semantic Scholar paperId) |
| Citation verification | The bibliographic block has been cross-checked by `citation-verification` against at least one of Semantic Scholar, CrossRef, arXiv |

If any check fails, fix the underlying skill/profile/CLAUDE.md issue and re-generate the smoke-test paper BEFORE running batch.

- [ ] **Step 4: Run `/zotero-notes` for the full seed collection**

Once Step 3 passes:

```
/zotero-notes synthetic-torpor-review
```

Expected: one `Papers/{slug}.md` per remaining seed paper.

- [ ] **Step 5: Spot-check 3 random non-smoke-test notes**

Pick 3 random `Papers/` files and run the same checklist from Step 3 against each.

Expected: all 3 pass. Any failure means revisit the generation; do not proceed to Task 7 with broken notes.

- [ ] **Step 6: Batch-verify citations across all paper notes**

In Claude Code, invoke `citation-verification` skill against the entire `Papers/` directory.

Expected: zero "unverified" entries in the report.

---

## Task 7: Snowball expansion

**Files:**
- Update: `~/github/manuscripts/synthetic-torpor-review/Papers/` (additional notes)
- Update: Zotero collection (new items)

- [ ] **Step 1: Extract reference candidates from existing paper notes**

In Claude Code, ask: "From every `Papers/*.md` `Relation to other papers` section, extract referenced works that do NOT yet have a `Papers/` note. List them with their identifier."

Expected: a list of candidate-for-addition papers with DOIs/PMIDs.

- [ ] **Step 2: User triage**

User reviews the candidate list and marks each as `Add` or `Skip`.

- [ ] **Step 3: Add `Add`-marked papers to Zotero**

Import the chosen papers into the `synthetic-torpor-review` Zotero collection.

- [ ] **Step 4: Re-run `/zotero-notes` incrementally**

```
/zotero-notes synthetic-torpor-review --incremental
```

(If the command does not natively support `--incremental`, ask Claude to only process Zotero items lacking a corresponding `Papers/*.md`.)

Expected: new paper notes are added; existing notes are not regenerated.

- [ ] **Step 5: Verify the stop condition (spec §5 Step 5)**

Run:

```bash
ls ~/github/manuscripts/synthetic-torpor-review/Papers/ | wc -l
```

Compare to `target_reference_count` in the project CLAUDE.md.

Repeat Steps 1–4 until either:
- two consecutive snowball passes add < 3 new papers each, OR
- the corpus size approaches `target_reference_count`.

- [ ] **Step 6: Final batch citation re-verification**

Re-run `citation-verification` across the full enlarged `Papers/` directory.

Expected: zero unverified entries.

---

## Task 8: Synthesis

**Files:**
- Create: `~/github/manuscripts/synthetic-torpor-review/Knowledge/Literature-Overview.md`
- Create: `~/github/manuscripts/synthetic-torpor-review/Knowledge/Method-Families.md`
- Create: `~/github/manuscripts/synthetic-torpor-review/Knowledge/Research-Gaps.md`
- Create: `~/github/manuscripts/synthetic-torpor-review/Maps/literature.canvas`
- Create: `~/github/manuscripts/synthetic-torpor-review/Writing/draft-outline.md`

- [ ] **Step 1: Invoke `obsidian-synthesis-map`**

In Claude Code at the project root, ask Claude to invoke `obsidian-synthesis-map` against `Papers/`.

- [ ] **Step 2: Generate `Knowledge/Literature-Overview.md`**

Expected content: narrative arc that walks from clinical TTM/TH (right-hand side) to basic synthetic torpor / metabolic suppression (left-hand side), via the transitional "metabolic-driven cooling vs cooling-driven metabolism" question.

Each claim in the overview cites at least one paper note by wikilink (e.g., `[[Papers/hrvatin-2020-natur]]`).

- [ ] **Step 3: Generate `Knowledge/Method-Families.md`**

Expected content: a comparison table grouping interventions by family — passive cooling, active cooling, pharmacological metabolic suppression (5'-AMP, adenosine A1R agonists, neuropeptide Qrfp), genetic activation of torpor circuits (Qrfp neurons via DREADD), with for each family: representative papers, animal model, primary readouts.

- [ ] **Step 4: Generate `Knowledge/Research-Gaps.md`**

Expected content: an explicit, citable gap statement (NOT generic "more research is needed").

Concrete pass criterion: the gap statement names at least one specific translational question that is supported by basic-research evidence in `Papers/` but is NOT addressed by current clinical TTM/TH trials. Example shape (your actual content will differ):

> "Basic studies in mouse (Hrvatin 2020, Takahashi 2020) demonstrate that
> central activation of Qrfp/Q neurons induces a regulated hypometabolic
> state distinct from passive cooling. No human trial has tested whether
> the cardioprotective and neuroprotective endpoints currently pursued
> through TTM (Nielsen 2013, Dankiewicz 2021) are achievable through
> pharmacological metabolic suppression instead. This translation gap is
> the central question of the present review."

If the gap statement reads like a textbook truism, rewrite it until it points to a specific decidable question.

- [ ] **Step 5: Refresh `Maps/literature.canvas`**

Have Claude generate the canvas with argument-map structure (claim nodes + edges labeled with supports/contradicts/extends), NOT a dense all-to-all graph.

Expected: opens in Obsidian without errors; nodes correspond to claims, papers, and gap statements; edges are labeled.

- [ ] **Step 6: Author `Writing/draft-outline.md`**

Expected content: section-by-section outline of the Japanese review article, with each section's intended argument and the supporting paper-note wikilinks. Sections at minimum:

1. はじめに — 体温管理療法の臨床的現状
2. 体温管理から代謝制御へのパラダイム転換
3. 自然冬眠と合成冬眠の生物学
4. 中枢回路と神経ペプチドによる代謝抑制の制御
5. 臨床応用に向けたtranslation gapと未解決の問い
6. おわりに

Each section bullet must end with at least one paper-note wikilink.

- [ ] **Step 7: Final synthesis review checkpoint (spec §6.3)**

Verify:
- `Research-Gaps.md` is specific and citable (not generic).
- `literature.canvas` opens in Obsidian without errors.
- `draft-outline.md` has wikilinks under every section bullet.

If any check fails, return to the failing step.

---

## Self-Review (run after Task 8)

Re-read the spec sections and confirm coverage:

| Spec section | Implemented by |
|--------------|----------------|
| §2.1 filesystem layout | Tasks 1, 2, 4, 8 |
| §2.2 component responsibilities | Tasks 1 (profile owns extension fields), 3 (project CLAUDE.md owns topic fields), 6 (zotero-obsidian-bridge ingests), 6 (citation-verification gates), 8 (obsidian-synthesis-map composes) |
| §3 profile contract | Task 1 Steps 3, 5, 6 |
| §4 project CLAUDE.md | Task 3 |
| §5 Step 1 Bootstrap | Task 2 |
| §5 Step 2 Scoping | Task 4 |
| §5 Step 3 Seed selection | Task 5 |
| §5 Step 4 Paper-note generation | Task 6 |
| §5 Step 5 Snowball | Task 7 |
| §5 Step 6 Synthesis | Task 8 |
| §5 Step 7 Writing | DEFERRED per spec |
| §6.1 Pre-execution checks | Task 1 Steps 4, 5 |
| §6.2 Post-Step-4 smoke test | Task 6 Step 3 |
| §6.3 Post-Step-6 review | Task 8 Step 7 |

If any spec requirement maps to no task, add a task. (None expected.)

---

## Notes on Execution

- **Commits are NOT included** in this plan per the user's global rule "commit only when the user asks." If the user wants per-task commits, ask once and then add commit steps.
- **Tasks 4–8 are workflow execution**, not classical software implementation. The bite-sized-step discipline is preserved, but verification is via spec checkpoints rather than unit tests.
- **The plan is reusable.** For a future basic-research review on a different topic, only Tasks 2, 3, 4, 5, 6, 7, 8 repeat. Task 1 is one-time infrastructure.
