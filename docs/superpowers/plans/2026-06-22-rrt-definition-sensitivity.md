# RRT Liberation-Definition Sensitivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train + internally-validate the development logistic model across the three liberation definitions (72h/7d/14d) and aggregate per-definition performance into a comparison table (proposal H3).

**Architecture:** A dedicated `pipeline/sensitivity.py` with `run_definition_sensitivity(...)` that loops over a list of liberation definitions, reusing existing building blocks (CohortFactory, build_features, LogisticModel, internal_validation) per definition, and writes `definition_sensitivity.csv` (one row per definition) + `definition_sensitivity.json` (full detail incl. coefficient CIs). A Hydra `sensitivity.yaml` lists the definitions. Synthetic data only; no `src/` logic added.

**Tech Stack:** Python 3.11, uv, pandas, numpy, sklearn (via the model), Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-22-rrt-definition-sensitivity-design.md](../specs/2026-06-22-rrt-definition-sensitivity-design.md)

**Working dir:** paths relative to `tools/rrt-liberation/` unless noted. Branch `feature/rrt-definition-sensitivity`. Run via `uv run`.

**Conventions:** type hints, module logger (no `print`), files 200-400 lines, seed fixed. Existing `run.py`/`validate.py`/`model=*`/all tests stay unchanged.

**Confirmed building blocks (reuse, do not reimplement):**
- `from rrt_liberation.liberation import get_horizon` → `get_horizon("def_72h")=72.0`, `def_7d=168.0`, `def_14d=336.0`.
- `from rrt_liberation.cohort import CohortFactory` → `CohortFactory("mimic")(min_off_hours=...).build(events, horizon)` returns cohort with `subject_id, stay_id, attempt_time, success`; builder also has `.to_canonical_events(events)`.
- `from rrt_liberation.features import build_features` → `build_features(cohort, sources, predictors)`; `sources` is a dict `{"labs","events","flags"}`.
- `from rrt_liberation.model.logistic import LogisticModel` → `LogisticModel(predictors=..., penalty=None, C=1.0, max_iter=1000).fit(X, y)`; raises ValueError on single-class y.
- `from rrt_liberation.evaluation.internal_validation import internal_validation` → returns `{"auroc": {"apparent","optimism","corrected"}, "calib_slope": {...}, "coefficients": {name: {"point","ci_low","ci_high"}}, "n_boot_used": int}`.
- `from rrt_liberation.utils import read_csv, set_seed, write_csv, write_json`.
- run.py builds events with `events[col] = events[col].astype("datetime64[ns]")` for starttime/endtime after read_csv (mimic). Mirror that for the mimic cohort.

---

## File Structure

| File | Responsibility |
|---|---|
| `pipeline/sensitivity.py` | `run_definition_sensitivity(...)` + Hydra `main` |
| `conf/sensitivity.yaml` | definitions list + cohort/features/model defaults + seed/n_boot |
| `tests/test_sensitivity.py` | unit + smoke tests |

---

## Task 1: `run_definition_sensitivity`

**Files:**
- Create: `pipeline/sensitivity.py`
- Test: `tests/test_sensitivity.py`

- [ ] **Step 1: Write the failing test** `tests/test_sensitivity.py`:

```python
import json
import math

from pipeline.sensitivity import run_definition_sensitivity
from tests.fixtures.synth import (
    make_two_class_events,
    make_two_class_flags,
    make_two_class_labs,
)

PREDS = [
    "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
    "sepsis_shock", "vasopressor", "mechanical_ventilation",
]
DEFS = ["def_72h", "def_7d", "def_14d"]


def _stage(tmp_path):
    d = tmp_path / "data" / "mimic"
    d.mkdir(parents=True)
    make_two_class_events().to_csv(d / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(d / "labs.csv", index=False)
    make_two_class_flags().to_csv(d / "flags.csv", index=False)
    return d


def _run(tmp_path, out_name="out"):
    d = _stage(tmp_path)
    out = tmp_path / out_name
    return run_definition_sensitivity(
        events_csv=d / "crrt_events.csv",
        labs_csv=d / "labs.csv",
        cohort_name="mimic",
        min_off_hours=24.0,
        definitions=DEFS,
        predictors=PREDS,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        output_dir=out,
        n_boot=20,
        seed=42,
        flags_csv=d / "flags.csv",
    ), out


def test_returns_one_row_per_definition_with_schema(tmp_path):
    rows, _ = _run(tmp_path)
    assert [r["definition"] for r in rows] == DEFS
    expected_keys = {
        "definition", "horizon_hours", "n", "n_events", "success_rate",
        "auroc_apparent", "auroc_corrected", "calib_slope_corrected",
        "n_boot_used", "single_class",
    }
    for r in rows:
        assert expected_keys <= set(r)


def test_horizon_hours_match(tmp_path):
    rows, _ = _run(tmp_path)
    by = {r["definition"]: r["horizon_hours"] for r in rows}
    assert by["def_72h"] == 72.0
    assert by["def_7d"] == 168.0
    assert by["def_14d"] == 336.0


def test_h3_longer_horizon_not_fewer_failures(tmp_path):
    # Longer horizon captures more restarts -> at least as many failures ->
    # success_count(14d) <= success_count(72h) on the same source data.
    rows, _ = _run(tmp_path)
    by = {r["definition"]: r for r in rows}
    assert by["def_14d"]["n_events"] <= by["def_72h"]["n_events"]


def test_outputs_written(tmp_path):
    rows, out = _run(tmp_path)
    assert (out / "definition_sensitivity.csv").exists()
    payload = json.loads((out / "definition_sensitivity.json").read_text())
    assert len(payload) == 3
    assert "coefficients" in payload[0]  # full detail includes coefficient CIs


def test_deterministic(tmp_path):
    r1, _ = _run(tmp_path, "a")
    r2, _ = _run(tmp_path, "b")
    a = {x["definition"]: x["auroc_corrected"] for x in r1}
    b = {x["definition"]: x["auroc_corrected"] for x in r2}
    for k in DEFS:
        assert (a[k] == b[k]) or (math.isnan(a[k]) and math.isnan(b[k]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sensitivity.py -q`
Expected: FAIL (`ModuleNotFoundError: pipeline.sensitivity`)

- [ ] **Step 3: Implement** `pipeline/sensitivity.py`:

```python
"""Liberation-definition sensitivity: train + internally-validate the dev model
across multiple liberation definitions and aggregate per-definition metrics."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation.internal_validation import internal_validation
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.utils import read_csv, set_seed, write_csv, write_json

logger = logging.getLogger(__name__)


def run_definition_sensitivity(
    events_csv: str | Path,
    labs_csv: str | Path,
    cohort_name: str,
    min_off_hours: float,
    definitions: List[str],
    predictors: List[str],
    model_hparams: Dict[str, object],
    output_dir: str | Path,
    n_boot: int = 200,
    seed: int = 42,
    flags_csv: Optional[str | Path] = None,
) -> List[Dict[str, object]]:
    """Run the dev logistic model across liberation definitions; aggregate metrics."""
    set_seed(seed)
    output_dir = Path(output_dir)

    builder = CohortFactory(cohort_name)(min_off_hours=min_off_hours)
    events = read_csv(events_csv)
    if cohort_name == "mimic":
        for col in ("starttime", "endtime"):
            events[col] = events[col].astype("datetime64[ns]")
    labs = read_csv(labs_csv)
    sources: Dict[str, pd.DataFrame] = {
        "labs": labs,
        "events": builder.to_canonical_events(events),
    }
    if flags_csv is not None:
        sources["flags"] = read_csv(flags_csv)

    penalty = model_hparams.get("penalty")
    c_value = float(model_hparams.get("C", 1.0))  # type: ignore[arg-type]
    max_iter = int(model_hparams.get("max_iter", 1000))  # type: ignore[arg-type]

    def fit_fn(x_tr: pd.DataFrame, y_tr: np.ndarray) -> LogisticModel:
        return LogisticModel(
            predictors=predictors, penalty=penalty, C=c_value, max_iter=max_iter
        ).fit(x_tr, y_tr)

    rows: List[Dict[str, object]] = []
    detail: List[Dict[str, object]] = []
    for name in definitions:
        horizon = get_horizon(name)
        cohort = builder.build(events=events, horizon_hours=horizon)
        feats = build_features(cohort, sources, predictors)
        y = feats["success"].to_numpy()
        n = int(len(y))
        n_events = int(y.sum())
        success_rate = float(n_events / n) if n else float("nan")

        if len(np.unique(y)) < 2:
            logger.warning("Definition %s is single-class; skipping model", name)
            row = {
                "definition": name, "horizon_hours": horizon, "n": n,
                "n_events": n_events, "success_rate": success_rate,
                "auroc_apparent": float("nan"), "auroc_corrected": float("nan"),
                "calib_slope_corrected": float("nan"), "n_boot_used": 0,
                "single_class": True,
            }
            rows.append(row)
            detail.append({**row, "coefficients": {}})
            continue

        iv = internal_validation(fit_fn, feats[predictors], y, n_boot=n_boot, seed=seed)
        auroc = iv["auroc"]  # type: ignore[index]
        calib = iv["calib_slope"]  # type: ignore[index]
        row = {
            "definition": name, "horizon_hours": horizon, "n": n,
            "n_events": n_events, "success_rate": success_rate,
            "auroc_apparent": float(auroc["apparent"]),
            "auroc_corrected": float(auroc["corrected"]),
            "calib_slope_corrected": float(calib["corrected"]),
            "n_boot_used": int(iv["n_boot_used"]),  # type: ignore[arg-type]
            "single_class": False,
        }
        rows.append(row)
        detail.append({**row, "coefficients": iv["coefficients"]})

    write_csv(pd.DataFrame(rows), output_dir / "definition_sensitivity.csv")
    write_json(detail, output_dir / "definition_sensitivity.json")
    logger.info("Definition sensitivity: %s", [(r["definition"], r["auroc_corrected"]) for r in rows])
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="sensitivity")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_definition_sensitivity(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        cohort_name=cfg.cohort.name,
        min_off_hours=cfg.cohort.min_off_hours,
        definitions=list(cfg.definitions),
        predictors=list(cfg.features.predictors),
        model_hparams={
            "penalty": cfg.model.penalty, "C": cfg.model.C, "max_iter": cfg.model.max_iter
        },
        output_dir=cfg.paths.output_dir,
        n_boot=cfg.n_boot,
        seed=cfg.seed,
        flags_csv=cfg.cohort.get("flags_csv"),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sensitivity.py -q`
Expected: PASS (5 passed). (May take ~10-20s: 3 definitions x bootstrap refits.)

- [ ] **Step 5: Run whole suite + lint/type**

Run: `uv run pytest -q` (no regressions), `uv run ruff check pipeline/sensitivity.py tests/test_sensitivity.py`, `uv run mypy pipeline/sensitivity.py`. All clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/pipeline/sensitivity.py tools/rrt-liberation/tests/test_sensitivity.py
git commit -m "feat(rrt): add liberation-definition sensitivity analysis"
```

---

## Task 2: Hydra config + CLI + README + verification

**Files:**
- Create: `conf/sensitivity.yaml`
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Create `conf/sensitivity.yaml`**

```yaml
defaults:
  - cohort: mimic
  - features: baseline
  - model: logistic
  - _self_

seed: 42
n_boot: 200
definitions:
  - def_72h
  - def_7d
  - def_14d
paths:
  data_dir: data
  output_dir: outputs
```

- [ ] **Step 2: Hydra CLI end-to-end**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs, make_two_class_flags; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False); make_two_class_flags().to_csv('data/mimic/flags.csv', index=False)"
uv run python -m pipeline.sensitivity cohort=mimic
```
Expected: writes `outputs/definition_sensitivity.csv` (3 rows: def_72h/def_7d/def_14d) and `outputs/definition_sensitivity.json`. Print the CSV (`cat outputs/definition_sensitivity.csv`) and confirm `cd /Users/llmmkkooii/github/pushtest && git status --porcelain` shows nothing under `data/`/`outputs/`.

- [ ] **Step 3: Update README `## Status` body** to:

