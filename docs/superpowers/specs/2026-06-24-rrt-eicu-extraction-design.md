# Design: eICU-CRD Extraction Layer (iteration 2, sub-project H)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Companion: [real-data-execution-runbook.md](../../../plan/real-data-execution-runbook.md)
> Parallel to: [MIMIC extraction](2026-06-24-rrt-mimic-extraction-design.md) / [eICU external validation](2026-06-22-rrt-eicu-external-validation-design.md)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-24

---

## 0. 位置づけとスコープ

MIMIC抽出（sub-project G）と**並行**の、eICU-CRD 生テーブル→正準入力CSV変換層。eICU から
`crrt_events`（eICU形）/ `labs`（正準）/ `flags`（正準）を生成し、ユーザーが
`pipeline.extract_eicu` → `pipeline.validate cohort=eicu` を繋げられるようにする。純pandas変換＋合成生テーブルTDD。

**重要な制約（明記）**: Claude は credentialed eICU に**アクセスできない**。検証は「合成生eICUテーブル（eICUスキーマ模倣・実値なし）→
期待する出力CSV」のTDD＋スキーマ準拠まで。**実eICU検証はユーザーがローカルで行う**。用語リスト・CRRT stop offset 導出は config 既定＋「実eICUで要確認」。

**Non-goals**: sepsis-3 厳密導出、人工呼吸の詳細分類、尿量24h窓化、包含/除外コホート自動化、CRRT timing の上流導出（stop offset 前提）、大規模IO最適化、AmsterdamUMCdb。

## 1. 確定した設計判断（brainstorm 合意）

| 項目 | 決定 |
|---|---|
| スコープ | eICU から 3出力（crrt_events/labs/flags）全部 |
| labs/flags 導出 | **eICU忠実な文字列マッチ**（labname/drugname/diagnosisstring/celllabel を contains・lower） |
| crrt_events 出力形 | **eICU形（分オフセット）**を維持（EicuCohortBuilder が offset→timestamp 変換） |
| 起動 | 専用 `pipeline/extract_eicu.py`（Hydra） |
| 定義 | 用語リスト・merge_gap は config 既定＋要確認。CRRT stop offset は前提（上流導出は次段） |

## 2. アーキテクチャ

```
src/rrt_liberation/extract/
├── eicu.py                # 純pandas: build_eicu_crrt_events / build_eicu_labs / build_eicu_flags
└── __init__.py            # eICU 3関数を export 追加（既存 mimic 3関数はそのまま）
pipeline/extract_eicu.py   # Hydra: 生eICUテーブル読込→変換→data/eicu/*.csv 書出
conf/extract_eicu.yaml     # 生パス・用語リスト(contains)・merge_gap・出力先
tests/test_extract_eicu.py
```
- 変換（純pandas）と読込（実eICUパス）を分離。既存 `extract/mimic.py`・解析・全テストは不変（並行追加）。
- 出力は §3/B のスキーマに正確一致 → `pipeline.validate cohort=eicu` 等がそのまま消費。coding-style準拠。

## 3. 3変換の操作的定義

用語リストは config 引数（contains・lower マッチ）。

### ① build_eicu_crrt_events(treatment, crrt_terms, merge_gap_minutes=360.0) -> DataFrame（eICU形）
- 入力 `treatment`: `patientunitstayid, treatmentoffset, treatmentstopoffset, treatmentstring`。crrt_terms 既定 ["cvvh","cvvhd","cvvhdf","crrt","continuous renal replacement","scuf"]。
- 処理: treatmentstring が crrt_terms のいずれかを contains(lower) → 抽出 → patientunitstayid ごと treatmentoffset 順 → **gap ≤ merge_gap_minutes の隣接/重複区間を結合**（分単位、結合後 min start / max stop）→ eICU形のまま出力（`patientunitstayid, treatmentoffset, treatmentstopoffset, treatmentstring="CRRT"`）。
- 出力 = §3 eICU events（`EicuCohortBuilder` が offset→timestamp 変換）。
- **stop offset 前提**: 実eICU treatment に treatmentstopoffset が無い場合は上流導出が必要（要確認）。本関数は両offset列を前提。

### ② build_eicu_labs(lab, intakeoutput, creatinine_terms, urine_terms) -> DataFrame（正準）
- creatinine: `lab`(`patientunitstayid, labname, labresult`) で labname contains creatinine_terms（既定 ["creatinine"]）→ **正準 itemid 50912**、`valuenum=labresult`、`stay_id=patientunitstayid`。
- 尿量: `intakeoutput`(`patientunitstayid, celllabel, cellvaluenumeric`) で celllabel contains urine_terms（既定 ["urine","foley","void"]）→ **正準 itemid 226559**、`valuenum=cellvaluenumeric`、`stay_id=patientunitstayid`。
- 出力 = §3 labs（`stay_id, itemid, valuenum`、creatinine+urine 縦結合）。

