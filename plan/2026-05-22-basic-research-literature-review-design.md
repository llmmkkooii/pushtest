# Basic-Research Literature Review Workflow — Design Spec

- **Date**: 2026-05-22
- **Author**: Hiroyuki Yamada (with Claude Code)
- **Status**: Draft for user review
- **First target**: Japanese-language narrative review «体温管理療法から代謝制御療法へ» for the special issue «人工冬眠がもたらす次世代医療に向き合う»
- **Approach selected**: A (minimal extension of existing skills via a profile file)

---

## 1. Goal and Non-Goals

### 1.1 Goal

Establish a reusable, Claude Code-native workflow for **basic-research literature reviews** that:

- reuses existing `~/.claude/skills/` infrastructure (no new top-level skill),
- adds the minimum extension required to handle basic-research-specific extraction (experimental models, mechanistic evidence strength, data/reagent availability, translational status),
- works for **narrative reviews** (not PRISMA systematic reviews),
- produces durable Obsidian project knowledge (`Papers/`, `Knowledge/`, `Maps/`, `Writing/`),
- can be invoked again for future basic-research reviews with only a project-level CLAUDE.md override.

### 1.2 Non-Goals

- PRISMA-compliant systematic review automation. PRISMA SR remains a separate workflow that requires two independent human reviewers; this spec does not replace that.
- Replacement of `obsidian-literature-workflow`. The existing skill stays canonical; this spec only adds a profile file as an extension point.
- A dedicated `literature-extraction-basic` skill. Earlier discussion concluded this would duplicate existing schema work and was rejected.
- NotebookLM integration. Excluded per existing account-scope guardrail (see `MEMORY.md` ➔ `notebooklm-skill-account-guardrail.md`).
- Figure-image quantitative reinterpretation. Western-blot densitometry, IF localization scoring, and similar visual judgments remain human tasks.

### 1.3 Success Criteria

| Criterion | Definition of done |
|-----------|--------------------|
| Reusability | The new profile file contains zero topic-specific (torpor/TTM) content; all topic-specific overrides live in the project-local CLAUDE.md. |
| Non-invasive | `obsidian-literature-workflow/SKILL.md` is unchanged. The profile is loaded as an extension, not a replacement. |
| Citation integrity | Every paper note's bibliographic block is cross-checked against Semantic Scholar OR CrossRef OR arXiv via the existing `citation-verification` skill. Zero unchecked entries. |
| Synthesis output | `Knowledge/Research-Gaps.md` explicitly names the translation gap between clinical TTM/TH evidence and basic synthetic-torpor mechanisms, with citations to specific papers in `Papers/`. |
| Workflow smoke test | One representative paper passes through the full Step 1 ➔ Step 6 pipeline and produces a complete `Papers/{slug}.md` plus an entry in `Maps/literature.canvas`. |

---

## 2. Architecture

### 2.1 Filesystem layout

```
~/.claude/skills/obsidian-literature-workflow/
├── SKILL.md                              # existing, unchanged
└── profiles/                             # NEW directory
    └── basic-research.md                 # NEW: extension profile

~/github/manuscripts/synthetic-torpor-review/    # NEW project
├── .claude/project-memory/registry.yaml  # binding marker (auto)
├── CLAUDE.md                             # project-local rules (venue, deadline,
│                                         # citation style, JA language, topic overrides)
├── Papers/                               # one structured note per paper
├── Knowledge/
│   ├── Literature-Overview.md
│   ├── Method-Families.md
│   ├── Research-Gaps.md
│   └── scoping-candidates.md             # transient, deleted after seed selection
├── Maps/
│   └── literature.canvas
├── Writing/
│   └── draft-outline.md
└── refs/
    └── zotero-collection.bib             # exported from Zotero
```

### 2.2 Component responsibilities

| Component | Owns | Reads from | Writes to |
|-----------|------|------------|-----------|
| `obsidian-literature-workflow` (existing) | Canonical paper-note schema, `Knowledge/` synthesis routing, `Maps/literature.canvas` refresh | `Papers/`, `Knowledge/` | `Papers/`, `Knowledge/`, `Maps/` |
| `profiles/basic-research.md` (new) | Extension fields for in-vivo/in-vitro/ex-vivo/computational basic research | (loaded by obsidian-literature-workflow) | (no direct writes; consumed) |
| Project-local `CLAUDE.md` (new) | Venue rules, citation style, deadline, topic-specific override fields | (loaded by Claude on project entry) | (no writes) |
| `zotero-obsidian-bridge` (existing) | Zotero ➔ `Papers/` ingest | Zotero | `Papers/` |
| `citation-verification` (existing) | Bibliographic integrity check via SS/CrossRef/arXiv | `Papers/` | (annotations only) |
| `obsidian-synthesis-map` (existing) | Higher-level synthesis notes | `Papers/` | `Knowledge/` |
| `research-ideation` (existing) | Scoping search via MCP | (external APIs) | `Knowledge/scoping-candidates.md` |
| `medical-english-proofreading` (existing) | Final-pass copyedit for the Japanese manuscript | `Writing/` | `Writing/` (track-changes) |
| `writing-anti-ai` (existing) | Remove AI writing patterns from drafts | `Writing/` | `Writing/` |
| `paper-self-review` (existing) | Pre-submission completeness check | `Writing/` | (review report) |

