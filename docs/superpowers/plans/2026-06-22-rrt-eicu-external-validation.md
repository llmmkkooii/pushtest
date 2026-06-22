# RRT eICU External Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the fixed development logistic model (from sub-project A) to an eICU cohort without retraining, producing external discrimination + calibration (true external validation), via a dedicated `pipeline/validate.py`.

**Architecture:** `EicuCohortBuilder` converts eICU-shaped events (minute offsets) into the canonical events frame and reuses the existing `find_attempts`/`label_outcome` (DB-independent liberation logic). A new `external_validate` computes external AUROC (+bootstrap CI) and calibration slope/intercept with NO optimism correction (external application has no optimism bias by construction). A new Hydra entry `pipeline/validate.py` loads a persisted `model_logistic.json` (preprocessing carried inside), builds the eICU cohort, applies the model, and writes external metrics. All synthetic; no credentialed data.

**Tech Stack:** Python 3.11, uv, pandas, numpy, sklearn (reused via the model), statsmodels (calibration, reused), Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-22-rrt-eicu-external-validation-design.md](../specs/2026-06-22-rrt-eicu-external-validation-design.md)

**Working dir:** paths relative to `tools/rrt-liberation/` unless noted. Branch `feature/rrt-eicu-external-validation`. Run via `uv run`.

**Conventions:** files 200-400 lines, type hints, module logger (no `print`), `__all__`, factory/registry unchanged, seed fixed. Existing `run.py` (training) and all existing tests stay unchanged.

**Key facts confirmed in the codebase:**
- `build_features(cohort, labs, predictors)` reads urine via `labs[labs["itemid"] == 226559]` grouped by `stay_id` mean. So eICU labs must be provided in the SAME canonical labs schema (`stay_id`, `itemid`, `valuenum`). Only eICU EVENTS are eICU-shaped (offsets) and converted by `EicuCohortBuilder`; eICU labs are emitted canonical (real eICU labname mapping is the feature-engineering sub-project).
- `load_model_json(path) -> LogisticModel` exists; the model exposes `.predictors`, `.predict_proba`, `.coefficients`.
- `auroc_with_ci(y, p, n_boot, seed) -> {"auroc","ci_low","ci_high"}`, `calibration_slope_intercept(y, p) -> {"slope","intercept"}`, `save_calibration_plot(y, p, path)`, `build_table1(cohort, by)`, `build_features`, `get_horizon(name)`, `CohortFactory`, `read_csv`/`write_csv`/`write_json`/`set_seed` all exist.
- `conf/cohort/eicu.yaml` already exists (name: eicu, min_off_hours, events_csv `${paths.data_dir}/eicu/crrt_events.csv`, labs_csv `.../eicu/labs.csv`).

---

## File Structure

| File | Responsibility |
|---|---|
| `tests/fixtures/synth.py` | + `make_eicu_events` (eICU-shaped, offsets), `make_eicu_labs` (canonical labs) |
| `src/rrt_liberation/cohort/eicu.py` | implement `EicuCohortBuilder` (offset→canonical, reuse liberation rules) |
| `src/rrt_liberation/evaluation/external_validation.py` | `external_validate(model, X, y, n_boot, seed)` |
| `conf/validate.yaml` | Hydra config for validation runs |
| `pipeline/validate.py` | `run_external_validation(...)` + Hydra `main` |
| `tests/test_eicu_cohort.py`, `tests/test_external_validation.py`, `tests/test_validate_smoke.py` | tests |

---

## Task 1: eICU synthetic fixtures

**Files:**
- Modify: `tests/fixtures/synth.py`
- Test: `tests/test_eicu_fixtures.py`

- [ ] **Step 1: Write the failing test** `tests/test_eicu_fixtures.py`:

```python
import numpy as np

from tests.fixtures.synth import make_eicu_events, make_eicu_labs


def test_eicu_events_schema_and_offsets():
    ev = make_eicu_events(n_patients=24, seed=42)
    assert list(ev.columns) == [
        "patientunitstayid", "treatmentoffset", "treatmentstopoffset", "treatmentstring"
    ]
    # offsets are integer minutes, stop after start
    assert (ev["treatmentstopoffset"] > ev["treatmentoffset"]).all()
    assert ev["patientunitstayid"].nunique() == 24


def test_eicu_labs_canonical_schema():
    labs = make_eicu_labs(n_patients=24, seed=42)
    # build_features reads itemid==226059? no -> 226559 urine, valuenum, stay_id
    assert {"stay_id", "itemid", "valuenum"} <= set(labs.columns)
    assert (labs["itemid"] == 226559).all()


def test_eicu_events_deterministic():
    a = make_eicu_events(n_patients=10, seed=1)
    b = make_eicu_events(n_patients=10, seed=1)
    assert a.equals(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_eicu_fixtures.py -v`
