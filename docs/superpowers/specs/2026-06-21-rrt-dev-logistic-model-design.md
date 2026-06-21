# Design: RRT Development Logistic Model (iteration 2, sub-project A)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Parent iteration-1 spec: [2026-06-21-rrt-liberation-pipeline-design.md](2026-06-21-rrt-liberation-pipeline-design.md)
> Companion plans: [research-proposal-rrt-liberation.md](../../../plan/research-proposal-rrt-liberation.md)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-21

---

## 0. 位置づけとスコープ

iteration 2 は4つの独立サブシステム（A: 開発モデル学習 / B: eICU外部検証 / C: DCA / D: 定義感度分析）に分解した。
依存の核は **A**（B/C/D はいずれも本命の開発モデルを必要とする）。本specは **A のみ**を対象とする。

**A の定義**: config駆動の **解釈可能ロジスティック学習機構**を iteration-1 骨格に追加する。
具体的には、前処理（中央値代入＋欠測フラグ＋標準化）を内蔵した `LogisticModel`、bootstrap による
optimism補正＋係数CIの内部検証、固定モデルのJSON永続化、評価/レポート統合。

**Non-goals（A に含めない）**:
- RF/XGBoost 参照モデル（`model/tree.py` は stub のまま）
- MIMIC からの本格的な特徴量エンジニアリング（§7予測子セットの抽出）= 別サブプロジェクト
- 多重代入(MICE)（中央値代入＋欠測フラグで代替、MIは次段）
- eICU外部検証 / DCA / 定義感度分析の実走（B/C/D）

## 1. 確定した方法論（brainstorm 合意事項）

| 項目 | 決定 |
|---|---|
| 内部検証 | **全コホート学習＋bootstrap optimism補正**（TRIPOD標準）。train/test分割はしない |
| 欠測 | **中央値代入＋欠測フラグ列**。MICEは次段 |
| 永続化 | **JSON**（係数＋前処理統計）。pickleは使わない（透明性・査読性・version非依存） |
| 推定器 | sklearn `LogisticRegression`（lbfgs）。係数CIは bootstrap で取得（statsmodelsの分離問題回避） |
| 特徴量境界 | A は学習機構に集中。特徴量拡張は別サブプロジェクト。合成fixtureに人工多変量を足して検証 |

## 2. アーキテクチャ

```
src/rrt_liberation/
├── preprocessing/                    # 新規パッケージ
│   ├── __init__.py                   #   Preprocessor をexport, __all__
│   └── preprocessor.py               #   中央値代入＋欠測フラグ＋標準化, fit/transform, to_dict/from_dict
├── model/
│   ├── logistic.py                   #   stub→実装: LogisticModel(Preprocessor内蔵, sklearn)
│   │                                 #     fit / predict_proba / to_dict / from_dict / coefficients / intercept
│   ├── persistence.py                # 新規: save_model_json / load_model_json
│   └── (base.py/underscore.py/tree.py/__init__.py 既存・不変)
├── evaluation/
│   ├── internal_validation.py        # 新規: internal_validation()（bootstrap1本でoptimism補正＋係数CI）
│   └── (discrimination.py/calibration.py 再利用)
├── reporting/report.py               #   build_coefficient_table() 追加
└── utils/io.py                       #   write_json() 追加（NaN→null）
conf/model/logistic.yaml              # 新規: penalty/C/max_iter/save_path
pipeline/run.py                       #   model=logistic 経路（fit→internal_validation→persist→report）
tests/
├── fixtures/synth.py                 #   人工予測子(creatinine, non_renal_sofa, 欠測混入)を追加
├── test_preprocessing.py             # 新規
├── test_logistic_model.py            # 新規
├── test_persistence.py               # 新規
├── test_internal_validation.py       # 新規
└── test_pipeline_smoke.py            #   model=logistic スモーク追加（既存underscoreは不変）
```

