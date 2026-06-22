# Design: RRT Liberation-Definition Sensitivity Analysis (iteration 2, sub-project D)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Depends on: A (dev logistic model), E (UNDERSCORE-6 features)
> Specs: [A](2026-06-21-rrt-dev-logistic-model-design.md) / [E](2026-06-22-rrt-underscore6-features-design.md) / [iteration1](2026-06-21-rrt-liberation-pipeline-design.md)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-22

---

## 0. 位置づけとスコープ

iteration 2 の定義感度分析（proposal H3）。離脱定義（72h/7d/14d）で離脱成功ラベルが変わるため、
**開発ロジスティックモデルを各定義で学習・内部検証し、定義ごとの性能・予測因子を1表に集約**する。
「定義により性能・予測因子が系統的に変化するか」を定量化（H3）。すべて合成データ。credentialed data は使わない・コミットしない。

**Non-goals**: UNDERSCORE/尿量との比較（H2）、新しい離脱定義の追加、退院時透析非依存定義、DCA(C)、MICE、実データ抽出。

## 1. 確定した設計判断（brainstorm 合意）

| 項目 | 決定 |
|---|---|
| 比較対象 | 開発ロジスティックモデルを def_72h/def_7d/def_14d の3定義で比較 |
| 起動 | 専用 `pipeline/sensitivity.py`（Hydra）。validate.py と同じ「既存部品の直接再利用」（run_pipeline は呼ばない） |
| 集約 | 定義ごと n・成功率・AUROC(apparent/corrected)・calib slope・n_boot_used・係数CI |
| 出力 | `definition_sensitivity.csv`（主表）＋ `definition_sensitivity.json`（係数含む全詳細） |

## 2. アーキテクチャ

```
pipeline/sensitivity.py     # 新規 Hydra: 定義ループ→各定義で学習+internal_validation→集約
conf/sensitivity.yaml       # 新規: defaults(cohort=mimic, features=baseline, model=logistic),
                            #   definitions:[def_72h,def_7d,def_14d], seed, n_boot
tests/test_sensitivity.py   # 新規
```
`src/` に新規ロジックは追加しない（既存部品の合成のみ。新しい統計・離脱ロジックは書かない）。

`run_definition_sensitivity(events_csv, labs_csv, cohort_name, min_off_hours, definitions, predictors, model_hparams, output_dir, n_boot, seed, flags_csv=None) -> list[dict]`:
- events/labs/(flags) を1回読み、`sources={labs, events=builder.to_canonical_events(events), flags?}` を構築。
- 各定義でループ：`horizon=get_horizon(name)` → `cohort=builder.build(events,horizon)` → `feats=build_features(cohort, sources, predictors)` → `y`。
  - 2クラス：`fit_fn=lambda Xtr,ytr: LogisticModel(predictors,penalty,C,max_iter).fit(...)` ＋ `internal_validation(fit_fn, feats[predictors], y, n_boot, seed)`。
  - 単一クラス：学習スキップ、`single_class=True`、メトリクスNaN、n等は記録。
- 集約：定義ごと1行を `definition_sensitivity.csv`、全詳細（係数CI含む）を `definition_sensitivity.json`。

既存 `run.py`/`validate.py`/`model=*`/全テストは不変（Dは読み取り専用の合成オーケストレーション）。`def_72h/def_7d/def_14d` と `get_horizon`(72/168/336h) は既存。

## 3. 集約契約（出力スキーマ）

戻り値 `list[dict]`（`definitions` 順）、各要素:
```python
{
  "definition": "def_7d", "horizon_hours": 168.0,
  "n": 36, "n_events": 24, "success_rate": 0.667,
  "auroc_apparent": 0.59, "auroc_corrected": 0.54,
  "calib_slope_corrected": -0.04, "n_boot_used": 200,
  "single_class": false,
}
```
出力（`outputs/` gitignore）:
- `definition_sensitivity.csv`：数値列のみ（係数除く）を定義ごと1行（H3主表）。`write_csv(pd.DataFrame(rows))`。
- `definition_sensitivity.json`：各定義の全詳細＋`coefficients`（internal_validation の係数CI辞書）。`write_json`（NaN→null）。

取得元（既存関数の再利用）:
- n / n_events / success_rate：その定義のコホートから算出（n=0 は success_rate=NaN）。
- auroc_apparent/corrected, calib_slope_corrected, n_boot_used, coefficients：`internal_validation` の戻り
  （`iv["auroc"]["apparent"/"corrected"]`, `iv["calib_slope"]["corrected"]`, `iv["n_boot_used"]`, `iv["coefficients"]`）。
- 単一クラス：`single_class=True`、AUROC/calib/coefficients は NaN/空、n系は記録。

決定性: seed固定で corrected AUROC・係数・success_rate が再現一致。PHI: 実データはローカルのみ、出力は集計のみ。

## 4. config・配線

`conf/sensitivity.yaml`:
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
`pipeline/sensitivity.py` の `main`（Hydra）が cfg から `run_definition_sensitivity` を呼ぶ。
`model_hparams={"penalty": cfg.model.penalty, "C": cfg.model.C, "max_iter": cfg.model.max_iter}`、`flags_csv=cfg.cohort.get("flags_csv")`。
CLI: `uv run python -m pipeline.sensitivity cohort=mimic`。既存エントリ（config.yaml/validate.yaml, run.py, validate.py）は不変。

## 5. テスト戦略

合成データ（実PHIなし）、`tests/test_sensitivity.py`:
| 検証 | 内容 |
|---|---|
| 3定義の行 | 3行返す／各行に契約スキーマのキー一式 |
| horizon整合 | def_72h→72.0, def_7d→168.0, def_14d→336.0 |
| H3方向性 | 同一コホートで horizon が長いほど再開を捕捉 → 14d の success_count ≤ 72h の success_count |
| 出力生成 | `definition_sensitivity.csv`(3行) ＋ `definition_sensitivity.json`(係数含む) |
| 決定性 | 同seed2回で corrected AUROC・success_rate 一致 |
| 単一クラス耐性 | 全success合成で single_class=True・NaNメトリクス・n記録（クラッシュなし） |

統合：2クラス＋6変数（flags含む）fixtureで端から端まで。検証ループ：`ruff → mypy src pipeline tests → pytest` 緑。後方互換：既存エントリ・全テスト不変。

## 6. 次段（このspecの外）

- C DCA（decision curve）、H2（UNDERSCORE/尿量比較）、退院時透析非依存定義、§7残り予測子、MICE、実MIMIC/eICU抽出、AmsterdamUMCdb。
