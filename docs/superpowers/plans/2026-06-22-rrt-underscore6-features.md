# RRT UNDERSCORE-6 Feature Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the UNDERSCORE-6 predictor set via a DB-independent feature registry so the dev logistic model, UNDERSCORE benchmark, and eICU external validation all run on the real six variables (synthetic sources for both MIMIC and eICU).

**Architecture:** A feature registry (`register_feature`/`FEATURE_REGISTRY`) where each feature is `fn(cohort, sources) -> pd.Series` aligned to cohort rows. `build_features(cohort, sources, predictors)` drives it. Six features cover three types: lab aggregates (urine, baseline creatinine), an attempt-time-truncated duration (CRRT hours), and binary flags (sepsis shock, vasopressor, mechanical ventilation). Cohort builders gain `to_canonical_events` so the duration feature works on canonical events for both MIMIC and eICU. Pipelines assemble a `sources` dict. Synthetic data only; no credentialed data.

**Tech Stack:** Python 3.11, uv, pandas, numpy, sklearn (via the model), Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-22-rrt-underscore6-features-design.md](../specs/2026-06-22-rrt-underscore6-features-design.md)

**Working dir:** paths relative to `tools/rrt-liberation/` unless noted. Branch `feature/rrt-underscore6-features`. Run via `uv run`.

**Conventions:** files 200-400 lines, type hints, module logger (no `print`), `__all__`, registry pattern, seed fixed.

**Confirmed current state:**
- `build_features(cohort, labs, predictors)` currently has urine-only if/elif; `features/__init__.py` exports only `build_features`; `tests/test_features.py` calls `build_features(cohort, labs=labs, predictors=[...])`.
- `BaseCohortBuilder.build(events, horizon_hours)`; `MimicCohortBuilder` events are already canonical; `EicuCohortBuilder._to_canonical` converts eICU offsets (it has `_EICU_T0`).
- `run_pipeline(... predictors, ... cohort_name="mimic", model_hparams, n_boot, created_utc)` builds `feats = build_features(cohort, labs=labs, predictors=predictors)` then `y`. `pipeline/validate.py` `run_external_validation(...)` similarly calls `build_features(cohort, labs=labs, predictors=predictors)`.
- `conf/cohort/{mimic,eicu}.yaml` have name/min_off_hours/events_csv/labs_csv. `conf/features/baseline.yaml` lists `urine_output_24h`. `conf/model/underscore.yaml` has coefficients {intercept, urine_output_24h}.
- Fixtures: `make_two_class_labs`/`make_eicu_labs` emit canonical labs (stay_id/itemid 226559/valuenum). `make_two_class_events` stay_id=2000+i; `make_eicu_events` patientunitstayid=5000+i.

**Itemids:** urine=226559 (existing), creatinine=50912.

---

## File Structure

| File | Responsibility |
|---|---|
| `tests/fixtures/synth.py` | + creatinine rows in two_class/eicu labs; + `make_two_class_flags`/`make_eicu_flags` |
| `src/rrt_liberation/features/registry.py` | `FEATURE_REGISTRY`, `register_feature`, the 6 feature fns |
| `src/rrt_liberation/features/builder.py` | `build_features(cohort, sources, predictors)` (registry driver) |
| `src/rrt_liberation/features/__init__.py` | export build_features, register_feature, FEATURE_REGISTRY |
| `src/rrt_liberation/cohort/base.py` | + `to_canonical_events` (default identity) |
| `src/rrt_liberation/cohort/mimic.py` | build via `to_canonical_events` (identity) |
| `src/rrt_liberation/cohort/eicu.py` | `to_canonical_events` public (offset conversion); build via it |
| `conf/features/baseline.yaml`, `conf/model/underscore.yaml`, `conf/cohort/{mimic,eicu}.yaml` | 6 predictors / 6 coeffs / flags_csv |
| `pipeline/run.py`, `pipeline/validate.py` | assemble `sources`, optional `flags_csv` |
| `tests/test_*` | registry, features, canonical-events, smoke |

---

## Task 1: Extend fixtures (creatinine + flags)

**Files:**
- Modify: `tests/fixtures/synth.py`
- Test: `tests/test_underscore6_fixtures.py`

- [ ] **Step 1: Write the failing test** `tests/test_underscore6_fixtures.py`:

```python
from tests.fixtures.synth import (
    make_eicu_flags,
    make_eicu_labs,
    make_two_class_flags,
    make_two_class_labs,
)


def test_labs_include_creatinine():
    labs = make_two_class_labs(n_patients=24, seed=42)
    assert set(labs["itemid"].unique()) >= {226559, 50912}  # urine + creatinine
    elabs = make_eicu_labs(n_patients=24, seed=42)
    assert set(elabs["itemid"].unique()) >= {226559, 50912}


def test_flags_schema_and_values():
    flags = make_two_class_flags(n_patients=24, seed=42)
    assert list(flags.columns) == [
        "stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"
    ]
    for col in ["sepsis_shock", "vasopressor", "mechanical_ventilation"]:
        assert set(flags[col].unique()) <= {0, 1}
    eflags = make_eicu_flags(n_patients=24, seed=42)
    assert set(eflags["stay_id"]) == {5000 + i for i in range(24)}


def test_fixtures_deterministic():
    assert make_two_class_flags(10, seed=1).equals(make_two_class_flags(10, seed=1))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_underscore6_fixtures.py -v`
Expected: FAIL (`ImportError: cannot import name 'make_two_class_flags'`)

- [ ] **Step 3: Implement** — in `tests/fixtures/synth.py`:

(a) Replace the body of `make_two_class_labs` so each patient gets a urine row AND (for most) a creatinine row (some missing for imputation testing):

```python
def make_two_class_labs(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Urine + creatinine, canonical labs schema. Some creatinine missing."""
    rng = np.random.default_rng(seed + 7)
    rows = []
    for i in range(n_patients):
        sid, stid = 1000 + i, 2000 + i
        rows.append({"subject_id": sid, "stay_id": stid, "charttime": _T0,
                     "itemid": 226559, "valuenum": float(rng.integers(200, 1800))})
        if i % 5 != 0:  # ~20% of patients have no creatinine -> NaN feature
            rows.append({"subject_id": sid, "stay_id": stid, "charttime": _T0,
                         "itemid": 50912, "valuenum": float(rng.integers(50, 400)) / 100.0})
    return pd.DataFrame(rows)
```

(b) Replace the body of `make_eicu_labs` similarly (stay_id = 5000+i):

```python
def make_eicu_labs(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """eICU urine + creatinine, canonical labs schema. Some creatinine missing."""
    rng = np.random.default_rng(seed + 29)
    rows = []
    for i in range(n_patients):
        pid = 5000 + i
        rows.append({"subject_id": pid, "stay_id": pid, "charttime": _T0,
                     "itemid": 226559, "valuenum": float(rng.integers(200, 1800))})
        if i % 5 != 0:
            rows.append({"subject_id": pid, "stay_id": pid, "charttime": _T0,
                         "itemid": 50912, "valuenum": float(rng.integers(50, 400)) / 100.0})
    return pd.DataFrame(rows)
```

(c) Append two flag generators:

```python
def make_two_class_flags(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Canonical per-stay binary flags for the MIMIC two-class cohort."""
    rng = np.random.default_rng(seed + 13)
    rows = []
    for i in range(n_patients):
        rows.append({
            "stay_id": 2000 + i,
            "sepsis_shock": int(rng.integers(0, 2)),
            "vasopressor": int(rng.integers(0, 2)),
            "mechanical_ventilation": int(rng.integers(0, 2)),
        })
    return pd.DataFrame(rows)


def make_eicu_flags(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Canonical per-stay binary flags for the eICU cohort (stay_id == patientunitstayid)."""
    rng = np.random.default_rng(seed + 17)
    rows = []
    for i in range(n_patients):
        rows.append({
            "stay_id": 5000 + i,
            "sepsis_shock": int(rng.integers(0, 2)),
            "vasopressor": int(rng.integers(0, 2)),
            "mechanical_ventilation": int(rng.integers(0, 2)),
        })
    return pd.DataFrame(rows)
```

Add all new names to the module `__all__` if present.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_underscore6_fixtures.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run whole suite to catch fixture-change regressions**

Run: `uv run pytest -q`
Expected: all pass. (The urine itemid 226559 still present, so existing urine-based tests are unaffected. `make_two_class_labs`/`make_eicu_labs` now have extra creatinine rows — existing tests only filter on 226559, so they are unaffected.)

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/tests/fixtures/synth.py tools/rrt-liberation/tests/test_underscore6_fixtures.py
git commit -m "test(rrt): add creatinine + binary-flag synthetic sources"
```

---

## Task 2: Feature registry + builder refactor (migrate urine)

**Files:**
- Create: `src/rrt_liberation/features/registry.py`
- Modify: `src/rrt_liberation/features/builder.py`
- Modify: `src/rrt_liberation/features/__init__.py`
- Modify: `tests/test_features.py`
- Test: `tests/test_feature_registry.py`

- [ ] **Step 1: Write the failing test** `tests/test_feature_registry.py`:

```python
import pandas as pd

from rrt_liberation.features import FEATURE_REGISTRY, build_features, register_feature


def _cohort():
    return pd.DataFrame({"subject_id": [1, 2], "stay_id": [1, 2], "success": [1, 0]})


