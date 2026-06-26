# RRT Liberation & Recovery Analysis Pipeline

Reproducible, config-driven pipeline for the **IHD-focused** dialysis liberation /
kidney-recovery study (with CRRT comparison), developed on MIMIC-IV and externally
validated on eICU-CRD. Archetype: Uchino 2009 (BEST Kidney). See
`../../plan/research-proposal-rrt-liberation.md`.

Two outcome paths share one modality-aware core:

- **Liberation (per attempt)** — short-term: no RRT resumption within a horizon (7d primary).
- **Recovery (per stay)** — long-term: alive and dialysis-free for ≥14 days before discharge
  (LIBERATE-D-style dialysis independence).

**Modality-aware** throughout: IHD (intermittent) uses a longer off-threshold (72h) than
CRRT (continuous, 24h) so routine alternate-day IHD sessions are not mis-counted as weaning
attempts. Every attempt/stay is tagged `modality_class` for the IHD-vs-CRRT comparison (RQ2).

## Run (synthetic dev data)

    uv sync
    uv run pytest -q
    uv run python -m pipeline.run cohort=mimic liberation=def_7d model=logistic

Artifacts are written to `outputs/` (gitignored); Hydra records each run's config under
`outputs/<date>/<time>/.hydra/`.

## Pipelines

| Command | Purpose |
|---|---|
| `python -m pipeline.run model=logistic` | Develop the liberation model (internal validation, calibration, DCA) |
| `python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu` | External validation on eICU (no retraining) |
| `python -m pipeline.benchmark cohort=eicu` | Compare dev vs urine-only (Uchino) vs UNDERSCORE + external DCA |
| `python -m pipeline.sensitivity cohort=mimic` | Liberation-definition robustness (72h/7d/14d) |
| `python -m pipeline.stratify model=logistic` | **RQ2**: liberation metrics + coefficients per modality (IHD vs CRRT) |
| `python -m pipeline.recovery model=logistic` | **Recovery** outcome, per-stay, modality-stratified |
| `python -m pipeline.extract_mimic` | MIMIC raw tables → `data/mimic/{crrt_events,labs,flags,stays}.csv` |
| `python -m pipeline.extract_eicu` | eICU raw tables → `data/eicu/{crrt_events,labs,flags,stays}.csv` |

Extraction captures **both IHD and CRRT** (`build_*_rrt_events`) and stay-level discharge +
death (`build_*_stays`, recovery inputs). Configure itemids/terms in `conf/extract_*.yaml`
and **verify them against your DB version** (entries marked 要確認).

## PHI boundary (read before using real data)

- Real credentialed data (MIMIC-IV, eICU-CRD) goes under `data/`, which is gitignored and
  MUST NOT be shared with Claude or any external AI service.
- All development and tests use synthetic fixtures (`tests/fixtures/`) with no real values.
- Run real-data analyses locally yourself. Only aggregate, non-PHI outputs (e.g. AUROC) are
  appropriate to discuss with an assistant.
- `conf/model/underscore.yaml` ships with placeholder zero coefficients — replace with the
  published values from Chaïbi et al., 2026 before any real run.
- Full procedure: `../../plan/real-data-execution-runbook.md`.

## Status

Implemented (synthetic skeleton, end-to-end):

- **Modality-aware liberation detection** (IHD/CRRT, per-class off-threshold, `modality_class`).
- MIMIC/eICU extraction (IHD + CRRT events, labs, flags, stays).
- Liberation path: cohort → UNDERSCORE-6 features → logistic model (JSON-persisted, bootstrap
  optimism-corrected internal validation) → eICU external validation → DCA → definition
  sensitivity → benchmark (dev vs urine-only vs UNDERSCORE) → TRIPOD flow + Table 1.
- **RQ2 modality stratification** (liberation and recovery).
- **Recovery path**: stays → per-stay recovery cohort → per-stay features → modality-stratified.

Future / optional (not required for the skeleton): Lee 2019 recovery benchmark predictors
(baseline eGFR / pre-admission Hb / liver disease) as config-driven features; RF/XGBoost
reference; AmsterdamUMCdb; 24h urine windowing; MICE.
