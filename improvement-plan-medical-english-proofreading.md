# Skill Improvement Plan: medical-english-proofreading

## Priority Summary
- **High Priority (P0)**: 3 items — projected gain **+10 pts**
- **Medium Priority (P1)**: 3 items — projected gain **+6 pts**
- **Low Priority (P2)**: 3 items — projected gain **+3 pts**
- **Quick Wins**: 4 items (≤15 min each)

---

## High Priority Improvements (P0)

### P0-1. Shorten and split the YAML description
**File**: `SKILL.md:3–15`
**Dimension**: Description Quality
**Impact**: +8 pts (description 70 → 90)
**Time**: ~20 min

**Current** (851 chars):
```yaml
description: >-
  Deep, track-changes-style English proofreading for medical and clinical
  manuscripts — case reports, original articles, abstracts, figure/table
  captions, cover letters, and responses to reviewers — aligned with the AMA
  Manual of Style (11th edition) and Nature Research Academies writing
  principles (Be Concise / Be Specific / Be Logical), including
  sentence- and paragraph-level restructuring. Use this skill whenever the
  user asks to proofread, copyedit, polish, revise, "fix the English of", or
  improve the language of any medical or scientific manuscript or manuscript
  section; when a non-native (especially Japanese) author wants a clinical
  paper made publication-ready; or when the user pastes manuscript text and
  asks for language/style improvement — even if they do not explicitly say
  "proofread".
```

**Suggested** (≤200 chars):
```yaml
description: >-
  Deep track-changes proofreading of medical/clinical manuscripts (case
  reports, IMRAD articles, abstracts, captions, cover letters, reviewer
  responses) in AMA 11th-ed style with active voice and Nature concise/
  specific/logical principles. Use when the user asks to proofread,
  copyedit, polish, or improve the English of any medical manuscript
  section, especially from non-native (Japanese) authors.
```

**Reason**: 100–300 char window is enforced by skill convention; the current 851 chars hurts trigger-matching precision and exceeds the Claude for Word add-in limit the author already noted. The detailed scenario list belongs in the body under "When to use".

---

### P0-2. Create `references/` and move detailed content
**File**: new `references/` directory + edits to `SKILL.md:113–127, 165–189, 261–275, 191–259, 323–328`
**Dimension**: Content Organization
**Impact**: +12 pts (organization 60 → 85)
**Time**: ~60 min

**Action**: Create these files by *moving* content (do not duplicate):

| New file | Move from SKILL.md | Approx. content |
|---|---|---|
| `references/substitution-tables.md` | lines 113–127, 165–189 | Wordy→lean, nominalization→verb, inflated→plain |
| `references/section-architecture.md` | lines 191–259 | Introduction (5), Methods (3), Results, Discussion (4), Conclusion, Case report, Abstract, Captions, Cover letter |
| `references/ama-style.md` | lines 261–275 | AMA 11th-ed defaults: spelling, comma, italics, numbers, "hospital day" rule |
| `references/portability.md` | lines 323–328 | The ≤200-char description repackaging note for Claude for Word |
| `references/reporting-guidelines.md` | NEW | CARE / PRISMA / CONSORT / STROBE mapping table (currently only CARE is referenced) |

**Replace in SKILL.md** with short pointers, e.g.:
> ### Redundant-expression replacements
> Replace wordy connectives with lean equivalents. See `references/substitution-tables.md` for the full wordy→lean, nominalization→verb, and inflated→plain tables.

**Reason**: Progressive disclosure is the single biggest scoring lever. Splitting moves ~700 words out of SKILL.md (target: ≤1,200 words in SKILL.md) while keeping all content one read away.

---

### P0-3. Add `examples/` with before/after pairs
**File**: new `examples/` directory
**Dimension**: Structural Integrity + Content Organization
**Impact**: +5 pts (structure 78 → 88, organization +2)
**Time**: ~45 min

**Action**: Create three `before-after-*.md` files. Each follows the format:

```markdown
# Example: <principle>

## Source
<one-paragraph clinical text exhibiting the problem>

## Edited
<the revised paragraph>

## Track changes (showing the principles applied)
1. **Before**: "CRRT was initiated by the renal team on the third hospital day"
   **After**: "The renal team initiated CRRT on hospital day 3"
   **Reason**: passive→active (clinical team as subject); "third hospital day"→"hospital day 3" (AMA Arabic-numeral rule)
2. ...
```

Suggested three:
1. `examples/before-after-active-voice.md` — Japanese-L2 passive over-production
2. `examples/before-after-quantification.md` — vague "most/some/markedly" → specific number with denominator
3. `examples/before-after-topic-stress.md` — choppy paragraph fixed by topic/stress reordering, not by adding connectives

**Reason**: A proofreading skill without before/after examples is the textbook anti-pattern. Examples also let the skill's *output format* be implicitly demonstrated.

---

## Medium Priority Improvements (P1)

### P1-1. Eliminate second-person voice in SKILL.md body
**File**: `SKILL.md:20, 30, 58, 62, 80`
**Dimension**: Writing Style
**Impact**: +5 pts (style 78 → 88)
**Time**: ~20 min

