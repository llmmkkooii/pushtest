# RRT Liberation Analysis Pipeline

Reproducible, config-driven pipeline for the CRRT liberation external-validation
study. Iteration 1 implements a MIMIC vertical slice with the UNDERSCORE benchmark.

## Run (synthetic dev data)

    uv sync
    uv run pytest -q
    uv run python -m pipeline.run cohort=mimic liberation=def_7d model=underscore

Artifacts (`table1.csv`, `flow.txt`, `calibration.png`) are written to `outputs/`
(gitignored). Note: the current config writes to a fixed `outputs/` dir, so repeated
runs overwrite prior artifacts; Hydra still records each run's config under
`outputs/<date>/<time>/.hydra/`. Timestamped artifact dirs are an iteration-2 improvement.

## PHI boundary (read before using real data)

- Real credentialed data (MIMIC-IV, eICU-CRD) goes under `data/`, which is
  gitignored and MUST NOT be shared with Claude or any external AI service.
- All development and tests use synthetic fixtures (`tests/fixtures/`) that mimic
  the schema with no real values.
- Run real-data analyses locally yourself. Only aggregate, non-PHI outputs
  (e.g. AUROC) are appropriate to discuss with an assistant.
- `conf/model/underscore.yaml` ships with placeholder zero coefficients. Replace
  them with the published values from Chaibi et al., 2026 before any real run.

## Status

Implemented: MIMIC cohort, liberation labeling, feature builder, UNDERSCORE
benchmark, **development logistic model** (median impute + missingness flags +
standardization, JSON-persisted, bootstrap optimism-corrected internal validation
with coefficient CIs), discrimination + calibration, TRIPOD flow + Table 1.

Run the dev model: `uv run python -m pipeline.run model=logistic` -> writes
`model_logistic.json`, `model_performance.json`, `coefficients.csv` to `outputs/`.

Stubbed (later iteration-2 sub-projects): RF/XGBoost reference model, eICU
external validation, DCA, definition sensitivity (72h/14d), MICE imputation,
full MIMIC feature engineering.