設計原則:
- **前処理はモデル内蔵**。外部DB(B)では JSON を load するだけで同一前処理が再現 → true external validation を構造で保証。
- internal_validation は既存 `auroc_with_ci`/`calibration_slope_intercept` を再利用。責務が薄く独立テスト可能。
- coding-style 準拠（200-400行/ファイル、型ヒント、logger、`__all__`、factory/registry不変）。
- `model=underscore` 経路と全既存テストは不変（後方互換）。

## 3. 前処理・永続化の契約

### Preprocessor（fit/transform、統計を保持）
- `fit(X, predictors)`:
  1. 各予測子の中央値 `medians[col]` を学習・保持。
  2. **学習時に欠測のある予測子について** 欠測フラグ列 `<col>_missing`(0/1) を生成、対象を `flag_columns` に保持。
  3. 中央値代入後、各予測子の標準化 `means[col]`/`sds[col]` を保持（SD=0は1にフォールバック）。
  4. `feature_order`（元予測子＋flag列）を確定・保持。
- `transform(X)`: 保持統計で 代入→フラグ→標準化 を適用、`feature_order` 列順で返す。
  学習時に見た予測子が欠ければエラー。**学習時に無かった欠測が外部で出ても新規フラグ列は作らない**（スキーマ厳守）。
- `to_dict()`/`from_dict(d)`: 下記JSONの `preprocessing` ブロックと相互変換。

### JSONスキーマ（persistence.save_model_json）
```json
{
  "model_type": "logistic",
  "created_utc": "<呼び出し側が注入。省略可>",
  "predictors": ["urine_output_24h", "creatinine", "non_renal_sofa"],
  "preprocessing": {
    "medians": {"...": 0.0},
    "flag_columns": ["creatinine_missing"],
    "means": {"...": 0.0},
    "sds": {"...": 1.0},
    "feature_order": ["urine_output_24h", "creatinine", "non_renal_sofa", "creatinine_missing"]
  },
  "coefficients": {"...": 0.0},
  "intercept": -0.15,
  "hyperparameters": {"penalty": "none", "C": 1.0, "max_iter": 1000}
}
```
- `created_utc` は run側が注入（ワークフロー環境は時刻取得が制限されるため、モデル内部で時刻生成しない＝決定性を壊さない）。
- `from_dict` は sklearnオブジェクトを再構築せず、**係数＋前処理だけで sigmoid 計算**（version非依存・透明）。
- PHI境界: `save_path` は既定で `outputs/`(gitignore)配下。集計統計のみ、患者行データを含まない。実データ係数JSONもコミットしない。

## 4. 学習＋bootstrap内部検証フロー

### LogisticModel
- `fit(X, y)`: Preprocessor.fit→transform → `LogisticRegression(penalty,C,max_iter,solver="lbfgs").fit`。
  `.coefficients`(予測子→β)・`.intercept`・Preprocessor統計を公開。
- `predict_proba(X)`: Preprocessor.transform → P(success)。`from_dict` 復元時は係数で直接 sigmoid。
- 単一クラス `y` での `fit` は明確な `ValueError`。

### internal_validation（単一bootstrapループ、Harrell法）
```
internal_validation(fit_fn, X, y, n_boot=200, seed=42) -> dict
  model_app = fit_fn(X, y); p_app = model_app.predict_proba(X)
  auroc_app = AUROC(y, p_app); slope_app = calib_slope(y, p_app)
  for b in 1..n_boot:
    idx = rng.integers(0, n, n)                  # 復元抽出, seed固定で決定的
    if y[idx] 単一クラス: skip
    m_b = fit_fn(X[idx], y[idx])
    opt_auroc_b = AUROC(y[idx], m_b.predict(X[idx])) - AUROC(y, m_b.predict(X))
    opt_slope_b = (calib_slope同様, statsmodels非収束は try/except でskip)
    coef_samples[name].append(m_b.coefficients[name])
  optimism  = mean(opt_*_b); corrected = apparent - optimism
  coef_ci[name] = {point: model_app係数, ci_low/ci_high: percentile(coef_samples, [2.5,97.5])}
  return {auroc:{apparent,optimism,corrected}, calib_slope:{apparent,optimism,corrected},
          coefficients: coef_ci, n_boot_used}
```
- AUROC/calib slope は既存関数を再利用。係数CIは同じbootstrap標本から（二役）。
- calib slope の非収束は try/except でskipし、`n_boot_used` に有効回数を残す（沈黙の切り捨て禁止・logにも記録）。
- 決定性: `np.random.default_rng(seed)`＋sklearn lbfgs。