def test_register_and_unknown_predictor():
    assert "urine_output_24h" in FEATURE_REGISTRY
    feats = build_features(_cohort(), {"labs": pd.DataFrame(columns=["stay_id", "itemid", "valuenum"])}, ["nope"])
    assert "nope" in feats.columns
    assert feats["nope"].isna().all()
    assert len(feats) == 2  # row count preserved


def test_urine_feature_mean_by_stay():
    labs = pd.DataFrame(
        {"stay_id": [1, 1, 2], "itemid": [226559, 226559, 226559], "valuenum": [100.0, 300.0, 500.0]}
    )
    feats = build_features(_cohort(), {"labs": labs}, ["urine_output_24h"])
    assert feats.loc[feats["stay_id"] == 1, "urine_output_24h"].iloc[0] == 200.0
    assert feats.loc[feats["stay_id"] == 2, "urine_output_24h"].iloc[0] == 500.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_feature_registry.py -v`
Expected: FAIL (`ImportError: cannot import name 'FEATURE_REGISTRY'`)

- [ ] **Step 3: Implement**

`src/rrt_liberation/features/registry.py`:

```python
"""Feature registry: each feature is fn(cohort, sources) -> Series aligned to cohort."""

from __future__ import annotations

import logging
from typing import Callable, Dict

import pandas as pd

logger = logging.getLogger(__name__)

FeatureFn = Callable[[pd.DataFrame, Dict[str, pd.DataFrame]], pd.Series]
FEATURE_REGISTRY: Dict[str, FeatureFn] = {}

_URINE_ITEMID = 226559


def register_feature(name: str) -> Callable[[FeatureFn], FeatureFn]:
    def deco(fn: FeatureFn) -> FeatureFn:
        FEATURE_REGISTRY[name] = fn
        return fn

    return deco


@register_feature("urine_output_24h")
def _urine_output_24h(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
    # NOTE (limitation): stay-level mean, not yet windowed to the 24h before the
    # attempt. Per-attempt windowing is future work; name kept for UNDERSCORE alignment.
    labs = sources["labs"]
    mean_by_stay = labs[labs["itemid"] == _URINE_ITEMID].groupby("stay_id")["valuenum"].mean()
    return cohort["stay_id"].map(mean_by_stay)
```

`src/rrt_liberation/features/builder.py` (replace entirely):

```python
"""Feature assembly at liberation-attempt time (registry-driven)."""

from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

from rrt_liberation.features.registry import FEATURE_REGISTRY

logger = logging.getLogger(__name__)


def build_features(
    cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame], predictors: List[str]
) -> pd.DataFrame:
    """Attach each requested predictor (registered feature) to the cohort.

    `sources` provides the tables features read: {"labs", "events", "flags"}.
    Unknown predictors are created as NaN columns so the contract stays explicit.
    """
    feats = cohort.copy()
    for name in predictors:
        fn = FEATURE_REGISTRY.get(name)
        if fn is None:
            logger.warning("Predictor %s not registered; filling NaN", name)
            feats[name] = pd.NA
            continue
        feats[name] = fn(cohort, sources)
    return feats
```

`src/rrt_liberation/features/__init__.py` (replace):

```python
from rrt_liberation.features.builder import build_features
from rrt_liberation.features.registry import FEATURE_REGISTRY, register_feature

# Importing registry submodule ensures all feature fns are registered at import.
__all__ = ["build_features", "register_feature", "FEATURE_REGISTRY"]
```

`tests/test_features.py` — update the call to the new signature:

```python
from rrt_liberation.features import build_features
from tests.fixtures.synth import make_crrt_events, make_labs
from rrt_liberation.cohort import CohortFactory


def test_build_features_adds_requested_columns():
    events = make_crrt_events(n_patients=5, seed=42)
    labs = make_labs(n_patients=5, seed=42)
    cohort = CohortFactory("mimic")(min_off_hours=24.0).build(events, 7 * 24)
    feats = build_features(cohort, {"labs": labs}, ["urine_output_24h"])
    assert "urine_output_24h" in feats.columns
    assert len(feats) == len(cohort)
    assert not feats["urine_output_24h"].isna().all()
```

**Minimal caller migration (keep the suite green now).** Update the two callers to the new signature with a labs-only sources dict; events/flags are added in Task 6.

In `pipeline/run.py`, replace `feats = build_features(cohort, labs=labs, predictors=predictors)` with:
```python
    feats = build_features(cohort, {"labs": labs}, predictors)
```

In `pipeline/validate.py`, replace `feats = build_features(cohort, labs=labs, predictors=predictors)` with:
```python
    feats = build_features(cohort, {"labs": labs}, predictors)
