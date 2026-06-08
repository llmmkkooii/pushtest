# Skill Quality Report: medical-english-proofreading

## Executive Summary
- **Overall Score**: 72/100 (**C-**)
- **Evaluated**: 2026-05-21
- **Skill Path**: `~/.claude/skills/medical-english-proofreading/`
- **Files**: 1 (`SKILL.md` only — no `references/`, `examples/`, or `scripts/`)
- **Size**: 13,614 B / 328 lines / 2,044 words / description 851 chars

The skill has excellent *domain content* — the three-pillar philosophy, the four-step workflow, the AMA + Nature alignment, and the Japanese-L2 passive-voice insight are all sophisticated and editorially correct. Its weakness is **packaging**: a 2,044-word single-file skill with no progressive disclosure, an 851-char description, and a second-person opening. With ~3 hours of restructuring (no domain rewriting), it can reach **A- (90+)**.

## Dimension Scores

### 1. Description Quality (25%)
**Score**: 70/100

**Strengths**:
- ✅ Excellent enumeration of trigger phrases: *proofread, copyedit, polish, revise, "fix the English of", improve the language*
- ✅ Highly specific scenarios named (case reports, original articles, abstracts, figure/table captions, cover letters, reviewer responses)
- ✅ Explicitly handles edge case: non-native (Japanese) authors, implicit requests ("even if they do not explicitly say 'proofread'")

**Weaknesses**:
- ❌ **Length: 851 chars** — far over the 100–300 char optimal. The author is aware (note on portability at end) but does not act on it
- ❌ Mixes two registers — declarative description AND a "Use this skill whenever..." imperative — making it harder to parse
- ❌ The "what this skill is" and "when to use it" are run together in one sentence rather than separated

**Recommendations**:
1. Split the description into a **lead sentence (≤200 chars)** stating *what it does* + a **trigger sentence** listing *when to use it*
2. Move the detailed scenario list (case reports, abstracts, …) into the body of SKILL.md under a "When to use" section
3. Apply the same shortening used in the existing portability note (≤200 chars) as the default, not an alternate

---

### 2. Content Organization (30%)
**Score**: 60/100

**Strengths**:
- ✅ Logical macro-flow: Philosophy → Workflow → Sentence-level → Section-level → AMA defaults → Output → Rules
- ✅ Numbered subworkflows (Step 1–4, edit priority 1–6) are clear and operational
- ✅ Tables used effectively for wordy→lean, nominalization→verb, inflated→plain substitutions

**Weaknesses**:
- ❌ **No `references/` directory** despite obvious extraction candidates:
  - 3 substitution tables (wordy/lean, nominalization, plain words)
  - AMA style defaults section
  - Section-level architecture (Introduction 5 elements, Methods 3 elements, Discussion 4 elements, Case report, Abstract, Caption, Cover letter)
- ❌ **No `examples/` directory** — a proofreading skill is the textbook case for *before/after* examples (e.g., a sample passive→active conversion, a vague-quantifier fix, a topic/stress-position reorder)
- ❌ SKILL.md is **2,044 words** — slightly over the 1,500–2,000 ideal sweet spot, and the body will exceed it once "Note on portability" plus more reference material is added later
- ❌ "Note on portability" at line 323–328 is meta-content that belongs in `references/portability.md`, not the main body

**Recommendations**:
1. Create `references/` and move: `ama-style.md`, `section-architecture.md`, `substitution-tables.md`, `portability.md`
2. Create `examples/` with at least: `before-after-active-voice.md`, `before-after-quantification.md`, `before-after-topic-stress.md`
3. Trim SKILL.md to ≤1,200 words: keep the **three pillars**, the **4-step workflow**, the **edit-priority list**, and **output format** — push the rest to `references/`

---

### 3. Writing Style (20%)
**Score**: 78/100

**Strengths**:
- ✅ Strong imperative verbs throughout edits: *Replace, Convert, Target, Flag, Apply, Treat, Prefer, Evaluate, Produce*
- ✅ Objective, instructional tone — no marketing/hedging language
- ✅ Principles are *named* concretely ("deletion test", "topic/stress reorder for signposting", "L2 interference pattern") so the reasoning is reusable
- ✅ "What not to do" section is a strong negative-instruction pattern