### 2.3 Key design decisions

| Decision | Rationale |
|----------|-----------|
| Profile in a separate file, not in `SKILL.md` | Allows future clinical/method-comparison/omics profiles without bloating the parent skill. |
| Project root under `~/github/manuscripts/` | Matches existing clinical-manuscript convention; one consistent workspace for all writing projects. |
| Topic-specific fields (torpor context, metabolic-vs-thermal hypothesis) live in project CLAUDE.md, not in the profile | Keeps the profile reusable across unrelated basic-research reviews. |
| Narrative-review mode is the default; PRISMA mode is out of scope here | Matches the immediate deliverable; PRISMA-mode work continues to follow the existing clinical SR convention. |
| No new top-level skill in `~/.claude/skills/` | YAGNI; one profile file solves the documented gap. Re-evaluate after running 2+ reviews end-to-end. |

---

## 3. Profile Specification: `profiles/basic-research.md`

### 3.1 Contract

The profile is a **markdown extension document**, not executable code. It is loaded by Claude in addition to `obsidian-literature-workflow/SKILL.md` when the active project's CLAUDE.md declares `literature_profile: basic-research`.

The profile MUST:

- declare which fields are added to the canonical paper-note schema,
- declare which fields remain unchanged (delegated to the parent skill),
- be free of project-specific topic vocabulary.

The profile MUST NOT:

- redefine or remove any field from the canonical schema (`Claim`, `Method`, `Evidence`, `Limitation`, `Direct relevance to repo`, `Relation to other papers`),
- contain torpor/TTM/hibernation/AKI/nephrology/etc. vocabulary,
- introduce executable scripts (those belong in a separate skill if needed).

### 3.2 Extension fields (additive)

Inserted between `Evidence` and `Limitation` of the canonical schema:

```markdown
## Experimental System
- Type: [in vivo | in vitro | ex vivo | clinical | computational | review]
- Species/strain:
- Genetic manipulation: [global KO | conditional KO | KD | OE | none]
  - Cre driver / inducible system:
  - Controls: [littermate | non-littermate | wild-type unrelated]
- Cell line / primary culture: (with authentication note if applicable)
- Disease/perturbation model: [induction method, severity]

## Mechanistic Evidence Strength
- Level: [correlative | gain-of-function | loss-of-function | rescue-confirmed | structural/biochemical]
- Direct binding shown: [Y/N — method: IP / ChIP / proximity / cryo-EM / ...]
- Off-target controls reported: [Y/N — note]

## Data & Reagent Availability
- Public datasets: [GEO / SRA / PRIDE / GenBank ID(s)]
- Key reagents: [Addgene plasmid IDs / antibody catalog#s + validation note]
- Code: [GitHub / Zenodo URL]

## Translational Status
- Stage: [basic only | translational candidate | early human | established clinical]
- Distance to clinical: [free-text, one sentence]
```

### 3.3 Field interpretation rules

- A field that does not apply is recorded as `n/a` rather than omitted. This preserves the diff usefulness of paper-note comparison across the corpus.
- "Mechanistic Evidence Strength ➔ Level" follows a strict ladder: rescue-confirmed > loss-of-function > gain-of-function > correlative. Claude records the highest level demonstrated, not claimed.
- Data availability uses accession IDs only; URLs go in the reagent line. No bare "yes" or "no" — always include the identifier when present.

---

## 4. Project-Local CLAUDE.md (for `synthetic-torpor-review`)

### 4.1 Required fields

The project CLAUDE.md MUST declare:

```yaml
literature_profile: basic-research        # activates §3 profile
review_type: narrative                    # narrative | scoping | prisma-sr
deliverable_language: ja                  # ja | en
citation_style: vancouver                 # vancouver | ama | apa | nature | <other>
target_venue: "TBD — to be filled in"
target_word_count: TBD
target_reference_count: TBD
deadline: TBD
```

