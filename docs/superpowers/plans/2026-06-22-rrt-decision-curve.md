# RRT Decision Curve Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Vickers net-benefit decision curve analysis and wire it into the development-logistic training path so each run emits a DCA table + plot.

**Architecture:** Implement `decision_curve(y, p, thresholds=None)` (treat-all / treat-none references) and `save_dca_plot(curve, path)` in the existing `evaluation/dca.py` stub, export them, and add a DCA output to `run.py`'s logistic branch (alongside the calibration plot). Decision-curve computation is deterministic; synthetic data only.

**Tech Stack:** Python 3.11, uv, numpy, pandas, matplotlib (Agg), Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-22-rrt-decision-curve-design.md](../specs/2026-06-22-rrt-decision-curve-design.md)

**Working dir:** paths relative to `tools/rrt-liberation/` unless noted. Branch `feature/rrt-decision-curve`. Run via `uv run`.

**Conventions:** type hints, module logger ok (no `print`), `__all__`, files 200-400 lines.

**Confirmed current state:**
- `src/rrt_liberation/evaluation/dca.py` is a stub: `decision_curve(y, p) -> dict` raises NotImplementedError; `__all__ = ["decision_curve"]`; imports only numpy.
- `src/rrt_liberation/evaluation/__init__.py` exports `auroc_with_ci, calibration_slope_intercept, save_calibration_plot`.
- `pipeline/run.py` logistic branch calls `save_calibration_plot(y, model.predict_proba(feats[predictors]), output_dir / "calibration.png")` (one line); imports from `rrt_liberation.evaluation` are a multi-line block (`auroc_with_ci, calibration_slope_intercept, save_calibration_plot`); `write_csv`/`pd` already imported.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/rrt_liberation/evaluation/dca.py` | `decision_curve` + `save_dca_plot` |
| `src/rrt_liberation/evaluation/__init__.py` | export the two new names |
| `pipeline/run.py` | emit `dca.csv` + `dca.png` in the logistic branch |
| `tests/test_dca.py`, `tests/test_pipeline_smoke.py` | tests |

---

## Task 1: `decision_curve` + `save_dca_plot`

**Files:**
- Modify: `src/rrt_liberation/evaluation/dca.py` (replace stub)
- Modify: `src/rrt_liberation/evaluation/__init__.py`
- Test: `tests/test_dca.py`

- [ ] **Step 1: Write the failing test** `tests/test_dca.py`:

```python
import numpy as np

from rrt_liberation.evaluation import decision_curve, save_dca_plot


def test_treat_none_is_zero_and_prevalence():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p)
    assert all(v == 0.0 for v in curve["net_benefit_none"])
    assert curve["prevalence"] == 0.5


def test_net_benefit_hand_calc_at_threshold_0_5():
    # y=[0,0,1,1], p=[.1,.2,.8,.9]; at pt=0.5: pred=[F,F,T,T] -> TP=2, FP=0, N=4, w=1
    # NB_model = 2/4 - 0*1 = 0.5 ; NB_all = 0.5 - 0.5*1 = 0.0
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p, thresholds=[0.5])
    assert abs(curve["net_benefit_model"][0] - 0.5) < 1e-12
    assert abs(curve["net_benefit_all"][0] - 0.0) < 1e-12


def test_treat_all_formula_at_threshold_0_25():
    # prevalence=0.5, w=0.25/0.75=1/3 -> NB_all = 0.5 - 0.5*(1/3)
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p, thresholds=[0.25])
    expected = 0.5 - 0.5 * (0.25 / 0.75)
    assert abs(curve["net_benefit_all"][0] - expected) < 1e-12


def test_perfect_separation_model_ge_all():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p, thresholds=[0.5])
    assert curve["net_benefit_model"][0] >= curve["net_benefit_all"][0]


def test_default_grid_and_override():
    y = np.array([0, 1, 0, 1])
    p = np.array([0.3, 0.7, 0.4, 0.6])
    default = decision_curve(y, p)
    assert 0.0 < min(default["thresholds"]) <= max(default["thresholds"]) < 1.0
    assert len(default["net_benefit_model"]) == len(default["thresholds"])
    custom = decision_curve(y, p, thresholds=[0.2, 0.4, 0.6])
    assert custom["thresholds"] == [0.2, 0.4, 0.6]


def test_deterministic():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    assert decision_curve(y, p) == decision_curve(y, p)