**Weaknesses**:
- ❌ **Second-person opening**: `You are proofreading medical and scientific manuscripts...` (line 20). Role-setting openers in second person are common in agent prompts but not in well-formed skills, which prefer descriptive framing
- ❌ Scattered second person in workflow steps:
  - "When you justify a change, the reason should map back…" (line 30)
  - "you cannot fix logic or remove true redundancy…" (line 62)
  - "Only after this do you move to sentence-level editing." (line 80)
  - "If it is ambiguous or only a fragment, say what you are assuming and proceed." (line 58)
- ❌ "should serve" / "should carry" / "should" appears ~12 times — convention prefers imperative or declarative-must

**Recommendations**:
1. Replace `You are proofreading...` with declarative framing: `This skill proofreads medical and scientific manuscripts written by non-native English speakers in emergency and critical care medicine.`
2. Convert remaining "you" instances to imperative: "When justifying a change…", "Logic and true redundancy cannot be fixed without knowing what comes later", "Move to sentence-level editing only after this step"
3. Reduce "should" usage by half; prefer imperative ("Serve one of three goals", "Carry old/known information") or stronger modal ("must")

---

### 4. Structural Integrity (25%)
**Score**: 78/100

**Strengths**:
- ✅ Valid YAML frontmatter — `name` and `description` both present
- ✅ No broken external file references (all references are internal cross-references like "see below")
- ✅ Skill loads cleanly in the harness (visible in available-skills list)

**Weaknesses**:
- ❌ Directory has no subdirectories despite the skill's complexity — `references/` and `examples/` should exist for a 2,000-word skill
- ❌ No supporting artifacts that a proofreading skill would benefit from:
  - `examples/sample-case-report-before.md` + `sample-case-report-after.md`
  - `references/reporting-guidelines.md` (CARE/PRISMA/CONSORT/STROBE — only CARE is currently mentioned)
  - `scripts/` not needed for this skill type, so absence is fine
- ❌ Internal references like "see the active/passive section below" / "see Output rules" are unanchored — when the skill is later split, these will break

**Recommendations**:
1. Add directory structure:
   ```
   medical-english-proofreading/
   ├── SKILL.md
   ├── references/
   │   ├── ama-style.md
   │   ├── section-architecture.md
   │   ├── substitution-tables.md
   │   ├── reporting-guidelines.md   ← NEW (CARE/PRISMA/CONSORT/STROBE)
   │   └── portability.md
   └── examples/
       ├── before-after-active-voice.md
       ├── before-after-quantification.md
       └── before-after-topic-stress.md
   ```
2. Replace internal "see below" references with explicit file/section anchors once split
3. Add CARE/PRISMA/CONSORT/STROBE coverage — currently only CARE is referenced, but the description claims the skill handles case reports AND original articles AND reviewer responses, all of which have their own checklists

---

## Grade Breakdown
| Dimension | Score | Weight | Contribution |
|-----------|-------|--------|--------------|
| Description | 70/100 | 25% | 17.5 |
| Organization | 60/100 | 30% | 18.0 |
| Style | 78/100 | 20% | 15.6 |
| Structure | 78/100 | 25% | 19.5 |
| **Overall** | **70.6/100** | **100%** | **~72 (C-)** |

## What the Skill Does Right (Do Not Touch These)

These elements are the skill's competitive advantage — preserve them as-is during any restructuring:

1. **Three-pillar philosophy** (Be Concise / Be Specific / Be Logical) with the explicit "shorter is not the goal; *nothing wasted* is the goal" reframing
2. **Edit-priority order** (1. Meaning → 2. Active voice → 3. Conciseness → 4. Grammar → 5. Numbers → 6. Terminology) — this is unusually rigorous
3. **Topic/stress position** discussion with the cross-sentence signposting rule
4. **L2 interference observation** about Japanese passive-voice over-production with the **four justified-passive exceptions**
5. **Division-of-labor rule** for figures/captions ("caption states facts; Results states trends")
6. **Output format** with the 4-block structure (Summary / Revised text / Track changes / Questions to author) and the "name the principle" annotation convention
7. **"Hospital day 3" Arabic-numeral rule** and other AMA number-style specifics

## Next Steps
See `improvement-plan-medical-english-proofreading.md` for prioritized fixes with current-vs-suggested content, time estimates, and expected score improvement.