```

(These keep the existing single-feature smokes green: urine needs only `sources["labs"]`.)

- [ ] **Step 4: Run the whole suite to verify it stays green**

Run: `uv run pytest -q`
Expected: all pass (registry + migrated callers; existing single-feature smokes use only labs).

- [ ] **Step 5: Lint/type**

Run: `uv run ruff check src/rrt_liberation/features tests/test_feature_registry.py tests/test_features.py pipeline/` and `uv run mypy src/rrt_liberation/features pipeline`. Clean.

- [ ] **Step 6: Commit (features package + minimal caller migration)**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/features tools/rrt-liberation/tests/test_feature_registry.py tools/rrt-liberation/tests/test_features.py tools/rrt-liberation/pipeline/run.py tools/rrt-liberation/pipeline/validate.py
git commit -m "refactor(rrt): introduce feature registry; migrate urine feature + callers"
```

---

## Task 3: Continuous features (baseline creatinine, CRRT duration)

**Files:**
- Modify: `src/rrt_liberation/features/registry.py`
- Test: `tests/test_feature_continuous.py`

- [ ] **Step 1: Write the failing test** `tests/test_feature_continuous.py`:

```python
import pandas as pd

from rrt_liberation.features import build_features

T0 = pd.Timestamp("2200-01-01")


def test_baseline_creatinine_is_min_by_stay():
    cohort = pd.DataFrame({"subject_id": [1, 2], "stay_id": [1, 2], "success": [1, 0]})
    labs = pd.DataFrame(
        {"stay_id": [1, 1, 2], "itemid": [50912, 50912, 226559], "valuenum": [3.0, 1.5, 800.0]}
    )
    feats = build_features(cohort, {"labs": labs}, ["baseline_creatinine"])
    assert feats.loc[feats["stay_id"] == 1, "baseline_creatinine"].iloc[0] == 1.5  # min
    assert feats.loc[feats["stay_id"] == 2, "baseline_creatinine"].isna().iloc[0]  # no Cr -> NaN


def test_crrt_duration_truncated_at_attempt_time():
    # stay 1: CRRT on 0h..24h; attempt at 24h -> 24.0h duration
    attempt = T0 + pd.Timedelta(hours=24)
    cohort = pd.DataFrame({"subject_id": [1], "stay_id": [1], "attempt_time": [attempt], "success": [1]})
    events = pd.DataFrame(
        {
            "subject_id": [1],
            "stay_id": [1],
            "starttime": [T0],
            "endtime": [T0 + pd.Timedelta(hours=24)],
            "modality": ["CVVHDF"],
        }
    )
    feats = build_features(cohort, {"events": events}, ["crrt_duration_hours"])
    assert abs(feats["crrt_duration_hours"].iloc[0] - 24.0) < 1e-9


def test_crrt_duration_per_attempt_differs():
    # two attempts in one stay: durations differ by attempt_time
    a1 = T0 + pd.Timedelta(hours=24)
    a2 = T0 + pd.Timedelta(hours=200)
    cohort = pd.DataFrame(
        {"subject_id": [1, 1], "stay_id": [1, 1], "attempt_time": [a1, a2], "success": [0, 1]}
    )
    events = pd.DataFrame(
        {
            "subject_id": [1, 1],
            "stay_id": [1, 1],
            "starttime": [T0, T0 + pd.Timedelta(hours=120)],
            "endtime": [T0 + pd.Timedelta(hours=24), T0 + pd.Timedelta(hours=144)],
            "modality": ["CVVHDF", "CVVHDF"],
        }
    )
    feats = build_features(cohort, {"events": events}, ["crrt_duration_hours"])
    # attempt at 24h -> only first block counts (24h); attempt at 200h -> both blocks (24+24=48h)
    assert abs(feats["crrt_duration_hours"].iloc[0] - 24.0) < 1e-9
    assert abs(feats["crrt_duration_hours"].iloc[1] - 48.0) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_feature_continuous.py -v`
Expected: FAIL (`baseline_creatinine` not registered → NaN column, assertions fail)

- [ ] **Step 3: Implement** — append to `src/rrt_liberation/features/registry.py`:

```python
_CREATININE_ITEMID = 50912


@register_feature("baseline_creatinine")
def _baseline_creatinine(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
    """Minimum creatinine per stay as a conservative baseline-renal-function proxy."""
    labs = sources["labs"]
    min_by_stay = labs[labs["itemid"] == _CREATININE_ITEMID].groupby("stay_id")["valuenum"].min()
    return cohort["stay_id"].map(min_by_stay)


@register_feature("crrt_duration_hours")
def _crrt_duration_hours(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
    """Total CRRT-on hours up to each attempt_time (per-attempt, truncated)."""
    events = sources["events"]
    values = []
    for _, row in cohort.iterrows():
        ev = events[events["stay_id"] == row["stay_id"]]
        attempt = row["attempt_time"]
        total_h = 0.0
        for _, e in ev.iterrows():
            end = min(e["endtime"], attempt)
            delta_h = (end - e["starttime"]).total_seconds() / 3600.0
            if delta_h > 0:
                total_h += delta_h
        values.append(total_h)
    return pd.Series(values, index=cohort.index)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_feature_continuous.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/features/registry.py tools/rrt-liberation/tests/test_feature_continuous.py
git commit -m "feat(rrt): add baseline_creatinine and crrt_duration_hours features"
```