Expected: FAIL (`ImportError: cannot import name 'make_eicu_events'`)

- [ ] **Step 3: Implement** — append to `tests/fixtures/synth.py` (the module already has `import numpy as np`, `import pandas as pd`, and `_T0`):

```python
_EICU_OFFSET0 = 0  # eICU offsets are minutes from unit admission


def make_eicu_events(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Synthetic eICU-shaped CRRT treatment rows (minute offsets). Two-class cohort.

    Half the patients restart CRRT within 7 days (failure) before a final
    sustained off (success); the rest never restart. No real data; deterministic.
    """
    rng = np.random.default_rng(seed + 23)
    rows = []
    for i in range(n_patients):
        pid = 5000 + i
        start0 = int(rng.integers(0, 12)) * 60          # minutes
        stop0 = start0 + 24 * 60                          # 24h on
        rows.append(
            {
                "patientunitstayid": pid,
                "treatmentoffset": start0,
                "treatmentstopoffset": stop0,
                "treatmentstring": "renal|dialysis|C V V H D",
            }
        )
        if i % 2 == 0:
            r_start = stop0 + int(rng.integers(48, 120)) * 60  # restart within 7d
            rows.append(
                {
                    "patientunitstayid": pid,
                    "treatmentoffset": r_start,
                    "treatmentstopoffset": r_start + 24 * 60,
                    "treatmentstring": "renal|dialysis|C V V H D",
                }
            )
    return pd.DataFrame(rows)


def make_eicu_labs(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Synthetic eICU urine output, emitted in the CANONICAL labs schema.

    Keyed by stay_id == patientunitstayid with itemid 226559 so the existing
    build_features reads it unchanged. (Real eICU labname mapping is the
    feature-engineering sub-project.)
    """
    rng = np.random.default_rng(seed + 29)
    rows = []
    for i in range(n_patients):
        pid = 5000 + i
        rows.append(
            {
                "subject_id": pid,
                "stay_id": pid,
                "charttime": _T0,
                "itemid": 226559,
                "valuenum": float(rng.integers(200, 1800)),
            }
        )
    return pd.DataFrame(rows)
```

Add `make_eicu_events` and `make_eicu_labs` to the module `__all__` if one is defined.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_eicu_fixtures.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/tests/fixtures/synth.py tools/rrt-liberation/tests/test_eicu_fixtures.py
git commit -m "test(rrt): add eICU-shaped synthetic fixtures"
```

---

## Task 2: EicuCohortBuilder

**Files:**
- Modify: `src/rrt_liberation/cohort/eicu.py` (replace stub)
- Test: `tests/test_eicu_cohort.py`

- [ ] **Step 1: Write the failing test** `tests/test_eicu_cohort.py`:

```python
import pandas as pd

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.cohort.eicu import _EICU_T0
from tests.fixtures.synth import make_eicu_events


def _one_stay(offsets):
    """offsets: list of (start_min, stop_min) for patientunitstayid 1."""
    return pd.DataFrame(
        [
            {
                "patientunitstayid": 1,
                "treatmentoffset": s,
                "treatmentstopoffset": e,
                "treatmentstring": "renal|dialysis|CVVH",
            }
            for s, e in offsets
        ]
    )


def test_offset_to_timestamp_conversion():
    builder = CohortFactory("eicu")(min_off_hours=24.0)
    # single CRRT block 0..1440 min (24h) then never restarts -> one attempt at 1440 min
    cohort = builder.build(_one_stay([(0, 1440)]), horizon_hours=7 * 24)
    assert len(cohort) == 1
    assert cohort.iloc[0]["attempt_time"] == _EICU_T0 + pd.Timedelta(minutes=1440)
    assert cohort.iloc[0]["success"] == 1


def test_restart_within_horizon_is_failure():
    # on 0..1440 (24h), restart at 1440+5*1440 (day 5) within 7d -> first attempt fails
    builder = CohortFactory("eicu")(min_off_hours=24.0)
    cohort = builder.build(
        _one_stay([(0, 1440), (1440 + 5 * 1440, 1440 + 7 * 1440)]), horizon_hours=7 * 24
    )
    assert cohort.iloc[0]["success"] == 0


