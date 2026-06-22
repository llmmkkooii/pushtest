# Design: RRT eICU External Validation (iteration 2, sub-project B)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Depends on: sub-project A (dev logistic model) — [2026-06-21-rrt-dev-logistic-model-design.md](2026-06-21-rrt-dev-logistic-model-design.md)
> Parent iteration-1 spec: [2026-06-21-rrt-liberation-pipeline-design.md](2026-06-21-rrt-liberation-pipeline-design.md)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-22

---

## 0. 位置づけとスコープ

iteration 2 の4サブプロジェクト（A 開発モデル / B eICU外部検証 / C DCA / D 定義感度）のうち **B** を対象。
A で保存した固定モデル（`model_logistic.json`、前処理内蔵）を **再学習せず eICU コホートへ適用**し、
外部識別能・較正を測る（true external validation, proposal H1）。

**B の定義**: (1) `EicuCohortBuilder` を実装（eICU形入力→正準イベント変換→既存離脱ロジック再利用）、
(2) `external_validate`（optimism無しの外部評価）を新設、(3) 専用 Hydra エントリ `pipeline/validate.py`
（学習しない／固定モデルをload→適用）。すべて合成データ。credentialed data は使わない・コミットしない。

**Non-goals（B に含めない）**:
- 本格的な eICU SQL 抽出（treatment/dialysis テーブルの実マッピング）= 特徴量サブプロジェクト
- UNDERSCORE/尿量単独との外部比較（H2）= 後段
- AmsterdamUMCdb、DCA(C)、定義感度(D)、MICE

## 1. 確定した設計判断（brainstorm 合意）

| 項目 | 決定 |
|---|---|
| eICUスキーマ | **eICU形入力（分オフセット）→正準イベントに変換**し、既存 find_attempts/label_outcome を再利用 |
| 起動方法 | **専用コマンド `pipeline/validate.py`**（train と責務分離。学習しない） |
| 外部評価 | optimism補正なし。外部 AUROC＋bootstrap CI ＋ calibration slope/intercept（既存関数再利用） |
| 前処理 | モデルJSON内蔵の統計（MIMIC学習時）でeICUを変換。eICUで再fitしない |

## 2. アーキテクチャ

```
src/rrt_liberation/
├── cohort/eicu.py                    # stub→実装: EicuCohortBuilder
│                                     #   eICU形→正準events→find_attempts/label_outcome 再利用
├── evaluation/external_validation.py # 新規: external_validate(model, X, y, n_boot, seed)
pipeline/
└── validate.py                       # 新規 Hydra: load固定モデル→eICUコホート→predict→external_validate→出力
conf/
└── validate.yaml                     # 新規: fixed_model_path, defaults(cohort=eicu...), n_boot, seed
tests/
├── fixtures/synth.py                 # + make_eicu_events / make_eicu_labs（分オフセット, 2クラス）
├── test_eicu_cohort.py               # 新規
├── test_external_validation.py       # 新規
└── test_validate_smoke.py            # 新規（train→save→validate 端から端）
```

設計原則:
- **離脱ロジックはDB非依存の単一の真実**：EicuCohortBuilder は正準化のみ担当し、`find_attempts`/`label_outcome` を再利用。新しい離脱判定は書かない。
- **external_validate は internal_validation と別物**：optimism補正なし（外部適用＝楽観バイアスが構造的に無い）。
- **validate.py は学習しない**：`load_model_json` → eICUコホート → `model.predict_proba` → external_validate。前処理はモデル内蔵。
- 既存 `run.py`（学習）・`model=*`・`cohort` registry・全テストは不変（eicu は登録済み、中身を実装するだけ）。

## 3. eICU→正準変換とコホート契約

### 合成 eICU 入力スキーマ（実値なし）
- `make_eicu_events`: `patientunitstayid, treatmentoffset, treatmentstopoffset, treatmentstring`
  （`*offset` は unit入室からの分、`treatmentstring` は CRRT 記述）。2クラス（一部 horizon内再開＝失敗＋末尾持続オフ＝成功）。
- `make_eicu_labs`: `patientunitstayid, labresultoffset, labname, labresult`。`build_features` が urine を読める最小形。

### EicuCohortBuilder.build(events, horizon_hours) の契約
1. 正準化：
   - `subject_id = stay_id = patientunitstayid`
   - `starttime = _EICU_T0 + Timedelta(minutes=treatmentoffset)`、`endtime = _EICU_T0 + Timedelta(minutes=treatmentstopoffset)`（`_EICU_T0` は固定基準時刻、決定的）
   - `modality`：`treatmentstring` から CRRT を正規化（スケルトンは定数 "CVVHDF" でも可）