---

## Task 4: Binary flag features

**Files:**
- Modify: `src/rrt_liberation/features/registry.py`
- Test: `tests/test_feature_binary.py`

- [ ] **Step 1: Write the failing test** `tests/test_feature_binary.py`:

```python
import pandas as pd

from rrt_liberation.features import build_features

PREDS = ["sepsis_shock", "vasopressor", "mechanical_ventilation"]


def _cohort():
    return pd.DataFrame({"subject_id": [1, 2, 3], "stay_id": [1, 2, 3], "success": [1, 0, 1]})


def test_binary_flags_joined_by_stay():
    flags = pd.DataFrame(
        {
            "stay_id": [1, 2],  # stay 3 absent -> 0
            "sepsis_shock": [1, 0],
            "vasopressor": [0, 1],
            "mechanical_ventilation": [1, 1],
        }
    )
    feats = build_features(_cohort(), {"flags": flags}, PREDS)
    assert feats.loc[feats["stay_id"] == 1, "sepsis_shock"].iloc[0] == 1
    assert feats.loc[feats["stay_id"] == 2, "vasopressor"].iloc[0] == 1
    assert feats.loc[feats["stay_id"] == 3, "sepsis_shock"].iloc[0] == 0  # absent -> 0


def test_binary_flags_zero_when_no_flags_source():
    feats = build_features(_cohort(), {"labs": pd.DataFrame()}, PREDS)
    for col in PREDS:
        assert (feats[col] == 0).all()  # lenient: no flags table -> all 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_feature_binary.py -v`
Expected: FAIL (binary features not registered)

- [ ] **Step 3: Implement** — append to `src/rrt_liberation/features/registry.py`:

```python
def _binary_flag(flag_name: str) -> FeatureFn:
    def fn(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
        flags = sources.get("flags")
        if flags is None or flag_name not in getattr(flags, "columns", []):
            return pd.Series(0, index=cohort.index, dtype=int)
        mapping = flags.set_index("stay_id")[flag_name]
        return cohort["stay_id"].map(mapping).fillna(0).astype(int)

    return fn


register_feature("sepsis_shock")(_binary_flag("sepsis_shock"))
register_feature("vasopressor")(_binary_flag("vasopressor"))
register_feature("mechanical_ventilation")(_binary_flag("mechanical_ventilation"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_feature_binary.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/features/registry.py tools/rrt-liberation/tests/test_feature_binary.py
git commit -m "feat(rrt): add sepsis_shock/vasopressor/mechanical_ventilation flag features"
```

---

## Task 5: `to_canonical_events` on cohort builders

**Files:**
- Modify: `src/rrt_liberation/cohort/base.py`
- Modify: `src/rrt_liberation/cohort/mimic.py`
- Modify: `src/rrt_liberation/cohort/eicu.py`
- Test: `tests/test_canonical_events.py`

- [ ] **Step 1: Write the failing test** `tests/test_canonical_events.py`:

```python
import pandas as pd

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.cohort.eicu import _EICU_T0

CANON = ["subject_id", "stay_id", "starttime", "endtime", "modality"]


def test_mimic_to_canonical_is_identity_schema():
    events = pd.DataFrame(
        {
            "subject_id": [1],
            "stay_id": [1],
            "starttime": [pd.Timestamp("2150-01-01")],
            "endtime": [pd.Timestamp("2150-01-02")],
            "modality": ["CVVHDF"],
        }
    )
    out = CohortFactory("mimic")(min_off_hours=24.0).to_canonical_events(events)
    assert set(CANON) <= set(out.columns)
    assert out["starttime"].iloc[0] == pd.Timestamp("2150-01-01")


def test_eicu_to_canonical_converts_offsets():
    raw = pd.DataFrame(
        {
            "patientunitstayid": [7],
            "treatmentoffset": [1440],
            "treatmentstopoffset": [2880],
            "treatmentstring": ["renal|dialysis|CVVH"],
        }
    )
    out = CohortFactory("eicu")(min_off_hours=24.0).to_canonical_events(raw)
    assert set(CANON) <= set(out.columns)
    assert out["starttime"].iloc[0] == _EICU_T0 + pd.Timedelta(minutes=1440)
    assert out["stay_id"].iloc[0] == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_canonical_events.py -v`
Expected: FAIL (`AttributeError: ... has no attribute 'to_canonical_events'`)

- [ ] **Step 3: Implement**

In `src/rrt_liberation/cohort/base.py`, add a default identity method to `BaseCohortBuilder` (after `__init__`, before the abstract `build`):