### 4.2 Topic-specific override fields (for this review only)

Added to each paper note via the project CLAUDE.md, NOT via the profile:

```markdown
## Torpor / Hibernation Context
- Setting: [natural hibernator | facultative torpor | synthetic torpor | hypothermia-only | not applicable]
- Metabolic vs thermal emphasis: [metabolic-primary | thermal-primary | mixed]
- Bridge to TTM/TH: [explicit | implicit | none]
```

### 4.3 Language and style rules inherited

The project CLAUDE.md inherits the user's global rules:

- Active voice, "Hospital day 3" Arabic numerals, numbers spelled out 1–9 / numerals ≥10 in prose, numerals always for measurements.
- For the Japanese deliverable: synthesis prose is である調. Direct paper-note quotes keep English. Technical terms keep English.
- `writing-anti-ai` applied to all draft prose before review.

---

## 5. Workflow (Narrative-Review Mode)

Each step lists its skill/command, its deliverable, and the stop-and-review checkpoint.

### Step 1 — Bootstrap (~10 min)

- **Command**: `/obsidian-init` against `~/github/manuscripts/synthetic-torpor-review/`
- **Manual action**: create `profiles/basic-research.md` per §3
- **Manual action**: create project CLAUDE.md per §4
- **Checkpoint**: registry.yaml exists; `literature_profile: basic-research` is declared; `obsidian-project-memory` activates on entering the directory.

### Step 2 — Scoping search (~30–60 min)

- **Skill**: `research-ideation`
- **Inputs**: 3–5 search queries spanning PubMed (clinical TTM/TH side), bioRxiv (preprint torpor), Semantic Scholar (citing/cited expansion from seed papers Hrvatin 2020 and Takahashi 2020).
- **Output**: `Knowledge/scoping-candidates.md` with ~100 candidate papers tagged by source.
- **Checkpoint**: user reviews the scoping list, removes obvious off-topic items.

### Step 3 — Seed selection (~30 min, human-led)

- **Action**: user selects 15–25 papers from the scoping list as the seed corpus.
- **Action**: create Zotero collection `synthetic-torpor-review` and import the seeds.
- **Checkpoint**: Zotero collection contains the seed set; PDFs attached where available.

### Step 4 — Paper-note generation (batch, Claude Code)

- **Command**: `/zotero-notes` with the `synthetic-torpor-review` collection.
- **Skills invoked under the hood**: `zotero-obsidian-bridge`, `obsidian-literature-workflow` + `profiles/basic-research.md`, `citation-verification`.
- **Output**: one `Papers/{slug}.md` per seed paper, fully populated with canonical schema + §3 extension fields + §4.2 topic fields.
- **Checkpoint**: spot-check 3 random paper notes; run `citation-verification` over the batch; confirm zero unverified entries.

### Step 5 — Snowball expansion (iterative)

- **Action**: from each paper note's `Relation to other papers` block, extract referenced works that are NOT yet in the corpus.
- **Action**: add them to the Zotero collection, re-run Step 4 incrementally.
- **Stop condition**: two consecutive snowball passes add fewer than 3 new papers each, or the deliverable's `target_reference_count` is approached.
- **Checkpoint**: corpus size matches the review scale; no obvious key paper is missing (user judgment).

### Step 6 — Synthesis