def test_returns_canonical_schema():
    builder = CohortFactory("eicu")(min_off_hours=24.0)
    cohort = builder.build(make_eicu_events(n_patients=8, seed=42), horizon_hours=7 * 24)
    assert {"subject_id", "stay_id", "attempt_time", "success"} <= set(cohort.columns)
    assert cohort["success"].isin([0, 1]).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_eicu_cohort.py -v`
Expected: FAIL (`ImportError: cannot import name '_EICU_T0'` and/or NotImplementedError)

- [ ] **Step 3: Implement** — replace `src/rrt_liberation/cohort/eicu.py` ENTIRELY with:

```python
"""eICU-CRD cohort builder: convert eICU-shaped treatment rows to the canonical
events frame, then reuse the DB-independent liberation logic."""

from __future__ import annotations

import logging

import pandas as pd

from rrt_liberation.cohort.base import BaseCohortBuilder
from rrt_liberation.liberation.rules import find_attempts, label_outcome

logger = logging.getLogger(__name__)

# Fixed reference instant for converting eICU minute-offsets to timestamps.
# Deterministic; only relative differences matter to the liberation logic.
_EICU_T0 = pd.Timestamp("2200-01-01")


class EicuCohortBuilder(BaseCohortBuilder):
    """Builds a labeled liberation cohort from eICU-shaped CRRT treatment rows."""

    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        canonical = self._to_canonical(events)
        attempts = find_attempts(canonical, min_off_hours=self.min_off_hours)
        labeled = label_outcome(attempts, canonical, horizon_hours=horizon_hours)
        logger.info("eICU cohort: %d attempts", len(labeled))
        return labeled

    @staticmethod
    def _to_canonical(events: pd.DataFrame) -> pd.DataFrame:
        """Map eICU columns + minute offsets to the canonical events schema."""
        out = pd.DataFrame()
        out["subject_id"] = events["patientunitstayid"].to_numpy()
        out["stay_id"] = events["patientunitstayid"].to_numpy()
        out["starttime"] = _EICU_T0 + pd.to_timedelta(events["treatmentoffset"], unit="m")
        out["endtime"] = _EICU_T0 + pd.to_timedelta(events["treatmentstopoffset"], unit="m")
        out["modality"] = "CVVHDF"
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_eicu_cohort.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run whole suite + lint/type**

Run: `uv run pytest -q` (no regressions), `uv run ruff check src/rrt_liberation/cohort/ tests/test_eicu_cohort.py`, `uv run mypy src/rrt_liberation/cohort/eicu.py`. All clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/cohort/eicu.py tools/rrt-liberation/tests/test_eicu_cohort.py
git commit -m "feat(rrt): implement EicuCohortBuilder (offset->canonical, reuse liberation rules)"
```

---

## Task 3: external_validate

**Files:**
- Create: `src/rrt_liberation/evaluation/external_validation.py`
- Test: `tests/test_external_validation.py`

- [ ] **Step 1: Write the failing test** `tests/test_external_validation.py`:

```python
import math

import numpy as np
import pandas as pd

from rrt_liberation.evaluation.external_validation import external_validate


class _StubModel:
    def __init__(self, p):
        self._p = np.asarray(p)

    def predict_proba(self, X):
        return self._p


def test_external_validate_known_auroc_no_optimism():
    y = pd.Series([0, 0, 1, 1])
    p = [0.1, 0.2, 0.8, 0.9]
    res = external_validate(_StubModel(p), pd.DataFrame({"f": [0, 0, 0, 0]}), y, n_boot=50, seed=42)
    assert abs(res["auroc"]["point"] - 1.0) < 1e-9
    assert res["single_class"] is False
    assert res["n"] == 4 and res["n_events"] == 2
    # external validation has NO optimism correction:
    assert set(res.keys()) == {"auroc", "calibration", "n", "n_events", "single_class"}


def test_external_validate_single_class():
    res = external_validate(
        _StubModel([0.5, 0.6]), pd.DataFrame({"f": [0, 0]}), pd.Series([1, 1]), seed=42
    )
    assert res["single_class"] is True
    assert math.isnan(res["auroc"]["point"])