```python
    def to_canonical_events(self, events: pd.DataFrame) -> pd.DataFrame:
        """Return events in the canonical schema. Default: identity (already canonical)."""
        return events
```

In `src/rrt_liberation/cohort/mimic.py`, route `build` through it (keeps identity behavior, makes intent explicit):

```python
    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        canonical = self.to_canonical_events(events)
        attempts = find_attempts(canonical, min_off_hours=self.min_off_hours)
        labeled = label_outcome(attempts, canonical, horizon_hours=horizon_hours)
        logger.info("MIMIC cohort: %d attempts", len(labeled))
        return labeled
```

In `src/rrt_liberation/cohort/eicu.py`, rename the static `_to_canonical` to a public override `to_canonical_events` and have `build` use it:

```python
    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        canonical = self.to_canonical_events(events)
        attempts = find_attempts(canonical, min_off_hours=self.min_off_hours)
        labeled = label_outcome(attempts, canonical, horizon_hours=horizon_hours)
        logger.info("eICU cohort: %d attempts", len(labeled))
        return labeled

    def to_canonical_events(self, events: pd.DataFrame) -> pd.DataFrame:
        """Map eICU columns + minute offsets to the canonical events schema."""
        out = pd.DataFrame()
        out["subject_id"] = events["patientunitstayid"].to_numpy()
        out["stay_id"] = events["patientunitstayid"].to_numpy()
        out["starttime"] = _EICU_T0 + pd.to_timedelta(events["treatmentoffset"], unit=_OFFSET_UNIT)
        out["endtime"] = _EICU_T0 + pd.to_timedelta(events["treatmentstopoffset"], unit=_OFFSET_UNIT)
        out["modality"] = "CVVHDF"
        return out
```