| Line | Current | Suggested |
|---|---|---|
| 20 | "You are proofreading medical and scientific manuscripts written, in most cases, by a non-native English speaker working in emergency and critical care medicine." | "This skill proofreads medical and scientific manuscripts written, in most cases, by non-native English speakers working in emergency and critical care medicine." |
| 30 | "When you justify a change, the reason should map back to one of these." | "When justifying a change, name the principle it maps back to." |
| 58 | "If it is ambiguous or only a fragment, say what you are assuming and proceed." | "If the type is ambiguous or only a fragment is supplied, state the assumption and proceed." |
| 62 | "You cannot fix logic or remove true redundancy without knowing what comes later." | "Logic gaps and true redundancy cannot be detected without knowing what comes later." |
| 80 | "Only after this do you move to sentence-level editing." | "Move to sentence-level editing only after this structural pass." |

**Reason**: Skills convention is descriptive/imperative third person. Role-setting via "You are X" is a prompt-engineering pattern, not a skill convention.

---

### P1-2. Reduce "should" usage and prefer imperative
**File**: `SKILL.md` global (~12 instances)
**Dimension**: Writing Style
**Impact**: +2 pts
**Time**: ~15 min

Examples:
| Current | Suggested |
|---|---|
| "Every edit should serve one of three goals." | "Every edit serves one of three goals." |
| "Each sentence should connect to the previous one" | "Each sentence connects to the previous one" |
| "should carry old/known information" | "carries old/known information" |
| "The abstract must not contain claims absent from the body." | (keep — "must" is correctly stronger here) |

**Reason**: Imperative or declarative-fact framing reads as instruction; "should" reads as advice and weakens the skill's voice.

---

### P1-3. Add CARE / PRISMA / CONSORT / STROBE mapping
**File**: new `references/reporting-guidelines.md` (created in P0-2)
**Dimension**: Structural Integrity + Description-promise alignment
**Impact**: +3 pts
**Time**: ~25 min

**Reason**: The description claims the skill handles case reports, original articles, abstracts, and reviewer responses, but only CARE is named in the body (line 238). The user's `CLAUDE.md` already lists the full mapping — bring it into the skill's references for self-containment:

```markdown
| Manuscript type | Guideline | Key items to verify |
|---|---|---|
| Case report | CARE | Timeline, diagnostic reasoning, patient perspective, informed consent |
| Original article (RCT) | CONSORT | Trial design, randomization, blinding, primary/secondary outcomes, CONSORT flow diagram |
| Original article (observational) | STROBE | Study design declared, eligibility criteria, bias, sample size, statistical methods |
| Systematic review / meta-analysis | PRISMA | Search strategy, PRISMA flow diagram, risk-of-bias assessment, PROSPERO registration |
```

---

## Low Priority Improvements (P2)

### P2-1. Anchor internal cross-references explicitly
**File**: `SKILL.md:89, 92, 195`
**Dimension**: Structural Integrity
**Impact**: +1 pt
**Time**: ~10 min

Replace `see the active/passive section below` / `see below` / `(see Output rules)` with explicit anchors so they survive the P0-2 split, e.g., `see "Active vs. passive voice" in SKILL.md` or `see references/substitution-tables.md#redundant-expressions`.

---

### P2-2. Surface the four justified-passive exceptions as a named rule
**File**: `SKILL.md:157–161`
**Dimension**: Content Organization
**Impact**: +1 pt
**Time**: ~5 min

The four exceptions are excellent content but currently buried in prose. Promote them to a named callout (e.g., **"Four justified-passive exceptions"**) so they can be referenced in track-changes output as `"Reason: justified passive (exception 3 — Methods focus)"`.

---

### P2-3. Add a "Skill self-check" callout at the end of SKILL.md
**File**: `SKILL.md` (new section before "Note on portability")
**Dimension**: Content Organization
**Impact**: +1 pt
**Time**: ~10 min

Add a 3-bullet self-check the model should run before returning output:

```markdown
## Self-check before delivering output

- Every track-change entry names a principle (deletion test, passive→active, etc.).
- No scientific claim, number, or conclusion has been altered.
- Structural gaps are flagged, not filled with invented content.
```

**Reason**: Mirrors `paper-self-review`'s pattern and closes the loop between the "Output rules" and what the model actually returns.

---

## Quick Wins (≤15 min each, do these first)

1. **P0-1 description shortening** — 20 min, +8 pts on its own
2. **P1-1 second-person removal** — 20 min, +5 pts (5 line edits)
3. **P1-2 "should" reduction** — 15 min, +2 pts (global find/replace candidates)
4. **P2-2 named-rule promotion for the four passive exceptions** — 5 min, +1 pt

→ ~60 min of edits, **+16 pts** (72 → ~88, **B+**)

---

## Estimated Time to Complete

| Tier | Items | Time |
|---|---|---|
| High (P0) | 3 | ~2 hr 5 min |
| Medium (P1) | 3 | ~1 hr |
| Low (P2) | 3 | ~25 min |
| **Total** | **9** | **~3 hr 30 min** |

## Expected Score Improvement

| Stage | Score | Grade |
|---|---|---|
| Current | 72/100 | C- |
| After Quick Wins (60 min) | ~88/100 | B+ |
| After all P0 | ~90/100 | A- |
| After P0 + P1 | ~94/100 | A |
| After everything | ~97/100 | A+ |

## Out of Scope (Do Not Change)

The domain content is **excellent and should not be rewritten**. See the "What the Skill Does Right" section of the quality report. This improvement plan is a **packaging refactor**, not a content rewrite — every domain principle, table, and rule survives unchanged; only its file location, voice, and frontmatter shrink.