### ③ build_eicu_flags(stays, diagnosis, infusiondrug, respiratorycare, septic_shock_terms, vasopressor_terms, vent_terms) -> DataFrame（正準）
- `stays`(`patientunitstayid`) 基準。stay_id=patientunitstayid。該当なし→0。
  - sepsis_shock: `diagnosis`(`patientunitstayid, diagnosisstring`) が septic_shock_terms（既定 ["septic shock"]）contains → 1。
  - vasopressor: `infusiondrug`(`patientunitstayid, drugname`) が vasopressor_terms（既定 ["norepinephrine","epinephrine","vasopressin","dopamine","phenylephrine"]）contains → 1。
  - mechanical_ventilation: `respiratorycare`(`patientunitstayid`) に該当行（vent_terms に当たる文字列列があれば contains、無ければ行存在）→ 1。本スケルトンは respiratorycare に行があれば 1（vent_terms は将来の文字列列フィルタ用）。
- 出力 = §3 flags（`stay_id, sepsis_shock, vasopressor, mechanical_ventilation`、stayごと1行）。

### 横断ルール
- 全て **stays 基準**で出力（対象外混入防止）。stay_id = patientunitstayid。
- 欠測: lab欠測→NaN（下流Preprocessor代入）、flag欠測→0。
- 文字列マッチは **lower + contains**（config 用語リスト）。用語リスト・CRRT stop導出は「実eICUで要確認」。

## 4. config・CLI配線

`conf/extract_eicu.yaml`:
```yaml
raw:
  treatment:       ${paths.data_dir}/eicu_raw/treatment.csv
  lab:             ${paths.data_dir}/eicu_raw/lab.csv
  intakeoutput:    ${paths.data_dir}/eicu_raw/intakeOutput.csv
  diagnosis:       ${paths.data_dir}/eicu_raw/diagnosis.csv
  infusiondrug:    ${paths.data_dir}/eicu_raw/infusionDrug.csv
  respiratorycare: ${paths.data_dir}/eicu_raw/respiratoryCare.csv
  patient:         ${paths.data_dir}/eicu_raw/patient.csv
terms:
  crrt:         ["cvvh", "cvvhd", "cvvhdf", "crrt", "continuous renal replacement", "scuf"]
  creatinine:   ["creatinine"]
  urine:        ["urine", "foley", "void"]
  septic_shock: ["septic shock"]
  vasopressor:  ["norepinephrine", "epinephrine", "vasopressin", "dopamine", "phenylephrine"]
  ventilation:  ["ventilator", "mechanical vent", "intubat"]
merge_gap_minutes: 360.0
paths:
  data_dir: data
  output_dir: ${paths.data_dir}/eicu
```
`pipeline/extract_eicu.py` の `main`: 各 raw を read_csv（patient=stays）→ 3変換 → `output_dir/{crrt_events,labs,flags}.csv`。
CLI: `uv run python -m pipeline.extract_eicu`（実行後 `pipeline.validate fixed_model_path=... cohort=eicu` が回る）。`eicu_raw/` も `data/` 配下＝gitignore。

## 5. テスト戦略

合成生eICUテーブル（eICUスキーマ模倣・実値なし）、`tests/test_extract_eicu.py`:
| 対象 | 検証 |
|---|---|
| crrt_events | crrt_terms contains 抽出（lower一致）／非CRRT除外／gap≤merge_gap(分) 結合（断片2→1, gap>閾値→2）／eICU形列維持・patientunitstayidごと |
| labs | lab labname→50912・intakeoutput celllabel→226559／valuenum 取得／正準列／creatinine+urine 縦結合／stay_id=patientunitstayid |
| flags | diagnosis "septic shock"→1・なし→0／infusiondrug drugname→1／respiratorycare 行あり→1／stayごと1行・該当なし0 |
| 横断 | stays基準（対象外混入なし）／lower+contains の大小無視 |
| 統合 | 合成生eICU→3CSV→**eICU形events を `CohortFactory("eicu").build` → `build_features(cohort, {labs,events,flags}, 6予測子)` が6列生成**（抽出→eICU解析の往復が繋がる） |

検証ループ: `ruff → mypy src pipeline tests → pytest` 緑。**実eICU検証は不可**（合成生テーブルのロジック＋スキーマ準拠まで、用語/CRRT stop は要確認）。後方互換: 既存全テスト・他エントリ不変。

## 6. 次段（このspecの外）

- CRRT timing の上流導出（treatment 点イベント→on区間）、sepsis-3 厳密導出、人工呼吸詳細、尿量24h窓化、§7残り予測子、包含/除外コホート自動化、AmsterdamUMCdb 抽出。