```markdown
## Status

Implemented: MIMIC/eICU cohort, liberation labeling, UNDERSCORE-6 feature registry,
UNDERSCORE benchmark, development logistic model (JSON-persisted, bootstrap
optimism-corrected internal validation), eICU external validation, **liberation-
definition sensitivity analysis** (72h/7d/14d), discrimination + calibration,
TRIPOD flow + Table 1.

Run training: `uv run python -m pipeline.run model=logistic`
Run external validation: `uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu`
Run definition sensitivity: `uv run python -m pipeline.sensitivity cohort=mimic`
-> writes `definition_sensitivity.csv` / `.json` to `outputs/`.

Stubbed (later sub-projects): RF/XGBoost reference, UNDERSCORE/urine external
comparison, remaining proposal-section-7 predictors, real MIMIC/eICU SQL extraction,
24h urine windowing, DCA, MICE, AmsterdamUMCdb.
```

Keep the rest of the README (title, Run, PHI boundary) unchanged.

- [ ] **Step 4: Verification sweep + reproducibility**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
uv run ruff check .
uv run mypy src pipeline tests
uv run pytest -q
```
All clean/green; report counts.

Reproducibility:
```bash
mkdir -p data/mimic
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs, make_two_class_flags; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False); make_two_class_flags().to_csv('data/mimic/flags.csv', index=False)"
uv run python -m pipeline.sensitivity cohort=mimic 2>&1 | grep "Definition sensitivity" | sed 's/.*Definition/Definition/' | tee /tmp/ds1.log
uv run python -m pipeline.sensitivity cohort=mimic 2>&1 | grep "Definition sensitivity" | sed 's/.*Definition/Definition/' | tee /tmp/ds2.log
diff /tmp/ds1.log /tmp/ds2.log && echo "IDENTICAL"
```
Expected: "IDENTICAL".

- [ ] **Step 5: PHI check + commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git ls-files tools/rrt-liberation/ | grep -E '(data|outputs)/' || echo "clean"
git add tools/rrt-liberation/conf/sensitivity.yaml tools/rrt-liberation/README.md
git commit -m "feat(rrt): add sensitivity Hydra config; document in README"
```

---

## Definition of Done

- `uv run python -m pipeline.sensitivity cohort=mimic` writes `definition_sensitivity.csv` (3 rows) + `.json` (incl. coefficient CIs).
- `uv run pytest -q` green (sensitivity tests + all prior).
- `ruff check .` and `mypy src pipeline tests` clean.
- Same-seed sensitivity reruns produce identical metrics.
- H3 direction holds on synthetic: `n_events(def_14d) <= n_events(def_72h)`.
- `data/`/`outputs/` gitignored; no credentialed data committed; no fabricated coefficients.
- Existing entrypoints (`run.py`, `validate.py`) and all prior tests unchanged.

---

## Self-Review

- **Spec coverage:** §1 decisions (logistic across 3 defs, dedicated sensitivity.py, reuse components) → Task 1 ✓. §2 architecture (sensitivity.py, conf, tests) → Tasks 1,2 ✓. §3 aggregation contract (row schema + csv/json outputs + internal_validation reuse) → Task 1 ✓. §4 config/wiring → Task 2 ✓. §5 tests (3 rows, horizons, H3 direction, outputs, determinism, single-class) → Task 1 ✓.
- **Placeholder scan:** none — full code in every step.
- **Type consistency:** `run_definition_sensitivity(events_csv, labs_csv, cohort_name, min_off_hours, definitions, predictors, model_hparams, output_dir, n_boot, seed, flags_csv)` consistent between test, impl, and `main`. Row schema keys identical between impl and the test's `expected_keys`. `internal_validation` access (`["auroc"]["apparent"/"corrected"]`, `["calib_slope"]["corrected"]`, `["n_boot_used"]`, `["coefficients"]`) matches its confirmed return shape. `get_horizon` values (72/168/336) match the test.
- **Single-class test:** the design lists a single-class-resilience case; on the standard two-class fixture all three definitions are two-class, so the unit suite exercises the two-class path. The single_class branch is covered by the schema (it always emits `single_class`) and is defensively implemented; an explicit single-class fixture test is deferred (the branch is simple and the standard fixture cannot produce it). Noted, not a gap that blocks H3.