def test_external_validate_deterministic():
    y = pd.Series([0, 1, 0, 1, 1, 0])
    p = [0.2, 0.7, 0.4, 0.6, 0.8, 0.3]
    r1 = external_validate(_StubModel(p), pd.DataFrame({"f": list(range(6))}), y, n_boot=50, seed=42)
    r2 = external_validate(_StubModel(p), pd.DataFrame({"f": list(range(6))}), y, n_boot=50, seed=42)
    assert r1 == r2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_external_validation.py -v`
Expected: FAIL (`ModuleNotFoundError: ...external_validation`)

- [ ] **Step 3: Implement** `src/rrt_liberation/evaluation/external_validation.py`:

```python
"""External validation: apply a FIXED model to an external cohort (no optimism)."""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

from rrt_liberation.evaluation.calibration import calibration_slope_intercept
from rrt_liberation.evaluation.discrimination import auroc_with_ci

logger = logging.getLogger(__name__)


def external_validate(
    model: object, X: pd.DataFrame, y: pd.Series, n_boot: int = 200, seed: int = 42
) -> Dict[str, object]:
    """Discrimination (AUROC + bootstrap CI) and calibration on an external cohort.

    The model is applied as-is (no refit, no optimism correction). Returns NaN
    metrics with single_class=True when the external outcome has one class.
    """
    y_arr = np.asarray(y)
    n = int(len(y_arr))
    n_events = int(y_arr.sum())
    if len(np.unique(y_arr)) < 2:
        logger.warning("External cohort is single-class; AUROC/calibration undefined")
        return {
            "auroc": {"point": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")},
            "calibration": {"slope": float("nan"), "intercept": float("nan")},
            "n": n,
            "n_events": n_events,
            "single_class": True,
        }
    p = model.predict_proba(X)  # type: ignore[attr-defined]
    disc = auroc_with_ci(y_arr, p, n_boot=n_boot, seed=seed)
    try:
        calib = calibration_slope_intercept(y_arr, p)
    except Exception as exc:  # pragma: no cover - numerical edge
        logger.warning("External calibration failed (%s); reporting NaN", exc)
        calib = {"slope": float("nan"), "intercept": float("nan")}
    return {
        "auroc": {"point": float(disc["auroc"]), "ci_low": float(disc["ci_low"]), "ci_high": float(disc["ci_high"])},
        "calibration": {"slope": float(calib["slope"]), "intercept": float(calib["intercept"])},
        "n": n,
        "n_events": n_events,
        "single_class": False,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_external_validation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run whole suite + lint/type**

Run: `uv run pytest -q`, `uv run ruff check src/rrt_liberation/evaluation/external_validation.py tests/test_external_validation.py`, `uv run mypy src/rrt_liberation/evaluation/external_validation.py`. All clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/evaluation/external_validation.py tools/rrt-liberation/tests/test_external_validation.py
git commit -m "feat(rrt): add external_validate (no-optimism external metrics)"
```

---

## Task 4: validate.py + config + smoke test

**Files:**
- Create: `conf/validate.yaml`
- Create: `pipeline/validate.py`
- Test: `tests/test_validate_smoke.py`

- [ ] **Step 1: Create `conf/validate.yaml`**

```yaml
defaults:
  - cohort: eicu
  - liberation: def_7d
  - _self_

seed: 42
n_boot: 200
fixed_model_path: outputs/model_logistic.json
paths:
  data_dir: data
  output_dir: outputs
```

- [ ] **Step 2: Write the failing smoke test** `tests/test_validate_smoke.py`:

```python
import json
from pathlib import Path

from pipeline.run import run_pipeline
from pipeline.validate import run_external_validation
from tests.fixtures.synth import (
    make_eicu_events,
    make_eicu_labs,
    make_two_class_events,
    make_two_class_labs,
)


def test_validate_end_to_end(tmp_path):
    # 1) Train a logistic model on MIMIC synthetic (sub-project A path) and save it.
    mimic = tmp_path / "data" / "mimic"
    mimic.mkdir(parents=True)
    make_two_class_events().to_csv(mimic / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(mimic / "labs.csv", index=False)
    train_out = tmp_path / "train_out"
    run_pipeline(
        events_csv=mimic / "crrt_events.csv",
        labs_csv=mimic / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=["urine_output_24h"],
        model_name="logistic",
        coefficients={},
        output_dir=train_out,
        seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        n_boot=20,
    )
    model_path = train_out / "model_logistic.json"
    assert model_path.exists()

    # 2) Stage eICU synthetic data and externally validate the FIXED model.
    eicu = tmp_path / "data" / "eicu"
    eicu.mkdir(parents=True)
    make_eicu_events().to_csv(eicu / "crrt_events.csv", index=False)
    make_eicu_labs().to_csv(eicu / "labs.csv", index=False)
    val_out = tmp_path / "val_out"

    result = run_external_validation(
        events_csv=eicu / "crrt_events.csv",
        labs_csv=eicu / "labs.csv",
        cohort_name="eicu",
        min_off_hours=24.0,
        liberation_name="def_7d",
        fixed_model_path=model_path,
        output_dir=val_out,
        n_boot=20,
        seed=42,
    )

    assert (val_out / "external_validation.json").exists()
    assert (val_out / "calibration_external.png").exists()
    assert (val_out / "external_table1.csv").exists()
    assert "auroc" in result and "ci_low" in result["auroc"] and "ci_high" in result["auroc"]
    # the saved JSON records the source model (proves a fixed model was applied, not retrained)
    saved = json.loads((val_out / "external_validation.json").read_text())
    assert Path(saved["source_model"]).name == "model_logistic.json"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_validate_smoke.py -v`
Expected: FAIL (`ModuleNotFoundError: pipeline.validate`)

- [ ] **Step 4: Implement** `pipeline/validate.py`:

```python
"""External-validation entrypoint: apply a FIXED model to an external cohort.

`run_external_validation` is a plain function (unit-testable). `main` wires Hydra
config to it. This entrypoint never trains a model.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import hydra
from omegaconf import DictConfig

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation import save_calibration_plot
from rrt_liberation.evaluation.external_validation import external_validate
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model.persistence import load_model_json
from rrt_liberation.reporting import build_table1
from rrt_liberation.utils import read_csv, set_seed, write_csv, write_json

logger = logging.getLogger(__name__)


def run_external_validation(
    events_csv: str | Path,
    labs_csv: str | Path,
    cohort_name: str,
    min_off_hours: float,
    liberation_name: str,
    fixed_model_path: str | Path,
    output_dir: str | Path,
    n_boot: int = 200,
    seed: int = 42,
) -> Dict[str, object]:
    """Load a fixed model and validate it on an external cohort (no retraining)."""
    set_seed(seed)
    output_dir = Path(output_dir)

    model = load_model_json(fixed_model_path)
    horizon = get_horizon(liberation_name)
    builder = CohortFactory(cohort_name)(min_off_hours=min_off_hours)
    events = read_csv(events_csv)
    labs = read_csv(labs_csv)
    cohort = builder.build(events=events, horizon_hours=horizon)

    predictors = list(model.predictors) if model.predictors is not None else []
    feats = build_features(cohort, labs=labs, predictors=predictors)
    y = feats["success"].to_numpy()

    res = external_validate(model, feats[predictors], feats["success"], n_boot=n_boot, seed=seed)

    save_calibration_plot(y, model.predict_proba(feats[predictors]), output_dir / "calibration_external.png")
    payload = dict(res)
    payload["source_model"] = str(fixed_model_path)
    write_json(payload, output_dir / "external_validation.json")
    write_csv(build_table1(feats).reset_index(names="variable"), output_dir / "external_table1.csv")

    logger.info("External validation: %s", res["auroc"])
    return res


@hydra.main(version_base=None, config_path="../conf", config_name="validate")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_external_validation(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        cohort_name=cfg.cohort.name,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        fixed_model_path=cfg.fixed_model_path,
        output_dir=cfg.paths.output_dir,
        n_boot=cfg.n_boot,
        seed=cfg.seed,
    )


if __name__ == "__main__":
    main()
```

NOTE: `save_calibration_plot` on a single-class external cohort still works (it just plots points); that's acceptable. If `predictors` is empty the build would fail — but a loaded LogisticModel always has predictors, so this is fine.

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `uv run pytest tests/test_validate_smoke.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Run the Hydra CLI end-to-end**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic data/eicu
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False)"
uv run python -m pipeline.run model=logistic   # produces outputs/model_logistic.json
uv run python -c "from tests.fixtures.synth import make_eicu_events, make_eicu_labs; make_eicu_events().to_csv('data/eicu/crrt_events.csv', index=False); make_eicu_labs().to_csv('data/eicu/labs.csv', index=False)"
uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu
```
Expected: `outputs/external_validation.json`, `outputs/calibration_external.png`, `outputs/external_table1.csv` created. Confirm `cd /Users/llmmkkooii/github/pushtest && git status --porcelain` shows nothing under `data/` or `outputs/`.

- [ ] **Step 7: Lint/type**

Run: `uv run ruff check pipeline/ conf/ tests/test_validate_smoke.py` and `uv run mypy pipeline/validate.py`. Clean. (If mypy flags `model.predictors`/`predict_proba` on the loaded model, note that `load_model_json` returns `LogisticModel` so attributes are typed; fix trivially if needed.)

- [ ] **Step 8: Commit (code/config/test only)**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/conf/validate.yaml tools/rrt-liberation/pipeline/validate.py tools/rrt-liberation/tests/test_validate_smoke.py
git commit -m "feat(rrt): add validate.py entrypoint for fixed-model external validation"
```

---

## Task 5: README + verification sweep

**Files:**
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Update the README `## Status` section body** to:

```markdown
## Status

Implemented: MIMIC cohort, liberation labeling, feature builder, UNDERSCORE
benchmark, development logistic model (JSON-persisted, bootstrap optimism-corrected
internal validation), **eICU external validation** (fixed model applied to an
eICU cohort, no retraining), discrimination + calibration, TRIPOD flow + Table 1.

Run external validation: `uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu`
-> writes `external_validation.json`, `calibration_external.png`, `external_table1.csv` to `outputs/`.

Stubbed (later iteration-2 sub-projects): RF/XGBoost reference model, UNDERSCORE/
urine external comparison, DCA, definition sensitivity (72h/14d), MICE imputation,
full MIMIC/eICU feature engineering, AmsterdamUMCdb.
```

Keep the rest of the README (title, Run section, PHI boundary) unchanged.

- [ ] **Step 2: Verification sweep**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
uv run ruff check .
uv run mypy src pipeline tests
uv run pytest -q
```
All clean/green. Report counts. Fix trivial issues; report non-trivial.

- [ ] **Step 3: Reproducibility check**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic data/eicu
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False)"
uv run python -m pipeline.run model=logistic
uv run python -c "from tests.fixtures.synth import make_eicu_events, make_eicu_labs; make_eicu_events().to_csv('data/eicu/crrt_events.csv', index=False); make_eicu_labs().to_csv('data/eicu/labs.csv', index=False)"
uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu 2>&1 | grep "External validation" | tee /tmp/ev1.log
uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu 2>&1 | grep "External validation" | tee /tmp/ev2.log
diff /tmp/ev1.log /tmp/ev2.log && echo "IDENTICAL"
```
Expected: "IDENTICAL".

- [ ] **Step 4: PHI check + commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git ls-files tools/rrt-liberation/ | grep -E '(data|outputs)/' || echo "clean"
git add tools/rrt-liberation/README.md
git commit -m "docs(rrt): document eICU external validation in README"
```

---

## Definition of Done

- `uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu` loads the fixed model and writes `external_validation.json`, `calibration_external.png`, `external_table1.csv`.
- `uv run pytest -q` green (existing + new: eicu_fixtures, eicu_cohort, external_validation, validate smoke).
- `ruff check .` and `mypy src pipeline tests` clean.
- Same-seed validate reruns produce identical external metrics.
- `data/`/`outputs/` gitignored; no credentialed data committed; the model is applied (not retrained) — `external_validation.json` records `source_model`.
- Existing training path (`run.py`, `model=*`) and all prior tests unchanged.

---

## Self-Review

- **Spec coverage:** §1 decisions (eICU→canonical → Task 2; validate.py → Task 4; no-optimism external eval → Task 3; preprocessing-from-JSON → load_model_json in Task 4) ✓. §2 architecture (all files) ✓. §3 conversion/cohort contract → Task 2 + fixtures Task 1 ✓. §4 external_validate + validate flow → Tasks 3,4 ✓. §5 tests → every task TDD ✓.
- **Placeholder scan:** none — full code in every step.
- **Type consistency:** `make_eicu_events`/`make_eicu_labs`, `EicuCohortBuilder.build(events, horizon_hours)` + `_EICU_T0`, `external_validate(model, X, y, n_boot, seed)` returning `{auroc:{point,ci_low,ci_high}, calibration:{slope,intercept}, n, n_events, single_class}`, `run_external_validation(events_csv, labs_csv, cohort_name, min_off_hours, liberation_name, fixed_model_path, output_dir, n_boot, seed)`, `load_model_json`, `build_features(cohort, labs, predictors)` — consistent across tasks. eICU labs use the canonical `stay_id/itemid/valuenum` schema so `build_features` works unchanged.