def test_save_dca_plot_writes_png(tmp_path):
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p)
    path = tmp_path / "sub" / "dca.png"
    save_dca_plot(curve, path)
    assert path.exists() and path.stat().st_size > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dca.py -q`
Expected: FAIL (`ImportError: cannot import name 'save_dca_plot'` / decision_curve raises NotImplementedError)

- [ ] **Step 3: Implement** — replace `src/rrt_liberation/evaluation/dca.py` ENTIRELY with:

```python
"""Decision curve analysis (Vickers net benefit)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np


def decision_curve(
    y: np.ndarray, p: np.ndarray, thresholds: Optional[Sequence[float]] = None
) -> Dict[str, object]:
    """Vickers net benefit across threshold probabilities.

    Positive class is the event (y == 1). At threshold pt a case is flagged
    positive when p >= pt. Returns the model curve plus treat-all/treat-none
    references and the prevalence. Deterministic.
    """
    y_arr = np.asarray(y)
    p_arr = np.asarray(p, dtype=float)
    n = int(len(y_arr))
    if thresholds is None:
        grid = np.arange(0.01, 1.00, 0.01)
    else:
        grid = np.asarray(thresholds, dtype=float)
    prevalence = float(y_arr.mean()) if n else float("nan")

    nb_model: List[float] = []
    nb_all: List[float] = []
    for pt in grid:
        flagged = p_arr >= pt
        tp = int(np.sum(flagged & (y_arr == 1)))
        fp = int(np.sum(flagged & (y_arr == 0)))
        weight = pt / (1.0 - pt)
        nb_model.append(tp / n - (fp / n) * weight)
        nb_all.append(prevalence - (1.0 - prevalence) * weight)

    return {
        "thresholds": grid.tolist(),
        "net_benefit_model": nb_model,
        "net_benefit_all": nb_all,
        "net_benefit_none": [0.0] * len(grid),
        "prevalence": prevalence,
    }


def save_dca_plot(curve: Dict[str, object], path: str | Path) -> None:
    """Save a decision-curve plot (model / treat-all / treat-none) to a local PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = curve["thresholds"]
    fig, ax = plt.subplots()
    ax.plot(t, curve["net_benefit_model"], label="Model")
    ax.plot(t, curve["net_benefit_all"], "--", label="Treat all")
    ax.plot(t, curve["net_benefit_none"], ":", color="grey", label="Treat none")
    ax.set_xlabel("Threshold probability")
    ax.set_ylabel("Net benefit")
    ax.set_title("Decision curve")
    ax.legend()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


__all__ = ["decision_curve", "save_dca_plot"]
```

Update `src/rrt_liberation/evaluation/__init__.py` to:

```python
from rrt_liberation.evaluation.calibration import (
    calibration_slope_intercept,
    save_calibration_plot,
)
from rrt_liberation.evaluation.dca import decision_curve, save_dca_plot
from rrt_liberation.evaluation.discrimination import auroc_with_ci

__all__ = [
    "auroc_with_ci",
    "calibration_slope_intercept",
    "save_calibration_plot",
    "decision_curve",
    "save_dca_plot",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dca.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Whole suite + lint/type**

Run: `uv run pytest -q` (no regressions), `uv run ruff check src/rrt_liberation/evaluation/ tests/test_dca.py`, `uv run mypy src/rrt_liberation/evaluation/dca.py`. All clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/evaluation/dca.py tools/rrt-liberation/src/rrt_liberation/evaluation/__init__.py tools/rrt-liberation/tests/test_dca.py
git commit -m "feat(rrt): implement decision curve analysis (net benefit)"
```

---

## Task 2: Wire DCA into run.py + smoke + README + verification

**Files:**
- Modify: `pipeline/run.py`
- Modify: `tests/test_pipeline_smoke.py`
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Update the import block in `pipeline/run.py`** — replace:

```python
from rrt_liberation.evaluation import (
    auroc_with_ci,
    calibration_slope_intercept,
    save_calibration_plot,
)
```

with:

```python
from rrt_liberation.evaluation import (
    auroc_with_ci,
    calibration_slope_intercept,
    decision_curve,
    save_calibration_plot,
    save_dca_plot,
)
```

- [ ] **Step 2: Add the DCA output in the logistic branch** — find the line:

```python
        save_calibration_plot(y, model.predict_proba(feats[predictors]), output_dir / "calibration.png")
```

and insert immediately AFTER it:

```python
        dca = decision_curve(y, model.predict_proba(feats[predictors]))
        write_csv(
            pd.DataFrame(
                {
                    "threshold": dca["thresholds"],
                    "net_benefit_model": dca["net_benefit_model"],
                    "net_benefit_all": dca["net_benefit_all"],
                    "net_benefit_none": dca["net_benefit_none"],
                }
            ),
            output_dir / "dca.csv",
        )
        save_dca_plot(dca, output_dir / "dca.png")
```

(Leave the underscore branch and everything else unchanged.)

- [ ] **Step 3: Add a DCA assertion to the existing 6-feature logistic smoke** — in `tests/test_pipeline_smoke.py`, inside `test_pipeline_logistic_six_features`, after the existing `coef = pd.read_csv(out_dir / "coefficients.csv")` / `assert len(coef) >= 6` lines, append:

```python
    assert (out_dir / "dca.csv").exists()
    assert (out_dir / "dca.png").exists()
```

- [ ] **Step 4: Run smoke + whole suite**

Run: `uv run pytest tests/test_pipeline_smoke.py -q` then `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Hydra CLI end-to-end**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs, make_two_class_flags; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False); make_two_class_flags().to_csv('data/mimic/flags.csv', index=False)"
uv run python -m pipeline.run model=logistic
```
Expected: `outputs/dca.csv` (columns threshold/net_benefit_model/net_benefit_all/net_benefit_none) and `outputs/dca.png` are created. Print `head -3 outputs/dca.csv`. Confirm `cd /Users/llmmkkooii/github/pushtest && git status --porcelain` shows nothing under `data/`/`outputs/`.

- [ ] **Step 6: Update README `## Status` body** to:

```markdown
## Status

Implemented: MIMIC/eICU cohort, liberation labeling, UNDERSCORE-6 feature registry,
UNDERSCORE benchmark, development logistic model (JSON-persisted, bootstrap
optimism-corrected internal validation), eICU external validation, liberation-
definition sensitivity analysis (72h/7d/14d), **decision curve analysis** (net
benefit), discrimination + calibration, TRIPOD flow + Table 1.

Run the dev model: `uv run python -m pipeline.run model=logistic` -> writes
`model_logistic.json`, `model_performance.json`, `coefficients.csv`, `calibration.png`,
`dca.csv`, `dca.png` to `outputs/`.
Run external validation: `uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu`
Run definition sensitivity: `uv run python -m pipeline.sensitivity cohort=mimic`

Stubbed (later sub-projects): RF/XGBoost reference model, UNDERSCORE/urine external
comparison, external-cohort DCA, remaining proposal-section-7 predictors, real
MIMIC/eICU SQL extraction, 24h urine windowing, MICE, AmsterdamUMCdb.
```

Keep the rest of the README (title, Run, PHI boundary) unchanged.

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
git add tools/rrt-liberation/pipeline/run.py tools/rrt-liberation/tests/test_pipeline_smoke.py tools/rrt-liberation/README.md
git commit -m "feat(rrt): emit decision curve (dca.csv/png) from the logistic pipeline"
```

---

## Definition of Done

- `uv run python -m pipeline.run model=logistic` writes `dca.csv` + `dca.png` alongside the existing logistic outputs.
- `uv run pytest -q` green (DCA unit tests + 6-feature smoke + all prior).
- `ruff check .` and `mypy src pipeline tests` clean.
- Net benefit matches hand calculation (NB_model=0.5, NB_all=0.0 at pt=0.5 on the canonical 4-point example); treat-none is all zeros; deterministic.
- `data/`/`outputs/` gitignored; no credentialed data committed.
- Backward compatible: `model=underscore` path, validate.py, and all prior tests unchanged.

---

## Self-Review

- **Spec coverage:** §1 decisions (Vickers NB, treat-all/none, positive=success via caller, default grid 0.01-0.99, dca.csv/png, run.py-only) → Tasks 1,2 ✓. §2 architecture (dca.py, __init__, run.py, tests) ✓. §3 NB math + save_dca_plot → Task 1 ✓. §4 run.py wiring/output → Task 2 ✓. §5 tests (treat-none, prevalence, hand-calc, treat-all formula, perfect-separation, grid, determinism, plot, smoke) → Tasks 1,2 ✓.
- **Placeholder scan:** none — full code each step.
- **Type consistency:** `decision_curve(y, p, thresholds=None) -> dict` keys (`thresholds`, `net_benefit_model`, `net_benefit_all`, `net_benefit_none`, `prevalence`) identical between impl, tests, and run.py wiring. `save_dca_plot(curve, path)` consistent. run.py uses `dca["thresholds"]` etc. matching the returned keys.
- **Hand-calc check:** at pt=0.5 on y=[0,0,1,1], p=[.1,.2,.8,.9]: pred=[F,F,T,T], TP=2 FP=0 N=4 w=1 → NB_model=0.5, NB_all=prevalence(0.5)-0.5*1=0.0. Tests pass explicit `thresholds=[0.5]` / `[0.25]` to avoid floating-point grid-membership issues.
