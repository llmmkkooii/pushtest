# RRT External Benchmark Comparison (H2) + External DCA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare the dev logistic model, a urine-only logistic, and UNDERSCORE on the same eICU external cohort (external AUROC + calibration + decision curve) — proposal H2 plus external DCA.

**Architecture:** A new `pipeline/benchmark.py` with `run_benchmark_comparison(...)` that loads/constructs three fixed models, applies each to the eICU features, and reuses `external_validate` + `decision_curve` to emit `benchmark_comparison.csv`, `dca_external.csv`, and an overlaid `dca_external.png`. Reuse-only; no `src/` logic added. Synthetic data only.

**Tech Stack:** Python 3.11, uv, pandas, numpy, matplotlib (Agg), Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-23-rrt-benchmark-comparison-design.md](../specs/2026-06-23-rrt-benchmark-comparison-design.md)

**Working dir:** paths relative to `tools/rrt-liberation/`. Branch `feature/rrt-benchmark-comparison`. Run via `uv run`.

**Conventions:** type hints, module logger (no print), files 200-400 lines, seed fixed. Existing `run.py`/`validate.py`/`sensitivity.py`/`model=*`/all tests stay unchanged.

**Confirmed building blocks (reuse, do not reimplement):**
- `load_model_json(path) -> LogisticModel` (has `.predictors`, `.predict_proba`).
- `UnderscoreModel(coefficients)` (has `.coefficients`, `.predict_proba` over RAW feature columns by coefficient name; requires "intercept" key).
- `external_validate(model, X, y, n_boot=200, seed=42)` → `{"auroc": {"point","ci_low","ci_high"}, "calibration": {"slope","intercept"}, "n", "n_events", "single_class"}`.
- `decision_curve(y, p, thresholds=None)` → `{"thresholds","net_benefit_model","net_benefit_all","net_benefit_none","prevalence"}`.
- `build_features(cohort, sources, predictors)`; `CohortFactory`; `get_horizon`; `read_csv/write_csv/set_seed`; `BaseModel` (base class of LogisticModel and UnderscoreModel).
- `run_pipeline(..., model_name="logistic", predictors=..., flags_csv=..., output_dir=...)` writes `model_logistic.json` to `output_dir` — used in tests to produce the dev + urine-only model files.
- Fixtures: `make_two_class_events/labs/flags` (MIMIC, 2-class), `make_eicu_events/labs/flags` (eICU, 2-class). eICU labs are canonical (urine 226559 + creatinine 50912).

---

## File Structure

| File | Responsibility |
|---|---|
| `pipeline/benchmark.py` | `run_benchmark_comparison(...)` + `_save_comparison_dca` + Hydra `main` |
| `conf/benchmark.yaml` | cohort/liberation/features defaults + model paths + underscore coefficients |
| `tests/test_benchmark.py` | unit + smoke tests |

---

## Task 1: `run_benchmark_comparison`

**Files:**
- Create: `pipeline/benchmark.py`
- Test: `tests/test_benchmark.py`

- [ ] **Step 1: Write the failing test** `tests/test_benchmark.py`:

```python
import math

from pipeline.benchmark import run_benchmark_comparison
from pipeline.run import run_pipeline
from tests.fixtures.synth import (
    make_eicu_events,
    make_eicu_flags,
    make_eicu_labs,
    make_two_class_events,
    make_two_class_flags,
    make_two_class_labs,
)

SIX = [
    "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
    "sepsis_shock", "vasopressor", "mechanical_ventilation",
]
UNDERSCORE_COEFS = {
    "intercept": -0.5, "urine_output_24h": 0.001, "baseline_creatinine": 0.2,
    "crrt_duration_hours": -0.01, "sepsis_shock": 0.3, "vasopressor": 0.2,
    "mechanical_ventilation": 0.1,
}


def _train_models(tmp_path):
    mimic = tmp_path / "data" / "mimic"
    mimic.mkdir(parents=True)
    make_two_class_events().to_csv(mimic / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(mimic / "labs.csv", index=False)
    make_two_class_flags().to_csv(mimic / "flags.csv", index=False)
    dev_out = tmp_path / "dev"
    urine_out = tmp_path / "urine"
    common = dict(
        events_csv=mimic / "crrt_events.csv", labs_csv=mimic / "labs.csv",
        min_off_hours=24.0, liberation_name="def_7d", model_name="logistic",
        coefficients={}, seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000}, n_boot=10,
        flags_csv=mimic / "flags.csv",
    )
    run_pipeline(predictors=SIX, output_dir=dev_out, **common)
    run_pipeline(predictors=["urine_output_24h"], output_dir=urine_out, **common)
    return dev_out / "model_logistic.json", urine_out / "model_logistic.json"


def _stage_eicu(tmp_path):
    eicu = tmp_path / "data" / "eicu"
    eicu.mkdir(parents=True)
    make_eicu_events().to_csv(eicu / "crrt_events.csv", index=False)
    make_eicu_labs().to_csv(eicu / "labs.csv", index=False)
    make_eicu_flags().to_csv(eicu / "flags.csv", index=False)
    return eicu


def _run(tmp_path, out_name="out"):
    dev_path, urine_path = _train_models(tmp_path)
    eicu = _stage_eicu(tmp_path)
    out = tmp_path / out_name
    rows = run_benchmark_comparison(
        events_csv=eicu / "crrt_events.csv",
        labs_csv=eicu / "labs.csv",
        cohort_name="eicu",
        min_off_hours=24.0,
        liberation_name="def_7d",
        fixed_model_path=dev_path,
        urine_model_path=urine_path,
        underscore_coefficients=UNDERSCORE_COEFS,
        predictors=SIX,
        output_dir=out,
        n_boot=10,
        seed=42,
        flags_csv=eicu / "flags.csv",
    )
    return rows, out


def test_three_models_with_schema(tmp_path):
    rows, _ = _run(tmp_path)
    assert [r["model"] for r in rows] == ["dev_logistic", "urine_only", "underscore"]
    keys = {
        "model", "auroc_point", "auroc_ci_low", "auroc_ci_high",
        "calib_slope", "calib_intercept", "n", "n_events", "single_class",
    }
    for r in rows:
        assert keys <= set(r)


def test_outputs_written(tmp_path):
    import pandas as pd

    _, out = _run(tmp_path)
    assert (out / "benchmark_comparison.csv").exists()
    assert (out / "dca_external.png").exists()
    dca = pd.read_csv(out / "dca_external.csv")
    for col in [
        "threshold", "net_benefit_dev_logistic", "net_benefit_urine_only",
        "net_benefit_underscore", "net_benefit_all", "net_benefit_none",
    ]:
        assert col in dca.columns


def test_deterministic(tmp_path):
    r1, _ = _run(tmp_path, "a")
    r2, _ = _run(tmp_path, "b")
    a = {x["model"]: x["auroc_point"] for x in r1}
    b = {x["model"]: x["auroc_point"] for x in r2}
    for k in a:
        assert (a[k] == b[k]) or (math.isnan(a[k]) and math.isnan(b[k]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_benchmark.py -q`
Expected: FAIL (`ModuleNotFoundError: pipeline.benchmark`)

- [ ] **Step 3: Implement** `pipeline/benchmark.py`:

```python
"""External benchmark comparison (H2): dev logistic vs urine-only vs UNDERSCORE on eICU."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import hydra
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation import decision_curve
from rrt_liberation.evaluation.external_validation import external_validate
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model.base import BaseModel
from rrt_liberation.model.persistence import load_model_json
from rrt_liberation.model.underscore import UnderscoreModel
from rrt_liberation.utils import read_csv, set_seed, write_csv

logger = logging.getLogger(__name__)


def _save_comparison_dca(
    curves: Dict[str, dict], ref_curve: dict, path: str | Path
) -> None:
    """Overlay each model's net-benefit curve plus treat-all/treat-none references."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    for name, curve in curves.items():
        ax.plot(curve["thresholds"], curve["net_benefit_model"], label=name)
    ax.plot(ref_curve["thresholds"], ref_curve["net_benefit_all"], "--", label="Treat all")
    ax.plot(
        ref_curve["thresholds"], ref_curve["net_benefit_none"], ":", color="grey", label="Treat none"
    )
    ax.set_xlabel("Threshold probability")
    ax.set_ylabel("Net benefit")
    ax.set_title("External decision curve")
    ax.legend()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def run_benchmark_comparison(
    events_csv: str | Path,
    labs_csv: str | Path,
    cohort_name: str,
    min_off_hours: float,
    liberation_name: str,
    fixed_model_path: str | Path,
    urine_model_path: str | Path,
    underscore_coefficients: Dict[str, float],
    predictors: List[str],
    output_dir: str | Path,
    n_boot: int = 200,
    seed: int = 42,
    flags_csv: Optional[str | Path] = None,
) -> List[Dict[str, object]]:
    """Compare three fixed models on the same external cohort (no retraining)."""
    set_seed(seed)
    output_dir = Path(output_dir)

    builder = CohortFactory(cohort_name)(min_off_hours=min_off_hours)
    events = read_csv(events_csv)
    labs = read_csv(labs_csv)
    horizon = get_horizon(liberation_name)
    cohort = builder.build(events=events, horizon_hours=horizon)
    sources: Dict[str, pd.DataFrame] = {
        "labs": labs,
        "events": builder.to_canonical_events(events),
    }
    if flags_csv is not None:
        sources["flags"] = read_csv(flags_csv)
    feats = build_features(cohort, sources, predictors)
    y = feats["success"]

    dev = load_model_json(fixed_model_path)
    urine = load_model_json(urine_model_path)
    under = UnderscoreModel(dict(underscore_coefficients))
    under_preds = [k for k in underscore_coefficients if k != "intercept"]

    models: List[Tuple[str, BaseModel, List[str]]] = [
        ("dev_logistic", dev, list(dev.predictors or [])),
        ("urine_only", urine, list(urine.predictors or [])),
        ("underscore", under, under_preds),
    ]

    rows: List[Dict[str, object]] = []
    curves: Dict[str, dict] = {}
    ref_curve: Optional[dict] = None
    for name, model, preds in models:
        res = external_validate(model, feats[preds], y, n_boot=n_boot, seed=seed)
        auroc = cast(Dict[str, float], res["auroc"])
        calib = cast(Dict[str, float], res["calibration"])
        rows.append(
            {
                "model": name,
                "auroc_point": auroc["point"],
                "auroc_ci_low": auroc["ci_low"],
                "auroc_ci_high": auroc["ci_high"],
                "calib_slope": calib["slope"],
                "calib_intercept": calib["intercept"],
                "n": res["n"],
                "n_events": res["n_events"],
                "single_class": res["single_class"],
            }
        )
        if not res["single_class"]:
            p = model.predict_proba(feats[preds])
            curve = decision_curve(y.to_numpy(), p)
            curves[name] = curve
            if ref_curve is None:
                ref_curve = curve

    write_csv(pd.DataFrame(rows), output_dir / "benchmark_comparison.csv")

    if ref_curve is not None:
        dca_df = pd.DataFrame({"threshold": ref_curve["thresholds"]})
        for name, curve in curves.items():
            dca_df[f"net_benefit_{name}"] = curve["net_benefit_model"]
        dca_df["net_benefit_all"] = ref_curve["net_benefit_all"]
        dca_df["net_benefit_none"] = ref_curve["net_benefit_none"]
        write_csv(dca_df, output_dir / "dca_external.csv")
        _save_comparison_dca(curves, ref_curve, output_dir / "dca_external.png")

    logger.info("Benchmark comparison: %s", [(r["model"], r["auroc_point"]) for r in rows])
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="benchmark")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_benchmark_comparison(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        cohort_name=cfg.cohort.name,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        fixed_model_path=cfg.fixed_model_path,
        urine_model_path=cfg.urine_model_path,
        underscore_coefficients=cast(
            Dict[str, float], OmegaConf.to_container(cfg.underscore_coefficients)
        ),
        predictors=list(cfg.features.predictors),
        output_dir=cfg.paths.output_dir,
        n_boot=cfg.n_boot,
        seed=cfg.seed,
        flags_csv=cfg.cohort.get("flags_csv"),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_benchmark.py -q`