### pipeline 統合（model=logistic 経路）
1. cohort+features（既存）→ `X=feats[predictors]`, `y`。
2. `fit_fn = lambda Xtr,ytr: LogisticModel(hp).fit(Xtr,ytr)`。
3. `model = fit_fn(X,y)` → `save_model_json(model, outputs/model_logistic.json)`。
4. `internal_validation(fit_fn, X, y, n_boot, seed)`。
5. report: 既存 table1/flow ＋ §5の新規出力。
- 単一クラスyなら学習不能 → `ValueError`（テストは2クラスfixture）。`model=underscore` 経路は不変。

## 5. 評価/レポート出力

| 出力 | 形式 | 中身 |
|---|---|---|
| `model_logistic.json` | JSON | §3スキーマ。Bの外部検証で load する固定モデル成果物 |
| `model_performance.json` | JSON | AUROC・calib slope の apparent/optimism/corrected、`n_boot_used` |
| `coefficients.csv` | CSV | 予測子ごと β・OR(=exp β)・95%CI（exp変換）。index=予測子 |
| `calibration.png` | PNG | apparent reliability diagram（既存関数再利用） |
| `table1.csv`/`flow.txt` | 既存 | 不変 |

- 新規 `reporting.build_coefficient_table(coef_ci) -> DataFrame`（β・OR・CI、OR/CI=exp変換は report層に閉じる）。
- 新規 `utils.io.write_json(obj, path)`（NaN→null）。
- `run_pipeline` の戻り値: logistic経路で `auroc_corrected`・`calib_slope_corrected`・`n_boot_used` を含む。
- logistic固有出力は `model_logistic.*`/`coefficients.csv`/`model_performance.json` に分離（underscore出力と非衝突）。

## 6. テスト戦略

合成多変量fixture（実PHIなし）。`make_two_class_*` に `creatinine`・`non_renal_sofa`（欠測混入）を追加。

| 対象 | 検証 |
|---|---|
| `preprocessor` | 中央値代入正・フラグ列が欠測ありの列のみ・標準化後平均≈0/SD≈1・SD=0フォールバック・feature_order厳守・外部新規欠測でフラグ増やさない |
| `logistic` | predict_proba∈[0,1]・線形分離データでAUROC=1.0・to_dict→from_dict往復で予測完全一致・単一クラスでValueError |
| `persistence` | save→load往復で予測一致・JSON可読・created_utc欠如でもload可 |
| `internal_validation` | 同seedで決定的・corrected=apparent−optimism・過適合データでcorrected<apparent・係数CIがpointを含む・非収束時n_boot_used減少 |
| `build_coefficient_table` | OR=exp(β)・CIもexp・index/列名規約通り |
| smoke（統合） | 2クラス多変量で model=logistic 端から端まで→ 4出力生成＋戻り値にauroc_corrected/n_boot_used。既存underscoreスモーク不変 |

検証ループ: `ruff → mypy src pipeline tests → pytest -q` 緑。再現性: 同seed2回でcorrected AUROC・係数完全一致。

## 7. 次段（このspecの外）

- B: eICU外部検証（`cohort/eicu.py` 実装＋固定モデル `model_logistic.json` を load して適用）
- 特徴量エンジニアリング（§7予測子セットのMIMIC抽出）
- C: DCA / D: 定義感度分析（72h/14d）/ MICE
