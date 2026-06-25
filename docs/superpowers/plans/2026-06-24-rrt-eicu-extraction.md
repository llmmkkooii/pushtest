# eICU-CRD Extraction Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-pandas eICU-CRD extraction layer that turns raw eICU tables into the pipeline's input CSVs (eICU-shaped `crrt_events`, canonical `labs`, canonical `flags`).

**Architecture:** Three pure transform functions in `src/rrt_liberation/extract/eicu.py` (raw eICU DataFrame → output DataFrame), using configurable lowercase-contains string matching (eICU is string-based, not itemid-based). A `pipeline/extract_eicu.py` Hydra entry loads real raw tables locally. NO real-data verification is possible here — only synthetic-table logic tests + schema conformance; the user runs it on credentialed eICU locally. Parallel to the MIMIC extraction (sub-project G), already on main.

**Tech Stack:** Python 3.11, uv, pandas, Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-24-rrt-eicu-extraction-design.md](../specs/2026-06-24-rrt-eicu-extraction-design.md)

**Working dir:** paths relative to `tools/rrt-liberation/`. Branch `feature/rrt-eicu-extraction`. Run via `uv run`.

**Conventions:** pure functions, type hints, module logger (no `print`), `__all__`, files 200-400 lines. Existing `src/` analysis modules, `extract/mimic.py`, all pipeline entrypoints, and all prior tests stay unchanged.

