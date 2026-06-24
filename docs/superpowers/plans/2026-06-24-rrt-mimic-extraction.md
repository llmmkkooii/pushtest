# MIMIC-IV Extraction Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-pandas MIMIC-IV extraction layer that turns raw module tables into the three canonical CSVs (`crrt_events`, `labs`, `flags`) the analysis pipeline consumes.

**Architecture:** Three pure transform functions in `src/rrt_liberation/extract/mimic.py` (raw DataFrame → canonical DataFrame), tested with small synthetic raw tables that mimic the MIMIC schema. A `pipeline/extract_mimic.py` Hydra entry loads real raw tables locally and writes the 3 CSVs. NO real-data verification is possible here — only schema conformance + synthetic-table logic tests; the user runs it on credentialed MIMIC locally.

**Tech Stack:** Python 3.11, uv, pandas, Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-24-rrt-mimic-extraction-design.md](../specs/2026-06-24-rrt-mimic-extraction-design.md)

**Working dir:** paths relative to `tools/rrt-liberation/`. Branch `feature/rrt-mimic-extraction`. Run via `uv run`.

**Conventions:** pure functions, type hints, module logger (no `print`), `__all__`, files 200-400 lines. Existing `src/` analysis modules, all pipeline entrypoints, and all prior tests stay unchanged (extraction is a new upstream layer).

**Canonical output schemas (must match exactly — the pipeline already consumes these):**
- `crrt_events`: columns `subject_id, stay_id, starttime, endtime, modality`.
- `labs`: columns `stay_id, itemid, valuenum` (urine emitted as itemid 226559, creatinine as 50912).
- `flags`: columns `stay_id, sepsis_shock, vasopressor, mechanical_ventilation` (0/1, one row per stay).

**Assumed raw-table columns (MIMIC-IV-like; the loader/user supplies these):**
- `procedureevents`: `subject_id, stay_id, itemid, starttime, endtime`.
- `outputevents`: `stay_id, itemid, value`.
- `labevents`: `subject_id, itemid, valuenum, charttime`.
- `icustays` (a.k.a. `stays`): `subject_id, hadm_id, stay_id, intime, outtime`.
- `diagnoses_icd`: `hadm_id, icd_code`.
- `inputevents`: `stay_id, itemid`.
- `ventilation`: `stay_id, itemid`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/rrt_liberation/extract/__init__.py` | export the 3 builders |
| `src/rrt_liberation/extract/mimic.py` | `build_mimic_crrt_events`, `build_mimic_labs`, `build_mimic_flags` |
| `pipeline/extract_mimic.py` | Hydra loader → 3 builders → write CSVs |
| `conf/extract_mimic.yaml` | raw paths, itemids/codes, merge_gap, output dir |
| `tests/test_extract_mimic.py` | per-builder unit tests + extract→cohort→features integration |

---

## Task 1: `build_mimic_crrt_events` (episode reconstruction)

**Files:**
- Create: `src/rrt_liberation/extract/__init__.py`
- Create: `src/rrt_liberation/extract/mimic.py`
- Test: `tests/test_extract_mimic.py`

- [ ] **Step 1: Write the failing test** `tests/test_extract_mimic.py`:

```python
import pandas as pd

from rrt_liberation.extract import build_mimic_crrt_events

T0 = pd.Timestamp("2150-01-01")


def _proc(rows):
    # rows: (stay_id, itemid, start_h, end_h)
    return pd.DataFrame(
        [
            {
                "subject_id": 1,
                "stay_id": s,
                "itemid": it,
                "starttime": T0 + pd.Timedelta(hours=sh),
                "endtime": T0 + pd.Timedelta(hours=eh),
            }
            for (s, it, sh, eh) in rows
        ]
    )


