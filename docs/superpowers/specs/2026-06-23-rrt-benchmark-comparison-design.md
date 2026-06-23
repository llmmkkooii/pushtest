# Design: RRT External Benchmark Comparison (H2) + External DCA (iteration 2, sub-project F)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Depends on: A (dev logistic), B (eICU external validation), C (DCA), E (UNDERSCORE-6 features)
> Specs: [B](2026-06-22-rrt-eicu-external-validation-design.md) / [C](2026-06-22-rrt-decision-curve-design.md) / [A](2026-06-21-rrt-dev-logistic-model-design.md)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-23

---

## 0. 位置づけとスコープ

iteration 2 の **H2**（開発モデルは UNDERSCORE/尿量単独を上回る or 同等で較正が優れる）＋ 外部コホートDCA。
eICU外部コホート上で「開発ロジスティック / 尿量単独 / UNDERSCORE」の3固定モデルを、外部 AUROC・較正・net benefit で公平比較する。
既存の `external_validate`(B)・`decision_curve`(C)・`UnderscoreModel`/`LogisticModel`(A)・`build_features`(E) の合成。すべて合成データ。credentialed data は使わない・コミットしない。

**Non-goals**: AmsterdamUMCdb、退院時透析非依存定義、§7残り予測子、MICE、実データSQL抽出、RF/XGBoost参照、開発(MIMIC)上での内部ベンチ比較（外部のみ）。

## 1. 確定した設計判断（brainstorm 合意）

| 項目 | 決定 |
|---|---|
| 尿量単独 | 単変量ロジスティックを MIMIC で学習・JSON保存→eICUに固定適用（true external） |
| 起動 | 専用 `pipeline/benchmark.py`（validate=単一, benchmark=複数比較で責務分離） |
| モデル集合 | dev_logistic(JSON,6) / urine_only(JSON,1) / underscore(config係数,生特徴量) |
| 評価 | 同一eICUコホート・同一y・同一閾値で external_validate＋decision_curve |
| 出力 | benchmark_comparison.csv ＋ dca_external.csv ＋ dca_external.png |

## 2. アーキテクチャ

```
pipeline/benchmark.py     # 新規 Hydra: run_benchmark_comparison(...) + _save_comparison_dca ヘルパー
conf/benchmark.yaml       # 新規: cohort=eicu, liberation, features, fixed_model_path/urine_model_path,
                          #   underscore_coefficients, n_boot, seed
tests/test_benchmark.py   # 新規
```
`src/` には新規ロジックを足さない（既存部品の合成）。既存 run.py/validate.py/model=*/全テストは不変。

`run_benchmark_comparison(events_csv, labs_csv, cohort_name, min_off_hours, liberation_name, fixed_model_path, urine_model_path, underscore_coefficients, predictors, output_dir, n_boot, seed, flags_csv=None) -> List[Dict]`:
- cohort＋sources＋`feats = build_features(cohort, sources, predictors)`（6変数の生値）を1回構築。
- 3固定モデルを `(name, model, model_predictors)` で揃える:
  1. `dev_logistic` = `load_model_json(fixed_model_path)`、preds=model.predictors（6）
  2. `urine_only` = `load_model_json(urine_model_path)`、preds=model.predictors（["urine_output_24h"]）
  3. `underscore` = `UnderscoreModel(underscore_coefficients)`、preds=`[k for k in coefficients if k != "intercept"]`
- 各モデルで `external_validate(model, feats[preds], feats["success"], n_boot, seed)` と `decision_curve(y, model.predict_proba(feats[preds]))`。
- 出力（§3）。

## 3. 3モデルの適用契約 + 出力

### 適用契約
- `feats` は6変数の**生値**。dev/urine の LogisticModel は predict_proba 内部で**自前Preprocessorが標準化**（MIMIC学習時統計＝true external）。UNDERSCORE は**生値×係数**の sigmoid（標準化なし、元論文が生変数係数）。
- predictors：dev/urine は `model.predictors`（JSON格納）、UNDERSCORE は係数キー−{intercept}。
- 2本のモデルJSONはユーザーが事前生成（dev=`pipeline.run model=logistic`、urine=predictors単独で run）。スモークは tmp で両方を学習・保存してから benchmark。
- UNDERSCORE係数：benchmark.yaml の `underscore_coefficients`（合成ではプレースホルダ0、実データ前に Chaibi 2026 から転記）。
- 欠落予測子：UNDERSCORE は既存仕様で警告＋0扱い、dev/urine は Preprocessor がスキーマ厳守。
- 単一クラスeICU：external_validate が NaN＋single_class、DCAは省略（堅牢）。

### 出力（`outputs/` gitignore）
- `benchmark_comparison.csv`：モデルごと1行（入力順）、列 `model, auroc_point, auroc_ci_low, auroc_ci_high, calib_slope, calib_intercept, n, n_events, single_class`。取得元は各 external_validate。
- `dca_external.csv`：`threshold` ＋ `net_benefit_<model>`（3列）＋ `net_benefit_all` ＋ `net_benefit_none`。all/none はモデル非依存（最初のモデル曲線から、prevalence共通）。閾値グリッドは全モデル共通（既定0.01–0.99）。
- `dca_external.png`：3モデルの net benefit ＋ treat-all（破線）＋ treat-none（点線grey）重ね描き。`benchmark.py` 内 `_save_comparison_dca`（Agg, headless, parent dir 作成）。`evaluation/dca.py` の `save_dca_plot` は不変。
- 戻り値：`run_benchmark_comparison` は `benchmark_comparison` の各行 `List[Dict]` を返す。

## 4. テスト戦略

合成（実PHIなし）、`tests/test_benchmark.py`:
| 検証 | 内容 |
|---|---|
| 3モデル比較 | MIMICで dev(6)＋urine単独 を学習・保存→eICUで benchmark→ 3行（dev_logistic/urine_only/underscore）、各行に契約キー一式 |
| UNDERSCORE導出 | 係数キー−intercept が predictors になり predict_proba が動く（生値） |
| 出力生成 | benchmark_comparison.csv(3行) / dca_external.csv(net_benefit_<model>3列＋all/none) / dca_external.png |
| 閾値整合 | 全モデルの dca が同一閾値グリッド長 |
| 決定性 | 同seed2回で auroc_point 一致 |
| 単一クラス耐性 | 全success合成eICUで single_class=True・NaN・クラッシュなし |

統合スモーク：train dev → train urine単独 → benchmark。検証ループ：`ruff → mypy src pipeline tests → pytest` 緑。後方互換：既存全テスト・他エントリ不変。

## 5. config・配線

`conf/benchmark.yaml`:
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
`main`(Hydra) が cfg から `run_benchmark_comparison` を呼ぶ（predictors=cfg.features.predictors, flags_csv=cfg.cohort.get("flags_csv")）。CLI: `uv run python -m pipeline.benchmark cohort=eicu`。

## 6. 次段（このspecの外）

- AmsterdamUMCdb、退院時透析非依存定義、§7残り予測子、MICE、実MIMIC/eICU SQL抽出、RF/XGBoost参照、開発内部でのベンチ比較。