**Output schemas (must match the pipeline's consumers exactly):**
- `crrt_events` (eICU-shaped — `EicuCohortBuilder.to_canonical_events` converts offsets downstream): columns `patientunitstayid, treatmentoffset, treatmentstopoffset, treatmentstring`.
- `labs` (canonical): columns `stay_id, itemid, valuenum` (urine→226559, creatinine→50912).
- `flags` (canonical): columns `stay_id, sepsis_shock, vasopressor, mechanical_ventilation` (0/1, one row per stay).

**Assumed raw eICU columns (user supplies; verify against your eICU version):**
- `treatment`: `patientunitstayid, treatmentoffset, treatmentstopoffset, treatmentstring`.
- `lab`: `patientunitstayid, labname, labresult`.
- `intakeoutput`: `patientunitstayid, celllabel, cellvaluenumeric`.
- `diagnosis`: `patientunitstayid, diagnosisstring`.
- `infusiondrug`: `patientunitstayid, drugname`.
- `respiratorycare`: `patientunitstayid`.
- `patient` (stays): `patientunitstayid`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/rrt_liberation/extract/eicu.py` | `_contains_any` + `build_eicu_crrt_events`, `build_eicu_labs`, `build_eicu_flags` |
| `src/rrt_liberation/extract/__init__.py` | export eICU builders alongside MIMIC builders |
| `pipeline/extract_eicu.py` | Hydra loader → 3 builders → write CSVs |
| `conf/extract_eicu.yaml` | raw paths, term lists, merge_gap, output dir |
| `tests/test_extract_eicu.py` | per-builder unit tests + extract→eICU-cohort→features integration |

---

## Task 1: `build_eicu_crrt_events` (offset-form episode reconstruction)

**Files:**
- Create: `src/rrt_liberation/extract/eicu.py`
- Modify: `src/rrt_liberation/extract/__init__.py`
- Test: `tests/test_extract_eicu.py`

- [ ] **Step 1: Write the failing test** `tests/test_extract_eicu.py`:

```python
import pandas as pd

from rrt_liberation.extract import build_eicu_crrt_events


def _treatment(rows):
    # rows: (patientunitstayid, treatmentstring, start_min, stop_min)
    return pd.DataFrame(
        [
            {"patientunitstayid": p, "treatmentstring": s,
             "treatmentoffset": a, "treatmentstopoffset": b}
            for (p, s, a, b) in rows
        ]
    )


def test_filters_crrt_by_term_lowercase():
    t = _treatment([(1, "Renal|Dialysis|CVVHDF", 0, 1440), (1, "antibiotics", 0, 60)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvhdf"], merge_gap_minutes=360.0)
    assert list(ev.columns) == [
        "patientunitstayid", "treatmentoffset", "treatmentstopoffset", "treatmentstring"
    ]
    assert len(ev) == 1
    assert ev.iloc[0]["treatmentstring"] == "CRRT"


def test_merges_within_gap_minutes():
    # fragments 0-120 and 240-360; gap 120min <= 360 -> merge to 0-360
    t = _treatment([(1, "CVVH", 0, 120), (1, "CVVH", 240, 360)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvh"], merge_gap_minutes=360.0)
    assert len(ev) == 1
    assert ev.iloc[0]["treatmentoffset"] == 0
    assert ev.iloc[0]["treatmentstopoffset"] == 360


def test_splits_beyond_gap_minutes():
    t = _treatment([(1, "CVVH", 0, 120), (1, "CVVH", 240, 360)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvh"], merge_gap_minutes=60.0)
    assert len(ev) == 2


def test_separate_stays_not_merged():
    t = _treatment([(1, "CVVH", 0, 120), (2, "CVVH", 60, 180)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvh"], merge_gap_minutes=360.0)
    assert set(ev["patientunitstayid"]) == {1, 2}
    assert len(ev) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract_eicu.py -q`
Expected: FAIL (`ImportError: cannot import name 'build_eicu_crrt_events'`)

- [ ] **Step 3: Implement**

`src/rrt_liberation/extract/eicu.py`:

```python
"""eICU-CRD extraction: raw tables -> pipeline input CSVs (pure pandas, string-match)."""

from __future__ import annotations

import logging
from typing import List, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

_EICU_EVENTS_COLS = ["patientunitstayid", "treatmentoffset", "treatmentstopoffset", "treatmentstring"]
_LABS_COLS = ["stay_id", "itemid", "valuenum"]
_URINE_CANONICAL = 226559
_CREATININE_CANONICAL = 50912


def _contains_any(series: pd.Series, terms: Sequence[str]) -> pd.Series:
    """Boolean mask: lowercase substring match against any term."""
    low = series.astype(str).str.lower()
    needles = [t.lower() for t in terms]
    return low.apply(lambda s: any(n in s for n in needles))


def build_eicu_crrt_events(
    treatment: pd.DataFrame,
    crrt_terms: Sequence[str],
    merge_gap_minutes: float = 360.0,
) -> pd.DataFrame:
    """CRRT on-intervals (eICU minute-offset form) per stay, merging within the gap."""
    crrt = treatment[_contains_any(treatment["treatmentstring"], crrt_terms)].copy()
    if crrt.empty:
        return pd.DataFrame(columns=_EICU_EVENTS_COLS)
    crrt["treatmentoffset"] = crrt["treatmentoffset"].astype(float)
    crrt["treatmentstopoffset"] = crrt["treatmentstopoffset"].astype(float)

    rows: List[dict] = []
    for pid, grp in crrt.sort_values("treatmentoffset").groupby("patientunitstayid"):
        cur_start = cur_end = None
        for _, r in grp.iterrows():
            s, e = r["treatmentoffset"], r["treatmentstopoffset"]
            if cur_start is None:
                cur_start, cur_end = s, e
            elif s <= cur_end + merge_gap_minutes:
                cur_end = max(cur_end, e)
            else:
                rows.append(
                    {"patientunitstayid": pid, "treatmentoffset": cur_start,
                     "treatmentstopoffset": cur_end, "treatmentstring": "CRRT"}
                )
                cur_start, cur_end = s, e
        rows.append(
            {"patientunitstayid": pid, "treatmentoffset": cur_start,
             "treatmentstopoffset": cur_end, "treatmentstring": "CRRT"}
        )
    return pd.DataFrame(rows, columns=_EICU_EVENTS_COLS)


def build_eicu_labs(*args: object, **kwargs: object) -> pd.DataFrame:
    raise NotImplementedError("build_eicu_labs is implemented in Task 2")


def build_eicu_flags(*args: object, **kwargs: object) -> pd.DataFrame:
    raise NotImplementedError("build_eicu_flags is implemented in Task 3")
```

Replace `src/rrt_liberation/extract/__init__.py` with:

```python
from rrt_liberation.extract.eicu import (
    build_eicu_crrt_events,
    build_eicu_flags,
    build_eicu_labs,
)
from rrt_liberation.extract.mimic import (
    build_mimic_crrt_events,
    build_mimic_flags,
    build_mimic_labs,
)

__all__ = [
    "build_mimic_crrt_events",
    "build_mimic_labs",
    "build_mimic_flags",
    "build_eicu_crrt_events",
    "build_eicu_labs",
    "build_eicu_flags",
]
```

(The labs/flags stubs keep the package importable; Tasks 2-3 replace them. Do NOT add tests asserting the stubs raise — they would need deleting in Tasks 2-3.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract_eicu.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Whole suite + lint/type**

Run: `uv run pytest -q` (no regressions), `uv run ruff check src/rrt_liberation/extract/ tests/test_extract_eicu.py`, `uv run mypy src/rrt_liberation/extract/eicu.py`. All clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/extract tools/rrt-liberation/tests/test_extract_eicu.py
git commit -m "feat(rrt): add eICU CRRT-event extraction (offset-form episode reconstruction)"
```

---

## Task 2: `build_eicu_labs`

**Files:**
- Modify: `src/rrt_liberation/extract/eicu.py` (replace the `build_eicu_labs` stub)
- Test: `tests/test_extract_eicu.py` (add)

- [ ] **Step 1: Write the failing test** — append to `tests/test_extract_eicu.py`:

```python
from rrt_liberation.extract import build_eicu_labs


def test_labs_creatinine_and_urine_canonical():
    lab = pd.DataFrame(
        {"patientunitstayid": [10, 10], "labname": ["creatinine", "sodium"],
         "labresult": [1.5, 140.0]}
    )
    intakeoutput = pd.DataFrame(
        {"patientunitstayid": [10, 10], "celllabel": ["Urine (mL)", "Stool"],
         "cellvaluenumeric": [750.0, 200.0]}
    )
    labs = build_eicu_labs(
        lab, intakeoutput, creatinine_terms=["creatinine"], urine_terms=["urine"]
    )
    assert list(labs.columns) == ["stay_id", "itemid", "valuenum"]
    cr = labs[labs["itemid"] == 50912]
    assert len(cr) == 1 and cr.iloc[0]["valuenum"] == 1.5 and cr.iloc[0]["stay_id"] == 10
    uo = labs[labs["itemid"] == 226559]
    assert len(uo) == 1 and uo.iloc[0]["valuenum"] == 750.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract_eicu.py::test_labs_creatinine_and_urine_canonical -q`
Expected: FAIL (NotImplementedError from the stub)

- [ ] **Step 3: Implement** — replace the `build_eicu_labs` stub in `src/rrt_liberation/extract/eicu.py` with:

```python
def build_eicu_labs(
    lab: pd.DataFrame,
    intakeoutput: pd.DataFrame,
    creatinine_terms: Sequence[str],
    urine_terms: Sequence[str],
) -> pd.DataFrame:
    """Canonical labs: creatinine (lab.labname -> 50912) + urine (intakeoutput -> 226559)."""
    cr = lab[_contains_any(lab["labname"], creatinine_terms)][
        ["patientunitstayid", "labresult"]
    ].copy()
    cr = cr.rename(columns={"patientunitstayid": "stay_id", "labresult": "valuenum"})
    cr["itemid"] = _CREATININE_CANONICAL
    cr["valuenum"] = cr["valuenum"].astype(float)

    uo = intakeoutput[_contains_any(intakeoutput["celllabel"], urine_terms)][
        ["patientunitstayid", "cellvaluenumeric"]
    ].copy()
    uo = uo.rename(columns={"patientunitstayid": "stay_id", "cellvaluenumeric": "valuenum"})
    uo["itemid"] = _URINE_CANONICAL
    uo["valuenum"] = uo["valuenum"].astype(float)

    return pd.concat([cr[_LABS_COLS], uo[_LABS_COLS]], ignore_index=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract_eicu.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Lint/type + whole suite**

Run: `uv run pytest -q`, `uv run ruff check src/rrt_liberation/extract/ tests/test_extract_eicu.py`, `uv run mypy src/rrt_liberation/extract/eicu.py`. Clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/extract/eicu.py tools/rrt-liberation/tests/test_extract_eicu.py
git commit -m "feat(rrt): add eICU labs extraction (creatinine + urine, string-match)"
```

---

## Task 3: `build_eicu_flags`

**Files:**
- Modify: `src/rrt_liberation/extract/eicu.py` (replace the `build_eicu_flags` stub)
- Test: `tests/test_extract_eicu.py` (add)

- [ ] **Step 1: Write the failing test** — append to `tests/test_extract_eicu.py`:

```python
from rrt_liberation.extract import build_eicu_flags


def test_flags_derivation():
    stays = pd.DataFrame({"patientunitstayid": [10, 20]})
    diagnosis = pd.DataFrame(
        {"patientunitstayid": [10], "diagnosisstring": ["sepsis|septic shock"]}
    )
    infusiondrug = pd.DataFrame({"patientunitstayid": [20], "drugname": ["Norepinephrine 4 mg"]})
    respiratorycare = pd.DataFrame({"patientunitstayid": [10]})
    flags = build_eicu_flags(
        stays, diagnosis, infusiondrug, respiratorycare,
        septic_shock_terms=["septic shock"], vasopressor_terms=["norepinephrine"],
        vent_terms=["ventilator"],
    )
    assert list(flags.columns) == [
        "stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"
    ]
    by = flags.set_index("stay_id")
    assert by.loc[10, "sepsis_shock"] == 1 and by.loc[20, "sepsis_shock"] == 0
    assert by.loc[20, "vasopressor"] == 1 and by.loc[10, "vasopressor"] == 0
    assert by.loc[10, "mechanical_ventilation"] == 1 and by.loc[20, "mechanical_ventilation"] == 0
    assert len(flags) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract_eicu.py::test_flags_derivation -q`
Expected: FAIL (NotImplementedError from the stub)

- [ ] **Step 3: Implement** — replace the `build_eicu_flags` stub with:

```python
def build_eicu_flags(
    stays: pd.DataFrame,
    diagnosis: pd.DataFrame,
    infusiondrug: pd.DataFrame,
    respiratorycare: pd.DataFrame,
    septic_shock_terms: Sequence[str],
    vasopressor_terms: Sequence[str],
    vent_terms: Sequence[str],
) -> pd.DataFrame:
    """Per-stay binary flags from eICU string tables.

    Ventilation is flagged by presence of a respiratorycare row for the stay;
    `vent_terms` is reserved for a future string-column filter.
    """
    out = pd.DataFrame({"stay_id": stays["patientunitstayid"].drop_duplicates().to_numpy()})

    shock_stays = set(
        diagnosis[_contains_any(diagnosis["diagnosisstring"], septic_shock_terms)][
            "patientunitstayid"
        ]
    )
    out["sepsis_shock"] = out["stay_id"].isin(shock_stays).astype(int)

    vaso_stays = set(
        infusiondrug[_contains_any(infusiondrug["drugname"], vasopressor_terms)][
            "patientunitstayid"
        ]
    )
    out["vasopressor"] = out["stay_id"].isin(vaso_stays).astype(int)

    vent_stays = set(respiratorycare["patientunitstayid"]) if not respiratorycare.empty else set()
    out["mechanical_ventilation"] = out["stay_id"].isin(vent_stays).astype(int)

    return out[["stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"]]
```

NOTE: `vent_terms` is intentionally accepted but unused in this skeleton (reserved). If ruff's unused-argument rule is enabled and flags it, prefix a no-op reference `_ = vent_terms` at the top of the function body and report it; with the default ruff config it is not flagged.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract_eicu.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Lint/type + whole suite**

Run: `uv run pytest -q`, `uv run ruff check src/rrt_liberation/extract/ tests/test_extract_eicu.py`, `uv run mypy src/rrt_liberation/extract/eicu.py`. Clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/extract/eicu.py tools/rrt-liberation/tests/test_extract_eicu.py
git commit -m "feat(rrt): add eICU flags extraction (septic shock/vasopressor/ventilation)"
```

---

## Task 4: CLI + config + extract→eICU-analysis integration

**Files:**
- Create: `pipeline/extract_eicu.py`
- Create: `conf/extract_eicu.yaml`
- Modify: `tests/test_extract_eicu.py` (add integration test)
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Write the failing integration test** — append to `tests/test_extract_eicu.py`:

```python
from rrt_liberation.cohort import CohortFactory
from rrt_liberation.features import build_features

SIX = [
    "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
    "sepsis_shock", "vasopressor", "mechanical_ventilation",
]


def _synthetic_eicu_raw(n_stays=8):
    treat, lab, io, dx, inf, resp, pat = [], [], [], [], [], [], []
    for i in range(n_stays):
        pid = 5000 + i
        pat.append({"patientunitstayid": pid})
        # CRRT on 0-1440 min (24h); even stays restart at 96h within 7d
        treat.append({"patientunitstayid": pid, "treatmentstring": "renal|CVVHDF",
                      "treatmentoffset": 0, "treatmentstopoffset": 1440})
        if i % 2 == 0:
            r0 = (24 + 72) * 60
            treat.append({"patientunitstayid": pid, "treatmentstring": "renal|CVVHDF",
                          "treatmentoffset": r0, "treatmentstopoffset": r0 + 1440})
        lab.append({"patientunitstayid": pid, "labname": "creatinine", "labresult": float(1.0 + 0.1 * i)})
        io.append({"patientunitstayid": pid, "celllabel": "Urine", "cellvaluenumeric": float(400 + 40 * i)})
        if i % 3 == 0:
            dx.append({"patientunitstayid": pid, "diagnosisstring": "septic shock"})
        if i % 2 == 0:
            inf.append({"patientunitstayid": pid, "drugname": "Norepinephrine"})
        if i % 2 == 1:
            resp.append({"patientunitstayid": pid})
    return (
        pd.DataFrame(treat), pd.DataFrame(lab), pd.DataFrame(io), pd.DataFrame(dx),
        pd.DataFrame(inf), pd.DataFrame(resp), pd.DataFrame(pat),
    )


def test_extract_then_build_features(tmp_path):
    treat, lab, io, dx, inf, resp, pat = _synthetic_eicu_raw()
    events = build_eicu_crrt_events(treat, ["cvvhdf"], 360.0)
    labs = build_eicu_labs(lab, io, ["creatinine"], ["urine"])
    flags = build_eicu_flags(
        pat, dx, inf, resp, ["septic shock"], ["norepinephrine"], ["ventilator"]
    )

    builder = CohortFactory("eicu")(min_off_hours=24.0)
    cohort = builder.build(events=events, horizon_hours=7 * 24)
    sources = {"labs": labs, "events": builder.to_canonical_events(events), "flags": flags}
    feats = build_features(cohort, sources, SIX)
    for col in SIX:
        assert col in feats.columns
    assert len(feats) == len(cohort) and len(cohort) > 0
```

- [ ] **Step 2: Run test to verify it fails / passes**

Run: `uv run pytest tests/test_extract_eicu.py::test_extract_then_build_features -q`
This exercises the extract→eICU-cohort→features handoff. The builders already exist (Tasks 1-3), so it should PASS once they are in place. If the cohort is empty (`len(cohort) > 0` fails), the synthetic CRRT intervals did not produce a liberation attempt — every stay has CRRT 0-1440min then a >=24h off period, which yields at least one attempt; if empty, widen the off period and report. Expected: PASS.

- [ ] **Step 3: Create `pipeline/extract_eicu.py`**

```python
"""Extract eICU-CRD raw tables into the pipeline input CSVs."""

from __future__ import annotations

import logging
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.extract import (
    build_eicu_crrt_events,
    build_eicu_flags,
    build_eicu_labs,
)
from rrt_liberation.utils import write_csv

logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../conf", config_name="extract_eicu")
def main(cfg: DictConfig) -> None:
    raw = cfg.raw
    treatment = pd.read_csv(raw.treatment)
    lab = pd.read_csv(raw.lab)
    intakeoutput = pd.read_csv(raw.intakeoutput)
    diagnosis = pd.read_csv(raw.diagnosis)
    infusiondrug = pd.read_csv(raw.infusiondrug)
    respiratorycare = pd.read_csv(raw.respiratorycare)
    patient = pd.read_csv(raw.patient)

    out = Path(cfg.paths.output_dir)
    write_csv(
        build_eicu_crrt_events(treatment, list(cfg.terms.crrt), cfg.merge_gap_minutes),
        out / "crrt_events.csv",
    )
    write_csv(
        build_eicu_labs(lab, intakeoutput, list(cfg.terms.creatinine), list(cfg.terms.urine)),
        out / "labs.csv",
    )
    write_csv(
        build_eicu_flags(
            patient, diagnosis, infusiondrug, respiratorycare,
            list(cfg.terms.septic_shock), list(cfg.terms.vasopressor), list(cfg.terms.ventilation),
        ),
        out / "flags.csv",
    )
    logger.info("Wrote canonical eICU CSVs to %s", out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create `conf/extract_eicu.yaml`**

```yaml
raw:
  treatment: ${paths.data_dir}/eicu_raw/treatment.csv
  lab: ${paths.data_dir}/eicu_raw/lab.csv
  intakeoutput: ${paths.data_dir}/eicu_raw/intakeOutput.csv
  diagnosis: ${paths.data_dir}/eicu_raw/diagnosis.csv
  infusiondrug: ${paths.data_dir}/eicu_raw/infusionDrug.csv
  respiratorycare: ${paths.data_dir}/eicu_raw/respiratoryCare.csv
  patient: ${paths.data_dir}/eicu_raw/patient.csv
terms:
  crrt: ["cvvh", "cvvhd", "cvvhdf", "crrt", "continuous renal replacement", "scuf"]
  creatinine: ["creatinine"]
  urine: ["urine", "foley", "void"]
  septic_shock: ["septic shock"]
  vasopressor: ["norepinephrine", "epinephrine", "vasopressin", "dopamine", "phenylephrine"]
  ventilation: ["ventilator", "mechanical vent", "intubat"]
merge_gap_minutes: 360.0
paths:
  data_dir: data
  output_dir: ${paths.data_dir}/eicu
```

- [ ] **Step 5: Run integration + whole suite**

Run: `uv run pytest tests/test_extract_eicu.py -q` then `uv run pytest -q`. All pass.

- [ ] **Step 6: Update README** — read `tools/rrt-liberation/README.md`. Find the line `Extract real MIMIC-IV (local, credentialed):` (added by sub-project G). Insert IMMEDIATELY AFTER its `-> writes ...` line (keep a blank line) this paragraph:

```markdown
Extract real eICU-CRD (local, credentialed): `uv run python -m pipeline.extract_eicu`
-> writes `data/eicu/{crrt_events,labs,flags}.csv` from raw eICU tables (configure
paths/terms in `conf/extract_eicu.yaml`; verify term lists + CRRT stop-offset handling
against your eICU version).
```

- [ ] **Step 7: Verification sweep + PHI + commit**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
uv run ruff check .
uv run mypy src pipeline tests
uv run pytest -q
```
All clean/green; report counts.

```bash
cd /Users/llmmkkooii/github/pushtest
git ls-files tools/rrt-liberation/ | grep -E '(data|outputs)/' || echo "clean"
git add tools/rrt-liberation/pipeline/extract_eicu.py tools/rrt-liberation/conf/extract_eicu.yaml tools/rrt-liberation/tests/test_extract_eicu.py tools/rrt-liberation/README.md
git commit -m "feat(rrt): add extract_eicu CLI + config; document eICU extraction"
```

---

## Definition of Done

- `build_eicu_crrt_events` / `build_eicu_labs` / `build_eicu_flags` produce the exact expected schemas (eICU-shaped events; canonical labs/flags), tested on synthetic raw tables.
- The extract→analysis chain works: extracted eICU CSVs feed `CohortFactory("eicu").build` + `build_features` to produce the 6 features (`test_extract_then_build_features`).
- `uv run python -m pipeline.extract_eicu` is a valid Hydra entry.
- `uv run pytest -q` green; `ruff check .` and `mypy src pipeline tests` clean.
- `data/`/`outputs/` gitignored (incl. `data/eicu_raw/`); no credentialed data committed.
- Existing analysis modules, `extract/mimic.py`, and all prior tests unchanged.
- Real-eICU verification is explicitly the user's local task (documented); term lists + CRRT stop-offset handling are config defaults to confirm.

---

## Self-Review

- **Spec coverage:** §1 decisions (string-match, eICU-shaped events, dedicated CLI, config defaults) → Tasks 1-4 ✓. §2 architecture (eicu.py, __init__, extract_eicu.py, conf, tests) ✓. §3 three transforms (crrt offset-merge / labs string→canonical itemids / flags string-match via stay) → Tasks 1,2,3 ✓. §4 config/CLI → Task 4 ✓. §5 tests incl. extract→eICU-analysis integration → Task 4 ✓.
- **Placeholder scan:** none — full code each step. (Task-1 NotImplementedError stubs for labs/flags are a sequencing device replaced in Tasks 2-3.)
- **Type consistency:** `build_eicu_crrt_events(treatment, crrt_terms, merge_gap_minutes)`, `build_eicu_labs(lab, intakeoutput, creatinine_terms, urine_terms)`, `build_eicu_flags(stays, diagnosis, infusiondrug, respiratorycare, septic_shock_terms, vasopressor_terms, vent_terms)` — signatures consistent across tests, impl, and `extract_eicu.py` main. Output columns match the pipeline's eICU-events / canonical labs / canonical flags schemas exactly. `_contains_any` reused by all three. Canonical itemids 226559/50912 consistent. The integration test uses `CohortFactory("eicu").build` + `to_canonical_events` for `sources["events"]`, matching how validate/benchmark already consume eICU.
- **Caveat honesty:** integration verifies the extract→analysis handoff on synthetic raw tables; real eICU term lists, CRRT stop-offset handling, and values are unverifiable here and are the user's local responsibility (documented in spec §0 + README).