2. `find_attempts(events, min_off_hours=self.min_off_hours)` → `label_outcome(attempts, events, horizon_hours)` を再利用。
3. 返り値は MimicCohortBuilder と同一スキーマ `{subject_id, stay_id, attempt_time, success}` → 下流無改変。

### 特徴量整合
- eICU labs から 2A の予測子（スケルトンは `urine_output_24h`）を**同じ `build_features`** で構築。
  `make_eicu_labs` は urine を MIMIC同様の itemid(226559) 相当で供給（本格的な eICU labname マッピングは特徴量サブプロジェクト）。
- 前処理はモデルJSON内蔵（MIMIC学習時統計）で eICU を変換 ＝ true external validation。eICUで再fitしない。

### エラー条件
- eICUコホートが単一クラス → 外部AUROC計算不能 → 警告、AUROC=NaN・calibrationスキップ・`single_class=True`。
- 予測子が eICU 特徴量に欠ける → build_features が欠測列を作り、Preprocessor が学習時統計で代入（スキーマ厳守）。

## 4. external_validate と validate.py フロー

### evaluation/external_validation.py
```
external_validate(model, X, y, n_boot=200, seed=42) -> dict
  if len(unique(y)) < 2:
     log warning
     return {auroc:{point:nan,ci_low:nan,ci_high:nan},
             calibration:{slope:nan,intercept:nan},
             n:len(y), n_events:int(y.sum()), single_class:True}
  p = model.predict_proba(X)                    # 固定モデル適用、再学習なし
  disc = auroc_with_ci(y, p, n_boot, seed)      # 既存関数（点＋bootstrap CI）
  try: calib = calibration_slope_intercept(y, p)
  except Exception: calib = {slope:nan,intercept:nan}（log warning）
  return {auroc:{point,ci_low,ci_high}, calibration:{slope,intercept},
          n:len(y), n_events:int(y.sum()), single_class:False}
```
- optimism補正なし（external）。AUROC/calibration は既存評価関数を再利用。seed固定で決定的。

### pipeline/validate.py（Hydra @main）と関数 run_external_validation
1. `set_seed(seed)`。
2. `model = load_model_json(fixed_model_path)`（2Aの model_logistic.json）。
3. eICUコホート：`CohortFactory(cohort_name)(min_off_hours=...).build(events, horizon)`（eICU events/labs CSV を read）。
4. `feats = build_features(cohort, labs, predictors=model.predictors)`。
5. `res = external_validate(model, feats[model.predictors], feats["success"], n_boot, seed)`。
6. 出力（`outputs/` gitignore）:
   - `external_validation.json`：AUROC(点+CI)・calibration(slope/intercept)・n・n_events・single_class・`source_model`(パス)
   - `calibration_external.png`：外部 reliability diagram（既存 save_calibration_plot 再利用）
   - `external_table1.csv`：外部ベースライン（既存 build_table1 再利用）
7. `run_external_validation(...)` の戻り値に外部 AUROC点推定・CI・slope を含める（スモークテスト用）。

CLI: `uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu`。
PHI境界: load するモデルJSONは集計統計のみ。eICU実データは `data/eicu/`(gitignore)・ローカル、外部AIに渡さない。出力も `outputs/`。

## 5. テスト戦略

合成 eICU形 fixture（実PHIなし）。

| 対象 | 検証 |
|---|---|
| `cohort/eicu.py` | 分オフセット→正準時刻変換（既知offset→既知時刻）／返りスキーマ同一／既知の離脱試行・再開が正しくラベル化／2クラス |
| `evaluation/external_validation.py` | 既知データで AUROC・slope 手計算一致／**optimismキー無し**／同seedで決定的／単一クラスで NaN＋single_class=True／calibration非収束をログ |
| smoke (`test_validate_smoke.py`) | train(2A)→save→validate 端から端→`external_validation.json`/`calibration_external.png`/`external_table1.csv` 生成、戻り値に外部AUROC点・CI・slope／固定モデル適用（source_model記録・係数不変）を確認 |

検証ループ: `ruff → mypy src pipeline tests → pytest` 緑。再現性: validate を同seed2回で外部AUROC・CI完全一致。後方互換: 既存 run.py・全テスト不変。

## 6. 次段（このspecの外）

- UNDERSCORE/尿量単独の外部比較（H2）、AmsterdamUMCdb 検証
- DCA(C)、定義感度(D, 72h/14d)、MICE、本格 eICU 特徴量エンジニアリング