Expected: PASS (3 passed). (Trains 2 models + 3-model external eval; ~15-30s.)

- [ ] **Step 5: Whole suite + lint/type**

Run: `uv run pytest -q` (no regressions), `uv run ruff check pipeline/benchmark.py tests/test_benchmark.py`, `uv run mypy pipeline/benchmark.py`. All clean. (If mypy flags `feats[preds]` or model attribute access, the casts above should cover it; if `dev.predictors` typing trips, the `or []` guard handles None — report anything unexpected.)

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/pipeline/benchmark.py tools/rrt-liberation/tests/test_benchmark.py
git commit -m "feat(rrt): add external benchmark comparison (dev vs urine vs UNDERSCORE)"
```

---

## Task 2: Hydra config + CLI + README + verification

**Files:**
- Create: `conf/benchmark.yaml`
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Create `conf/benchmark.yaml`**

```yaml
defaults:
  - cohort: eicu
  - liberation: def_7d
  - features: baseline
  - _self_

seed: 42
n_boot: 200
fixed_model_path: outputs/model_logistic.json
urine_model_path: outputs/urine_model_logistic.json
underscore_coefficients:
  intercept: 0.0
  urine_output_24h: 0.0
  baseline_creatinine: 0.0
  crrt_duration_hours: 0.0
  sepsis_shock: 0.0
  vasopressor: 0.0
  mechanical_ventilation: 0.0
paths:
  data_dir: data
  output_dir: outputs
```

- [ ] **Step 2: Hydra CLI end-to-end**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic data/eicu
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs, make_two_class_flags; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False); make_two_class_flags().to_csv('data/mimic/flags.csv', index=False)"
# dev model (6 features) -> outputs/model_logistic.json
uv run python -m pipeline.run model=logistic
# urine-only model -> save under outputs/urine_model_logistic.json (copy after a urine-only run)
uv run python -m pipeline.run model=logistic features.predictors='[urine_output_24h]' hydra.run.dir=. paths.output_dir=outputs_urine
cp outputs_urine/model_logistic.json outputs/urine_model_logistic.json
# eICU data
uv run python -c "from tests.fixtures.synth import make_eicu_events, make_eicu_labs, make_eicu_flags; make_eicu_events().to_csv('data/eicu/crrt_events.csv', index=False); make_eicu_labs().to_csv('data/eicu/labs.csv', index=False); make_eicu_flags().to_csv('data/eicu/flags.csv', index=False)"
uv run python -m pipeline.benchmark cohort=eicu
```
Expected: `outputs/benchmark_comparison.csv` (3 rows), `outputs/dca_external.csv`, `outputs/dca_external.png`. Print `cat outputs/benchmark_comparison.csv`. Confirm `cd /Users/llmmkkooii/github/pushtest && git status --porcelain` shows nothing under `data/`/`outputs/` (note: `outputs_urine/` is also gitignored only if under `outputs`? It is NOT — see note). 
**NOTE:** `outputs_urine/` is a NON-gitignored dir; remove it after the run: `rm -rf outputs_urine`. (Only `outputs/` and `data/` are gitignored.) The test suite does not use it; this is just for the manual CLI demo.

- [ ] **Step 3: Update README `## Status` body** to:

```markdown
## Status

Implemented: MIMIC/eICU cohort, liberation labeling, UNDERSCORE-6 feature registry,
UNDERSCORE benchmark, development logistic model (JSON-persisted, bootstrap
optimism-corrected internal validation), eICU external validation, liberation-
definition sensitivity (72h/7d/14d), decision curve analysis, **external benchmark
comparison** (dev vs urine-only vs UNDERSCORE with external DCA), discrimination +
calibration, TRIPOD flow + Table 1.

Run the dev model: `uv run python -m pipeline.run model=logistic`
Run external validation: `uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu`
Run definition sensitivity: `uv run python -m pipeline.sensitivity cohort=mimic`
Run benchmark comparison: `uv run python -m pipeline.benchmark cohort=eicu`
-> writes `benchmark_comparison.csv`, `dca_external.csv`, `dca_external.png` to `outputs/`.

Stubbed (later sub-projects): RF/XGBoost reference model, remaining proposal-
section-7 predictors, real MIMIC/eICU SQL extraction, 24h urine windowing, MICE,
AmsterdamUMCdb.
```

Keep the rest of the README (title, Run, PHI boundary) unchanged.

- [ ] **Step 4: Verification sweep**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
uv run ruff check .
uv run mypy src pipeline tests
uv run pytest -q
```
All clean/green; report counts.

- [ ] **Step 5: PHI check + commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git ls-files tools/rrt-liberation/ | grep -E '(data|outputs)/' || echo "clean"
git add tools/rrt-liberation/conf/benchmark.yaml tools/rrt-liberation/README.md
git commit -m "feat(rrt): add benchmark Hydra config; document in README"
```

---

## Definition of Done

- `uv run python -m pipeline.benchmark cohort=eicu` writes `benchmark_comparison.csv` (3 rows: dev_logistic/urine_only/underscore), `dca_external.csv`, `dca_external.png`.
- `uv run pytest -q` green (benchmark tests + all prior).
- `ruff check .` and `mypy src pipeline tests` clean.
- Same-seed reruns produce identical `auroc_point` per model.
- `data/`/`outputs/` gitignored; no credentialed data committed; UNDERSCORE coefficients are config placeholders (no fabrication).
- Existing entrypoints (`run.py`, `validate.py`, `sensitivity.py`) and all prior tests unchanged.

---

## Self-Review

- **Spec coverage:** §1 decisions (urine univariable fixed, dedicated benchmark.py, 3-model set, reuse external_validate+decision_curve) → Task 1 ✓. §2 architecture (benchmark.py, conf, tests) → Tasks 1,2 ✓. §3 application contract + outputs (benchmark_comparison.csv / dca_external.csv / dca_external.png, UNDERSCORE preds from coef keys, raw features) → Task 1 ✓. §4 tests → Task 1 ✓. §5 config/wiring → Tasks 1 (main) + 2 (yaml/CLI) ✓.
- **Placeholder scan:** none — full code each step.
- **Type consistency:** `run_benchmark_comparison(events_csv, labs_csv, cohort_name, min_off_hours, liberation_name, fixed_model_path, urine_model_path, underscore_coefficients, predictors, output_dir, n_boot, seed, flags_csv)` identical between test, impl, main. Row keys identical between impl and test's `keys` set. `external_validate` access (`["auroc"]["point"/"ci_low"/"ci_high"]`, `["calibration"]["slope"/"intercept"]`, `["n"]`, `["n_events"]`, `["single_class"]`) matches its return shape. `decision_curve` keys (`thresholds`, `net_benefit_model`, `net_benefit_all`, `net_benefit_none`) match usage. dca_external columns `net_benefit_<model>` match the test's expected column names (dev_logistic/urine_only/underscore).
- **Single-class note:** the design lists a single-class-resilience case; on the standard 2-class eICU fixture all models take the 2-class path, so the unit suite exercises the normal path and the determinism/schema/outputs tests. The single_class branch (skip DCA, NaN row) is defensively implemented; an explicit all-success eICU fixture test is deferred (the standard fixture cannot produce it). Noted.