def test_filters_non_crrt_itemids():
    proc = _proc([(1, 225802, 0, 24), (1, 999999, 0, 24)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert list(ev.columns) == ["subject_id", "stay_id", "starttime", "endtime", "modality"]
    assert len(ev) == 1
    assert ev.iloc[0]["modality"] == "CRRT"


def test_merges_within_gap():
    # two fragments 0-2h and 4-6h; gap = 2h <= 6h merge -> one interval 0-6h
    proc = _proc([(1, 225802, 0, 2), (1, 225802, 4, 6)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert len(ev) == 1
    assert ev.iloc[0]["starttime"] == T0
    assert ev.iloc[0]["endtime"] == T0 + pd.Timedelta(hours=6)


def test_splits_beyond_gap():
    # gap = 2h > 1h threshold -> two intervals
    proc = _proc([(1, 225802, 0, 2), (1, 225802, 4, 6)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=1.0)
    assert len(ev) == 2


def test_separate_stays_not_merged():
    proc = _proc([(1, 225802, 0, 2), (2, 225802, 3, 5)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert set(ev["stay_id"]) == {1, 2}
    assert len(ev) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract_mimic.py -q`
Expected: FAIL (`ModuleNotFoundError: rrt_liberation.extract`)

- [ ] **Step 3: Implement**

`src/rrt_liberation/extract/mimic.py`:

```python
"""MIMIC-IV extraction: raw module tables -> canonical pipeline CSVs (pure pandas)."""

from __future__ import annotations

import logging
from typing import List, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

_EVENTS_COLS = ["subject_id", "stay_id", "starttime", "endtime", "modality"]
_URINE_CANONICAL = 226559
_CREATININE_CANONICAL = 50912


def build_mimic_crrt_events(
    procedureevents: pd.DataFrame,
    crrt_itemids: Sequence[int],
    merge_gap_hours: float = 6.0,
) -> pd.DataFrame:
    """CRRT on-intervals per stay, merging fragments within merge_gap_hours."""
    crrt = procedureevents[procedureevents["itemid"].isin(list(crrt_itemids))].copy()
    if crrt.empty:
        return pd.DataFrame(columns=_EVENTS_COLS)
    crrt["starttime"] = pd.to_datetime(crrt["starttime"])
    crrt["endtime"] = pd.to_datetime(crrt["endtime"])
    gap = pd.Timedelta(hours=merge_gap_hours)

    rows: List[dict] = []
    for stay_id, grp in crrt.sort_values("starttime").groupby("stay_id"):
        subject_id = grp["subject_id"].iloc[0]
        cur_start = cur_end = None
        for _, r in grp.iterrows():
            s, e = r["starttime"], r["endtime"]
            if cur_start is None:
                cur_start, cur_end = s, e
            elif s <= cur_end + gap:
                cur_end = max(cur_end, e)
            else:
                rows.append(
                    {"subject_id": subject_id, "stay_id": stay_id,
                     "starttime": cur_start, "endtime": cur_end, "modality": "CRRT"}
                )
                cur_start, cur_end = s, e
        rows.append(
            {"subject_id": subject_id, "stay_id": stay_id,
             "starttime": cur_start, "endtime": cur_end, "modality": "CRRT"}
        )
    return pd.DataFrame(rows, columns=_EVENTS_COLS)
```

`src/rrt_liberation/extract/__init__.py`:

```python
from rrt_liberation.extract.mimic import (
    build_mimic_crrt_events,
    build_mimic_flags,
    build_mimic_labs,
)

__all__ = ["build_mimic_crrt_events", "build_mimic_labs", "build_mimic_flags"]
```

NOTE: `__init__.py` imports `build_mimic_labs`/`build_mimic_flags` which are added in Tasks 2-3. To keep THIS task importable/green in isolation, ALSO add minimal stubs to `mimic.py` now so the package imports:

```python
def build_mimic_labs(*args: object, **kwargs: object) -> pd.DataFrame:
    raise NotImplementedError("build_mimic_labs is implemented in Task 2")


def build_mimic_flags(*args: object, **kwargs: object) -> pd.DataFrame:
    raise NotImplementedError("build_mimic_flags is implemented in Task 2")
```

(Tasks 2 and 3 REPLACE these stubs with real implementations.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract_mimic.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Whole suite + lint/type**

Run: `uv run pytest -q` (no regressions), `uv run ruff check src/rrt_liberation/extract/ tests/test_extract_mimic.py`, `uv run mypy src/rrt_liberation/extract/mimic.py`. All clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/extract tools/rrt-liberation/tests/test_extract_mimic.py
git commit -m "feat(rrt): add MIMIC CRRT-event extraction (episode reconstruction)"
```

---

## Task 2: `build_mimic_labs`

**Files:**
- Modify: `src/rrt_liberation/extract/mimic.py` (replace the `build_mimic_labs` stub)
- Test: `tests/test_extract_mimic.py` (add)

- [ ] **Step 1: Write the failing test** — append to `tests/test_extract_mimic.py`:

```python
from rrt_liberation.extract import build_mimic_labs


def test_labs_urine_and_creatinine_canonical():
    outputevents = pd.DataFrame(
        {"stay_id": [10, 10], "itemid": [226559, 999], "value": [800.0, 5.0]}
    )
    labevents = pd.DataFrame(
        {
            "subject_id": [1, 1],
            "itemid": [50912, 50912],
            "valuenum": [1.2, 3.4],
            "charttime": [T0 + pd.Timedelta(hours=1), T0 + pd.Timedelta(days=10)],
        }
    )
    stays = pd.DataFrame(
        {
            "subject_id": [1],
            "hadm_id": [100],
            "stay_id": [10],
            "intime": [T0],
            "outtime": [T0 + pd.Timedelta(days=2)],
        }
    )
    labs = build_mimic_labs(
        outputevents, labevents, stays, urine_itemids=[226559], creatinine_itemids=[50912]
    )
    assert list(labs.columns) == ["stay_id", "itemid", "valuenum"]
    # urine: only the 226559 row, canonicalized to 226559
    urine = labs[labs["itemid"] == 226559]
    assert len(urine) == 1 and urine.iloc[0]["valuenum"] == 800.0
    # creatinine: only the in-stay measurement (1h, within [T0, T0+2d]); the day-10 one is dropped
    cr = labs[labs["itemid"] == 50912]
    assert len(cr) == 1 and cr.iloc[0]["valuenum"] == 1.2
    assert cr.iloc[0]["stay_id"] == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract_mimic.py::test_labs_urine_and_creatinine_canonical -q`
Expected: FAIL (NotImplementedError from the stub)

- [ ] **Step 3: Implement** — replace the `build_mimic_labs` stub in `src/rrt_liberation/extract/mimic.py` with:

```python
def build_mimic_labs(
    outputevents: pd.DataFrame,
    labevents: pd.DataFrame,
    stays: pd.DataFrame,
    urine_itemids: Sequence[int],
    creatinine_itemids: Sequence[int],
) -> pd.DataFrame:
    """Canonical labs: urine (outputevents -> 226559) + creatinine (labevents -> 50912)."""
    cols = ["stay_id", "itemid", "valuenum"]

    uo = outputevents[outputevents["itemid"].isin(list(urine_itemids))][["stay_id", "value"]].copy()
    uo = uo.rename(columns={"value": "valuenum"})
    uo["itemid"] = _URINE_CANONICAL
    uo["valuenum"] = uo["valuenum"].astype(float)

    cr = labevents[labevents["itemid"].isin(list(creatinine_itemids))].copy()
    cr["charttime"] = pd.to_datetime(cr["charttime"])
    st = stays[["subject_id", "stay_id", "intime", "outtime"]].copy()
    st["intime"] = pd.to_datetime(st["intime"])
    st["outtime"] = pd.to_datetime(st["outtime"])
    merged = cr.merge(st, on="subject_id", how="inner")
    in_stay = merged[
        (merged["charttime"] >= merged["intime"]) & (merged["charttime"] <= merged["outtime"])
    ]
    cr_out = in_stay[["stay_id"]].copy()
    cr_out["itemid"] = _CREATININE_CANONICAL
    cr_out["valuenum"] = in_stay["valuenum"].astype(float).to_numpy()

    return pd.concat([uo[cols], cr_out[cols]], ignore_index=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract_mimic.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Lint/type + whole suite**

Run: `uv run pytest -q`, `uv run ruff check src/rrt_liberation/extract/ tests/test_extract_mimic.py`, `uv run mypy src/rrt_liberation/extract/mimic.py`. Clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/extract/mimic.py tools/rrt-liberation/tests/test_extract_mimic.py
git commit -m "feat(rrt): add MIMIC labs extraction (urine + creatinine, stay assignment)"
```

---

## Task 3: `build_mimic_flags`

**Files:**
- Modify: `src/rrt_liberation/extract/mimic.py` (replace the `build_mimic_flags` stub)
- Test: `tests/test_extract_mimic.py` (add)

- [ ] **Step 1: Write the failing test** — append to `tests/test_extract_mimic.py`:

```python
from rrt_liberation.extract import build_mimic_flags


def test_flags_derivation():
    stays = pd.DataFrame(
        {"subject_id": [1, 2], "hadm_id": [100, 200], "stay_id": [10, 20],
         "intime": [T0, T0], "outtime": [T0 + pd.Timedelta(days=2)] * 2}
    )
    diagnoses_icd = pd.DataFrame({"hadm_id": [100], "icd_code": ["R6521"]})  # stay 10 only
    inputevents = pd.DataFrame({"stay_id": [20], "itemid": [221906]})        # stay 20 vasopressor
    ventilation = pd.DataFrame({"stay_id": [10], "itemid": [225792]})        # stay 10 vent
    flags = build_mimic_flags(
        stays, diagnoses_icd, inputevents, ventilation,
        septic_shock_icd=["R6521"], vasopressor_itemids=[221906], vent_itemids=[225792],
    )
    assert list(flags.columns) == [
        "stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"
    ]
    by = flags.set_index("stay_id")
    assert by.loc[10, "sepsis_shock"] == 1 and by.loc[20, "sepsis_shock"] == 0
    assert by.loc[20, "vasopressor"] == 1 and by.loc[10, "vasopressor"] == 0
    assert by.loc[10, "mechanical_ventilation"] == 1 and by.loc[20, "mechanical_ventilation"] == 0
    assert len(flags) == 2  # one row per stay
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract_mimic.py::test_flags_derivation -q`
Expected: FAIL (NotImplementedError from the stub)

- [ ] **Step 3: Implement** — replace the `build_mimic_flags` stub with:

```python
def build_mimic_flags(
    stays: pd.DataFrame,
    diagnoses_icd: pd.DataFrame,
    inputevents: pd.DataFrame,
    ventilation: pd.DataFrame,
    septic_shock_icd: Sequence[str],
    vasopressor_itemids: Sequence[int],
    vent_itemids: Sequence[int],
) -> pd.DataFrame:
    """Per-stay binary flags: septic shock (ICD via hadm), vasopressor, ventilation."""
    out = pd.DataFrame({"stay_id": stays["stay_id"].drop_duplicates().to_numpy()})

    shock_codes = {str(c) for c in septic_shock_icd}
    shock_hadm = set(
        diagnoses_icd[diagnoses_icd["icd_code"].astype(str).isin(shock_codes)]["hadm_id"]
    )
    stay_hadm = stays[["stay_id", "hadm_id"]].drop_duplicates().copy()
    stay_hadm["sepsis_shock"] = stay_hadm["hadm_id"].isin(shock_hadm).astype(int)
    out = out.merge(stay_hadm[["stay_id", "sepsis_shock"]], on="stay_id", how="left")
    out["sepsis_shock"] = out["sepsis_shock"].fillna(0).astype(int)

    vaso_stays = set(inputevents[inputevents["itemid"].isin(list(vasopressor_itemids))]["stay_id"])
    out["vasopressor"] = out["stay_id"].isin(vaso_stays).astype(int)

    vent_stays = set(ventilation[ventilation["itemid"].isin(list(vent_itemids))]["stay_id"])
    out["mechanical_ventilation"] = out["stay_id"].isin(vent_stays).astype(int)

    return out[["stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract_mimic.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Lint/type + whole suite**

Run: `uv run pytest -q`, `uv run ruff check src/rrt_liberation/extract/ tests/test_extract_mimic.py`, `uv run mypy src/rrt_liberation/extract/mimic.py`. Clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/extract/mimic.py tools/rrt-liberation/tests/test_extract_mimic.py
git commit -m "feat(rrt): add MIMIC flags extraction (septic shock/vasopressor/ventilation)"
```

---

## Task 4: CLI + config + extract→analysis integration

**Files:**
- Create: `pipeline/extract_mimic.py`
- Create: `conf/extract_mimic.yaml`
- Modify: `tests/test_extract_mimic.py` (add integration test)
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Write the failing integration test** — append to `tests/test_extract_mimic.py`:

```python
import numpy as np

from pipeline.run import run_pipeline


def _synthetic_mimic_raw(n_stays=12):
    """Synthetic raw MIMIC tables that yield a 2-class liberation cohort after extraction."""
    proc, outp, lab, dx, inp, vent, stays = [], [], [], [], [], [], []
    for i in range(n_stays):
        subj, hadm, stay = 1000 + i, 2000 + i, 3000 + i
        stays.append({"subject_id": subj, "hadm_id": hadm, "stay_id": stay,
                      "intime": T0, "outtime": T0 + pd.Timedelta(days=30)})
        # CRRT on 0-24h
        proc.append({"subject_id": subj, "stay_id": stay, "itemid": 225802,
                     "starttime": T0, "endtime": T0 + pd.Timedelta(hours=24)})
        if i % 2 == 0:  # restart within 7d -> failure attempt; trailing off -> success
            r0 = 24 + 72
            proc.append({"subject_id": subj, "stay_id": stay, "itemid": 225802,
                         "starttime": T0 + pd.Timedelta(hours=r0),
                         "endtime": T0 + pd.Timedelta(hours=r0 + 24)})
        outp.append({"stay_id": stay, "itemid": 226559, "value": float(400 + 50 * i)})
        lab.append({"subject_id": subj, "itemid": 50912, "valuenum": float(1.0 + 0.1 * i),
                    "charttime": T0 + pd.Timedelta(hours=2)})
        if i % 3 == 0:
            dx.append({"hadm_id": hadm, "icd_code": "R6521"})
        if i % 2 == 0:
            inp.append({"stay_id": stay, "itemid": 221906})
        if i % 2 == 1:
            vent.append({"stay_id": stay, "itemid": 225792})
    return (
        pd.DataFrame(proc), pd.DataFrame(outp), pd.DataFrame(lab),
        pd.DataFrame(dx), pd.DataFrame(inp), pd.DataFrame(vent), pd.DataFrame(stays),
    )


def test_extract_then_train(tmp_path):
    from rrt_liberation.extract import (
        build_mimic_crrt_events,
        build_mimic_flags,
        build_mimic_labs,
    )

    proc, outp, lab, dx, inp, vent, stays = _synthetic_mimic_raw()
    data = tmp_path / "data" / "mimic"
    data.mkdir(parents=True)
    build_mimic_crrt_events(proc, [225802], 6.0).to_csv(data / "crrt_events.csv", index=False)
    build_mimic_labs(outp, lab, stays, [226559], [50912]).to_csv(data / "labs.csv", index=False)
    build_mimic_flags(
        stays, dx, inp, vent, ["R6521"], [221906], [225792]
    ).to_csv(data / "flags.csv", index=False)

    # The extracted CSVs feed the existing analysis pipeline unchanged.
    result = run_pipeline(
        events_csv=data / "crrt_events.csv",
        labs_csv=data / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=[
            "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
            "sepsis_shock", "vasopressor", "mechanical_ventilation",
        ],
        model_name="logistic",
        coefficients={},
        output_dir=tmp_path / "out",
        seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        n_boot=10,
        flags_csv=data / "flags.csv",
    )
    assert "auroc_corrected" in result and result["n_boot_used"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract_mimic.py::test_extract_then_train -q`
Expected: FAIL if the 2-class generator does not yield two classes (ValueError "requires two outcome classes"). If it fails for that reason, the generator needs both classes — the `i % 2 == 0` patients produce a within-7d-restart failure attempt plus a trailing success, and odd patients produce a single success; that yields both classes. If you still get a single class, widen the restart pattern (e.g. make every even patient restart) and report. Otherwise this step's "failure" is simply that the test is new and exercises the full chain — run it and confirm it PASSES once Tasks 1-3 are done (the builders already exist). If it passes immediately, that is acceptable for this integration test (no new src code is required for it).

- [ ] **Step 3: Create `pipeline/extract_mimic.py`**

```python
"""Extract MIMIC-IV raw tables into the canonical pipeline CSVs."""

from __future__ import annotations

import logging
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.extract import (
    build_mimic_crrt_events,
    build_mimic_flags,
    build_mimic_labs,
)
from rrt_liberation.utils import write_csv

logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../conf", config_name="extract_mimic")
def main(cfg: DictConfig) -> None:
    raw = cfg.raw
    procedureevents = pd.read_csv(raw.procedureevents)
    outputevents = pd.read_csv(raw.outputevents)
    labevents = pd.read_csv(raw.labevents)
    diagnoses_icd = pd.read_csv(raw.diagnoses_icd)
    inputevents = pd.read_csv(raw.inputevents)
    ventilation = pd.read_csv(raw.ventilation)
    stays = pd.read_csv(raw.icustays)

    out = Path(cfg.paths.output_dir)
    write_csv(
        build_mimic_crrt_events(procedureevents, list(cfg.itemids.crrt), cfg.merge_gap_hours),
        out / "crrt_events.csv",
    )
    write_csv(
        build_mimic_labs(
            outputevents, labevents, stays,
            list(cfg.itemids.urine), list(cfg.itemids.creatinine),
        ),
        out / "labs.csv",
    )
    write_csv(
        build_mimic_flags(
            stays, diagnoses_icd, inputevents, ventilation,
            list(cfg.codes.septic_shock_icd), list(cfg.itemids.vasopressor),
            list(cfg.itemids.ventilation),
        ),
        out / "flags.csv",
    )
    logger.info("Wrote canonical MIMIC CSVs to %s", out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create `conf/extract_mimic.yaml`**

```yaml
raw:
  procedureevents: ${paths.data_dir}/mimic_raw/procedureevents.csv
  outputevents: ${paths.data_dir}/mimic_raw/outputevents.csv
  labevents: ${paths.data_dir}/mimic_raw/labevents.csv
  diagnoses_icd: ${paths.data_dir}/mimic_raw/diagnoses_icd.csv
  inputevents: ${paths.data_dir}/mimic_raw/inputevents.csv
  ventilation: ${paths.data_dir}/mimic_raw/ventilation.csv
  icustays: ${paths.data_dir}/mimic_raw/icustays.csv
itemids:
  crrt: [225802, 225803, 225805, 225809]
  urine: [226559, 226560, 227510]
  creatinine: [50912]
  vasopressor: [221906, 221289, 222315, 221662, 221749]
  ventilation: [225792, 225794]
codes:
  septic_shock_icd: ["R6521", "78552"]
merge_gap_hours: 6.0
paths:
  data_dir: data
  output_dir: ${paths.data_dir}/mimic
```

- [ ] **Step 5: Run the integration test + whole suite**

Run: `uv run pytest tests/test_extract_mimic.py -q` then `uv run pytest -q`.
Expected: all pass.

- [ ] **Step 6: Update README `## Status`** — add an extraction line. Read `tools/rrt-liberation/README.md` and insert, right before the existing `Run the dev model:` line, this paragraph:

```markdown
Extract real MIMIC-IV (local, credentialed): `uv run python -m pipeline.extract_mimic`
-> writes `data/mimic/{crrt_events,labs,flags}.csv` from raw module tables (configure
paths/itemids in `conf/extract_mimic.yaml`; verify itemids against your MIMIC version).
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
git add tools/rrt-liberation/pipeline/extract_mimic.py tools/rrt-liberation/conf/extract_mimic.yaml tools/rrt-liberation/tests/test_extract_mimic.py tools/rrt-liberation/README.md
git commit -m "feat(rrt): add extract_mimic CLI + config; document extraction"
```

---

## Definition of Done

- `build_mimic_crrt_events` / `build_mimic_labs` / `build_mimic_flags` produce the exact canonical schemas, tested on synthetic raw tables.
- The extract→analysis chain works: extracted CSVs train the logistic model (`test_extract_then_train`).
- `uv run python -m pipeline.extract_mimic` is a valid Hydra entry (CLI runs given configured raw paths).
- `uv run pytest -q` green; `ruff check .` and `mypy src pipeline tests` clean.
- `data/`/`outputs/` gitignored (incl. `data/mimic_raw/`); no credentialed data committed.
- Existing analysis modules and all prior tests unchanged.
- Real-MIMIC verification is explicitly the user's local task (documented); itemids/codes are config defaults to confirm.

---

## Self-Review

- **Spec coverage:** §1 decisions (pandas transforms, synthetic-raw TDD, dedicated CLI, config defaults) → Tasks 1-4 ✓. §2 architecture (extract package, extract_mimic.py, conf, tests) ✓. §3 three transforms (crrt merge / labs urine+cr with stay assignment / flags via hadm+stay) → Tasks 1,2,3 ✓. §4 config/CLI → Task 4 ✓. §5 tests incl. extract→analysis integration → Task 4 ✓.
- **Placeholder scan:** none — full code each step. (The Task-1 NotImplementedError stubs for labs/flags are an explicit sequencing device replaced in Tasks 2-3, not a plan placeholder.)
- **Type consistency:** `build_mimic_crrt_events(procedureevents, crrt_itemids, merge_gap_hours)`, `build_mimic_labs(outputevents, labevents, stays, urine_itemids, creatinine_itemids)`, `build_mimic_flags(stays, diagnoses_icd, inputevents, ventilation, septic_shock_icd, vasopressor_itemids, vent_itemids)` — signatures consistent across tests, impl, and `extract_mimic.py` main. Canonical output columns match the pipeline's expected `crrt_events`/`labs`/`flags` schemas exactly. Itemid constants 226559/50912 consistent.
- **Real-data caveat:** the integration test verifies the extract→analysis handoff on synthetic raw tables; real MIMIC itemids/values are unverifiable here and are the user's local responsibility (documented in spec §0 and README).