- **Skill**: `obsidian-synthesis-map`
- **Outputs**:
  - `Knowledge/Literature-Overview.md`: narrative arc from clinical TTM/TH to synthetic torpor.
  - `Knowledge/Method-Families.md`: cooling vs metabolic-suppression intervention families.
  - `Knowledge/Research-Gaps.md`: explicit naming of the translation gap (this is the spine of the review's argument).
  - `Maps/literature.canvas`: argument-map structure, not all-to-all links.
  - `Writing/draft-outline.md`: section-by-section outline matching the special-issue brief.
- **Checkpoint**: user confirms the gap statement is publishable, not generic.

### Step 7 (deferred) — Writing

- **Skills (applicable as-is)**:
  - `writing-anti-ai`: bilingual; usable on the Japanese draft.
  - `paper-self-review`: structural/completeness check; language-agnostic.
- **Skill with a language gap**:
  - `medical-english-proofreading` is **English-only** (AMA 11th edition). It cannot copyedit Japanese prose directly. Two practical options for the Japanese deliverable:
    (a) draft directly in Japanese; defer to a future Japanese-specific proofreading skill (out of scope for this spec), OR
    (b) draft an English working version first for synthesis verification, then translate to Japanese for the final deliverable. The English working version *can* be run through `medical-english-proofreading`.
  - The decision between (a) and (b) is deferred to the writing spec; it depends on the user's drafting preference and the venue's style expectations.
- **Output**: submission-ready Japanese manuscript.
- **Out of scope for this spec**: writing is treated as a downstream activity. A separate writing spec will resolve the Japanese-proofreading gap.

---

## 6. Verification

### 6.1 Pre-execution checks

- `obsidian-literature-workflow/SKILL.md` MD5/SHA matches before and after profile addition (the parent skill must be untouched).
- `profiles/basic-research.md` passes the negative-content check: `grep -iE "(torpor|hibernation|TTM|hypothermia|AKI|kidney|nephron|sepsis)"` returns zero lines.

### 6.2 Post-Step-4 smoke test

One designated seed paper is processed end-to-end. The resulting `Papers/{slug}.md` MUST contain:

- all six canonical schema sections, populated (no empty headers),
- all four §3 extension sections, populated or marked `n/a`,
- all three §4.2 topic sections, populated or marked `n/a`,
- bibliographic block with at least one programmatic source identifier (DOI/PMID/arXiv ID/Semantic Scholar paper ID) verified.

Failure of any of these blocks Step 5 until corrected.

### 6.3 Post-Step-6 review

- `Knowledge/Research-Gaps.md` is read aloud (mentally) to confirm it states a specific, citable gap, not a generic "more research is needed" line.
- `Maps/literature.canvas` opens in Obsidian without errors and renders the argument-map structure.

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Profile drifts into topic-specific content over time | §3.1 contract forbids topic vocabulary; verification §6.1 grep check enforces it. |
| Paper notes accumulate but synthesis never happens | Step 5 has an explicit stop condition; Step 6 must run before Step 7 begins. |
| Citation hallucination | `citation-verification` skill is invoked in Step 4 batch; no manuscript citation ever bypasses programmatic verification. |
| Scope creep into PRISMA SR | This spec explicitly excludes PRISMA in §1.2; a future spec can add a `profiles/prisma-sr.md` extension if needed. |
| Topic-specific override fields leak into the reusable profile | §4.2 owns these fields, and the profile (§3) is checked by §6.1. |
| Re-running on a new basic-research topic requires re-deciding extension fields | The profile is topic-agnostic by §3.1 design; only the project CLAUDE.md and topic overrides need authoring per project. |

---

## 8. Out of Scope (Explicitly Deferred)

These were considered and deferred, not forgotten:

- **PIER paragraph-structure checking skill**: defer until the writing stage reveals a concrete need; existing `medical-english-proofreading` plus `writing-anti-ai` covers immediate needs.
- **Logical-structure self-review skill**: `paper-self-review` already covers this.
- **Narrative-review orchestrator skill (Approach C)**: revisit only if 2+ basic-research reviews complete under Approach A and reveal a clear orchestration gap.
- **Figure-image semantic interpretation**: a separate vision-skill design problem, not in this scope.
- **Living-systematic-review-style auto-updating**: future, not now.

---

## 9. Implementation Order (Preview for `writing-plans`)

A separate implementation plan will be produced by `superpowers:writing-plans`. Anticipated coarse order:

1. Write `profiles/basic-research.md` and pass §6.1 checks.
2. Bootstrap `~/github/manuscripts/synthetic-torpor-review/` via `/obsidian-init`.
3. Author project CLAUDE.md with all required fields filled (some marked `TBD` if not yet known).
4. Execute Step 2 scoping search; gate on user review of the candidate list.
5. Execute Step 3 seed selection; gate on Zotero state.
6. Execute Step 4 batch note generation + §6.2 smoke test; gate on smoke-test pass.
7. Execute Step 5 snowball loop until stop condition.
8. Execute Step 6 synthesis.

Writing (Step 7) is deferred to a future spec.

---

## 10. Open Questions for the User

The following items are marked `TBD` in §4 and should be answered before the project CLAUDE.md is finalized:

1. **Venue**: which Japanese journal or book chapter is the host for «体温管理療法から代謝制御療法へ»?
2. **Word count target**: approximate Japanese character count or English-equivalent word count?
3. **Reference count cap**: typical 40–80 for a Japanese review article, but venue-specific.
4. **Deadline**: drives the stop conditions in Steps 5 and 6.
5. **Co-authors**: any? If yes, the workflow may need to coordinate Papers/ ownership.

These are not blockers for Step 1 (bootstrap), but Step 5 (snowball stop condition) and Step 6 (synthesis scale) depend on them.