(Remove the old `@staticmethod def _to_canonical(...)`. Keep `_EICU_T0` and `_OFFSET_UNIT`. Update `tests/test_eicu_cohort.py` only if it referenced `_to_canonical` directly — it does not; it uses `build`, so no test change needed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_canonical_events.py tests/test_eicu_cohort.py tests/test_cohort.py -v`
Expected: PASS (eICU + mimic cohort tests still green; new canonical tests pass)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/cohort tools/rrt-liberation/tests/test_canonical_events.py
git commit -m "feat(rrt): add to_canonical_events for DB-agnostic event access"
```

---

## Task 6: Pipeline wiring + config (restore green suite)

**Files:**
- Modify: `pipeline/run.py`
- Modify: `pipeline/validate.py`
- Modify: `conf/cohort/mimic.yaml`, `conf/cohort/eicu.yaml`, `conf/features/baseline.yaml`, `conf/model/underscore.yaml`
- Modify: `tests/test_pipeline_smoke.py` (add 6-feature logistic smoke)
- Modify: `tests/test_validate_smoke.py` (add 6-feature external validation)

- [ ] **Step 1: Update `pipeline/run.py`** (callers already pass `{"labs": labs}` from Task 2 — now expand sources with events/flags)

(a) Add `flags_csv: Optional[str | Path] = None` to `run_pipeline`'s signature (place after `created_utc`).

(b) Replace `feats = build_features(cohort, {"labs": labs}, predictors)` with:

```python
    sources: Dict[str, pd.DataFrame] = {
        "labs": labs,
        "events": builder.to_canonical_events(events),
    }
    if flags_csv is not None:
        sources["flags"] = read_csv(flags_csv)
    feats = build_features(cohort, sources, predictors)
```

(c) In `main`, pass `flags_csv` (add as the last argument to the `run_pipeline(...)` call):

```python
        flags_csv=cfg.cohort.get("flags_csv"),
```

(`cfg.cohort.get("flags_csv")` returns None if absent — safe.)

- [ ] **Step 2: Update `pipeline/validate.py`** — replace `feats = build_features(cohort, {"labs": labs}, predictors)` with:

```python
    sources: Dict[str, pd.DataFrame] = {
        "labs": labs,
        "events": builder.to_canonical_events(events),
    }
    if flags_csv is not None:
        sources["flags"] = read_csv(flags_csv)
    feats = build_features(cohort, sources, predictors)
```

Add `flags_csv: Optional[str | Path] = None` to `run_external_validation`'s signature (after `seed`); import `Optional` if missing; and in `validate.py`'s `main` add `flags_csv=cfg.cohort.get("flags_csv")` to the `run_external_validation(...)` call.

- [ ] **Step 3: Update config files**

`conf/cohort/mimic.yaml` — add a line:
```yaml
flags_csv: ${paths.data_dir}/mimic/flags.csv
```
`conf/cohort/eicu.yaml` — add a line:
```yaml
flags_csv: ${paths.data_dir}/eicu/flags.csv
```
`conf/features/baseline.yaml` — replace with:
```yaml
predictors:
  - urine_output_24h
  - baseline_creatinine
  - crrt_duration_hours
  - sepsis_shock
  - vasopressor
  - mechanical_ventilation
```
`conf/model/underscore.yaml` — replace coefficients block with 6 placeholders:
```yaml
name: underscore
# Fill from Chaibi et al., 2026 (Intensive Care Medicine). Placeholder zeros
# below are NOT the real score and must be replaced before any real-data run.
coefficients:
  intercept: 0.0
  urine_output_24h: 0.0
  baseline_creatinine: 0.0
  crrt_duration_hours: 0.0
  sepsis_shock: 0.0
  vasopressor: 0.0
  mechanical_ventilation: 0.0
```

- [ ] **Step 4: Add a 6-feature logistic smoke test** — append to `tests/test_pipeline_smoke.py`:

```python
def test_pipeline_logistic_six_features(tmp_path):
    from tests.fixtures.synth import (
        make_two_class_events,
        make_two_class_flags,
        make_two_class_labs,
    )

    data_dir = tmp_path / "data" / "mimic"
    data_dir.mkdir(parents=True)
    make_two_class_events().to_csv(data_dir / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(data_dir / "labs.csv", index=False)
    make_two_class_flags().to_csv(data_dir / "flags.csv", index=False)
    out_dir = tmp_path / "outputs"

    preds = [
        "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
        "sepsis_shock", "vasopressor", "mechanical_ventilation",
    ]
    result = run_pipeline(
        events_csv=data_dir / "crrt_events.csv",
        labs_csv=data_dir / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=preds,
        model_name="logistic",
        coefficients={},
        output_dir=out_dir,
        seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        n_boot=20,
        flags_csv=data_dir / "flags.csv",
    )
    assert "auroc_corrected" in result and result["n_boot_used"] > 0
    import pandas as pd
    coef = pd.read_csv(out_dir / "coefficients.csv")
    # 6 predictors + creatinine missingness flag column -> >= 6 coefficient rows
    assert len(coef) >= 6
```

- [ ] **Step 5: Add a 6-feature external-validation smoke** — append to `tests/test_validate_smoke.py`:

```python
def test_validate_six_features(tmp_path):
    from tests.fixtures.synth import (
        make_eicu_events,
        make_eicu_flags,
        make_eicu_labs,
        make_two_class_events,
        make_two_class_flags,
        make_two_class_labs,
    )

    preds = [
        "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
        "sepsis_shock", "vasopressor", "mechanical_ventilation",
    ]
    mimic = tmp_path / "data" / "mimic"
    mimic.mkdir(parents=True)
    make_two_class_events().to_csv(mimic / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(mimic / "labs.csv", index=False)
    make_two_class_flags().to_csv(mimic / "flags.csv", index=False)
    train_out = tmp_path / "train_out"
    run_pipeline(
        events_csv=mimic / "crrt_events.csv",
        labs_csv=mimic / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=preds,
        model_name="logistic",
        coefficients={},
        output_dir=train_out,
        seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        n_boot=20,
        flags_csv=mimic / "flags.csv",
    )

    eicu = tmp_path / "data" / "eicu"
    eicu.mkdir(parents=True)
    make_eicu_events().to_csv(eicu / "crrt_events.csv", index=False)
    make_eicu_labs().to_csv(eicu / "labs.csv", index=False)
    make_eicu_flags().to_csv(eicu / "flags.csv", index=False)
    val_out = tmp_path / "val_out"
    result = run_external_validation(
        events_csv=eicu / "crrt_events.csv",
        labs_csv=eicu / "labs.csv",
        cohort_name="eicu",
        min_off_hours=24.0,
        liberation_name="def_7d",
        fixed_model_path=train_out / "model_logistic.json",
        output_dir=val_out,
        n_boot=20,
        seed=42,
        flags_csv=eicu / "flags.csv",
    )
    assert (val_out / "external_validation.json").exists()
    assert "auroc" in result
```

- [ ] **Step 6: Run the whole suite (now fully green)**

Run: `uv run pytest -q`
Expected: all pass (the Task 2 caller breakage is now resolved; old single-feature smokes still pass because `flags_csv` defaults to None and urine needs only labs).

- [ ] **Step 7: Hydra CLI end-to-end (6 features)**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic data/eicu
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs, make_two_class_flags; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False); make_two_class_flags().to_csv('data/mimic/flags.csv', index=False)"
uv run python -m pipeline.run model=logistic
uv run python -c "from tests.fixtures.synth import make_eicu_events, make_eicu_labs, make_eicu_flags; make_eicu_events().to_csv('data/eicu/crrt_events.csv', index=False); make_eicu_labs().to_csv('data/eicu/labs.csv', index=False); make_eicu_flags().to_csv('data/eicu/flags.csv', index=False)"
uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu
```
Expected: training writes `coefficients.csv` with rows for the 6 predictors (+ a `baseline_creatinine_missing`/`urine_output_24h_missing` flag if those labs had missing); validation writes `external_validation.json`. Confirm `cd /Users/llmmkkooii/github/pushtest && git status --porcelain` shows nothing under `data/`/`outputs/`.

- [ ] **Step 8: Lint/type + commit**

Run: `uv run ruff check . && uv run mypy src pipeline tests` (clean).

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/pipeline tools/rrt-liberation/conf tools/rrt-liberation/tests/test_pipeline_smoke.py tools/rrt-liberation/tests/test_validate_smoke.py
git commit -m "feat(rrt): wire 6-feature sources into pipelines; configs to UNDERSCORE-6"
```

---

## Task 7: README + verification sweep

**Files:**
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Update the README `## Status` body** to:

```markdown
## Status

Implemented: MIMIC/eICU cohort, liberation labeling, **UNDERSCORE-6 feature
registry** (urine, baseline creatinine, CRRT duration, sepsis shock, vasopressor,
mechanical ventilation; DB-independent over labs/events/flags sources), UNDERSCORE
benchmark, development logistic model (JSON-persisted, bootstrap optimism-corrected
internal validation), eICU external validation, discrimination + calibration,
TRIPOD flow + Table 1.

Run training (6 features): `uv run python -m pipeline.run model=logistic`
Run external validation: `uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu`

Stubbed (later sub-projects): RF/XGBoost reference, remaining proposal-section-7
predictors, real MIMIC/eICU SQL extraction, 24h urine windowing, DCA, definition
sensitivity (72h/14d), MICE, AmsterdamUMCdb.
```

Keep the rest of the README (title, Run, PHI boundary) unchanged.

- [ ] **Step 2: Verification sweep**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
uv run ruff check .
uv run mypy src pipeline tests
uv run pytest -q
```
All clean/green. Report counts.

- [ ] **Step 3: Reproducibility check (6-feature logistic)**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs, make_two_class_flags; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False); make_two_class_flags().to_csv('data/mimic/flags.csv', index=False)"
uv run python -m pipeline.run model=logistic 2>&1 | grep "Logistic pipeline metrics" | tee /tmp/u6_1.log
uv run python -m pipeline.run model=logistic 2>&1 | grep "Logistic pipeline metrics" | tee /tmp/u6_2.log
diff /tmp/u6_1.log /tmp/u6_2.log && echo "IDENTICAL"
```
Expected: "IDENTICAL".

- [ ] **Step 4: PHI check + commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git ls-files tools/rrt-liberation/ | grep -E '(data|outputs)/' || echo "clean"
git add tools/rrt-liberation/README.md
git commit -m "docs(rrt): document UNDERSCORE-6 feature registry"
```

---

## Definition of Done

- `uv run python -m pipeline.run model=logistic` trains on the 6 features and writes `coefficients.csv` with the 6 predictors (+ missingness flags); `uv run python -m pipeline.validate ... cohort=eicu` externally validates on the 6 features.
- `uv run pytest -q` green (registry, continuous, binary, canonical-events, fixtures, 6-feature smokes, plus all prior tests).
- `ruff check .` and `mypy src pipeline tests` clean.
- Same-seed 6-feature logistic reruns produce identical metrics.
- `data/`/`outputs/` gitignored; no credentialed data committed; no fabricated coefficients (UNDERSCORE placeholders stay 0; logistic learned from synthetic).
- Backward compatible: single-feature smokes and the `model=underscore` path still pass.

---

## Self-Review

- **Spec coverage:** §1 decisions (registry, DB-agnostic, to_canonical_events, flags optional) → Tasks 2,5,6 ✓. §2 architecture (all files) ✓. §3 six feature defs → Tasks 2,3,4 ✓. §4 wiring/config/back-compat → Task 6 ✓. §5 tests → every task TDD; DB-agnostic verified via canonical-events (Task 5) + 6-feature external smoke (Task 6) ✓.
- **Placeholder scan:** none — full code each step. (Task 2 explicitly documents a temporary red suite restored in Task 6 — an intentional sequencing note, not a placeholder.)
- **Type consistency:** `build_features(cohort, sources: Dict[str, DataFrame], predictors)`, feature fns `fn(cohort, sources) -> Series`, `register_feature`/`FEATURE_REGISTRY`, `to_canonical_events(events) -> DataFrame`, `run_pipeline(..., flags_csv=None)`, `run_external_validation(..., flags_csv=None)` — consistent across tasks. Itemids 226559 (urine) / 50912 (creatinine) consistent. Flags schema `stay_id, sepsis_shock, vasopressor, mechanical_ventilation` consistent across fixtures, features, configs.
