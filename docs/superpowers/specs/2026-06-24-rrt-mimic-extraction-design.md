# Design: MIMIC-IV Extraction Layer (iteration 2, sub-project G)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Companion: [real-data-execution-runbook.md](../../../plan/real-data-execution-runbook.md)（§3 抽出スキーマ）
> Depends on: analysis pipeline (iteration 1 + 2A/E)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-24

---

## 0. 位置づけとスコープ

合成スケルトンの**上流に実データ抽出層を追加**する。MIMIC-IV の生テーブルから、解析パイプラインが消費する
§3スキーマの3CSV（`crrt_events` / `labs` / `flags`）を生成する純pandas変換層。これにより、ユーザーがローカルで
`pipeline.extract_mimic` → `pipeline.run` を繋げられる。

**重要な制約（明記）**: Claude は credentialed MIMIC に**アクセスできない**。検証は「**合成生テーブル（MIMICスキーマ模倣・実値なし）→ 期待する正準CSV**」の
TDD と スキーマ準拠まで。**実MIMICでの検証はユーザーがローカルで行う**。itemid/ICD/定義は config 既定＋「実MIMICで要確認」。

**Non-goals**: eICU抽出（次サブプロジェクト）、sepsis-3 の厳密導出、人工呼吸の詳細分類、尿量24h窓化、包含/除外コホート定義の自動化（stays は入力前提）、大規模IO最適化（読込はユーザー環境依存）。

## 1. 確定した設計判断（brainstorm 合意）

| 項目 | 決定 |
|---|---|
| スコープ | MIMIC-IV から 3出力（crrt_events/labs/flags）全部 |
| 実装媒体 | 純pandas変換関数（生テーブルDF→正準DF）＋合成生テーブルTDD。読込層は薄く分離 |
| 起動 | 専用 `pipeline/extract_mimic.py`（Hydra） |
| 定義 | itemid/ICD/merge_gap は config 既定＋要確認。臨床的厳密化は次段 |

## 2. アーキテクチャ

```
src/rrt_liberation/extract/
├── __init__.py            # build_mimic_crrt_events / build_mimic_labs / build_mimic_flags をexport
└── mimic.py               # 純pandas変換関数
pipeline/extract_mimic.py  # Hydra: 生テーブル読込→変換→data/mimic/*.csv 書出
conf/extract_mimic.yaml    # 生パス・itemid/ICD・merge_gap・出力先
tests/test_extract_mimic.py
```
- **変換（純pandas関数）と読込（実MIMICパス）を分離**：関数は生DF→正準DF＝合成生テーブルでTDD可能。`extract_mimic.py` が読込（既定 read_csv、DuckDB/parquetに差替可）＋書出。
- 出力は §3スキーマに正確一致 → 既存 `pipeline.run` 等がそのまま消費。
- 既存 `src/`・解析パイプライン・全テストは不変（extract は独立した上流層）。coding-style準拠（純関数・型ヒント・logger・`__all__`）。

## 3. 3変換関数の操作的定義

itemid/ICDは config 引数（既定はMIMIC-IV実値、要確認）。

### ① build_mimic_crrt_events(procedureevents, crrt_itemids, merge_gap_hours=6.0) -> DataFrame
- 入力 `procedureevents`: `subject_id, stay_id, itemid, starttime, endtime`。`crrt_itemids` 既定 [225802, 225803, 225805, 225809]。
- 処理: CRRT itemid 抽出 → stayごと starttime順 → **gap ≤ merge_gap_hours の隣接/重複区間を1セッションに結合** → 正準 `subject_id, stay_id, starttime, endtime, modality`（modality="CRRT"）。
- 出力 = §3 crrt_events。離脱境界判定は下流 `find_attempts`。merge_gap は離脱 min_off_hours(24h, 下流) とは別。

### ② build_mimic_labs(outputevents, labevents, stays, urine_itemids, creatinine_itemids) -> DataFrame
- 尿量: `outputevents`(`stay_id, itemid, value`) から urine_itemids（既定 [226559, 226560, 227510]）→ **正準 itemid 226559**、`valuenum=value`。
- Cr: `labevents`(`subject_id, itemid, valuenum, charttime`) から creatinine_itemids（既定 [50912]）→ `stays`(`subject_id, stay_id, intime, outtime`) で **charttime→stay_id 割当（在室期間内のみ）** → **正準 itemid 50912**。
- 出力 = §3 labs（`stay_id, itemid, valuenum`、urine+Cr 縦結合）。
- 注意（要確認）: 尿量は outputevents（labではない）、Cr は labevents。単位（mL / mg/dL）を §2係数と整合。

### ③ build_mimic_flags(stays, diagnoses_icd, inputevents, vent_events, septic_shock_icd, vasopressor_itemids, vent_itemids) -> DataFrame
- `stays` の各 stay_id を基準に3二値（該当なし→0）:
  - `sepsis_shock`: `diagnoses_icd` に septic_shock_icd（既定 ["R6521", "78552"]）→ 1。（sepsis-3導出は次段、まずICD）
  - `vasopressor`: `inputevents` に vasopressor_itemids（既定 [221906, 221289, 222315, 221662, 221749]）の投与 → 1。
  - `mechanical_ventilation`: `vent_events` に vent_itemids（既定 [225792, 225794]）→ 1。
- 出力 = §3 flags（`stay_id, sepsis_shock, vasopressor, mechanical_ventilation`、stayごと1行）。

### 横断ルール
- すべて **stays 基準**で出力（対象コホート外混入防止）。stays はユーザーの包含/除外を反映したICU stay一覧（入力前提）。
- 欠測: lab欠測→NaN（下流Preprocessorが代入）、flag欠測→0。
- itemid/ICD/定義は全て config 既定＋「実MIMICで要確認」。臨床的厳密化（sepsis-3, vent詳細, urine 24h窓化）は次段。

## 4. config・CLI配線

`conf/extract_mimic.yaml`:
```yaml
raw:
  procedureevents: ${paths.data_dir}/mimic_raw/procedureevents.csv
  outputevents:    ${paths.data_dir}/mimic_raw/outputevents.csv
  labevents:       ${paths.data_dir}/mimic_raw/labevents.csv
  diagnoses_icd:   ${paths.data_dir}/mimic_raw/diagnoses_icd.csv
  inputevents:     ${paths.data_dir}/mimic_raw/inputevents.csv
  ventilation:     ${paths.data_dir}/mimic_raw/ventilation.csv
  icustays:        ${paths.data_dir}/mimic_raw/icustays.csv
itemids:
  crrt:        [225802, 225803, 225805, 225809]
  urine:       [226559, 226560, 227510]
  creatinine:  [50912]
  vasopressor: [221906, 221289, 222315, 221662, 221749]
  ventilation: [225792, 225794]
codes:
  septic_shock_icd: ["R6521", "78552"]
merge_gap_hours: 6.0
paths:
  data_dir: data
  output_dir: ${paths.data_dir}/mimic
```
`pipeline/extract_mimic.py` の `main`: 各 raw を read_csv（日時列 datetime 化）→ 3変換関数 → `output_dir/{crrt_events,labs,flags}.csv`。
CLI: `uv run python -m pipeline.extract_mimic`（実行後 `pipeline.run model=logistic` が回る）。`mimic_raw/` も `data/` 配下＝gitignore。

## 5. テスト戦略

合成生テーブル（MIMICスキーマ模倣・実値なし）、`tests/test_extract_mimic.py`:
| 対象 | 検証 |
|---|---|
| crrt_events | CRRT itemid抽出／gap≤merge_gap 結合（断片2行→1区間, gap>閾値→2区間）／非CRRT除外／正準列・modality |
| labs | urine→226559・Cr→50912 統一／labevents charttime→stay_id 割当（在室内のみ）／正準列／urine+Cr 縦結合 |
| flags | septic_shock_icd→1・なし→0／vasopressor投与→1／vent→1／stayごと1行・該当なし0 |
| 横断 | stays基準（対象外混入なし）／欠測挙動 |
| 統合 | 合成生テーブル→3CSV→**既存 run_pipeline(model=logistic) に食わせて学習が回る**（抽出→解析の往復が繋がる） |

検証ループ: `ruff → mypy src pipeline tests → pytest` 緑。**実MIMIC検証は不可**（合成生テーブルでのロジック検証＋スキーマ準拠まで）。後方互換: 既存全テスト・他エントリ不変。

## 6. 次段（このspecの外）

- eICU 抽出（treatment/lab/diagnosis/infusiondrug → §3スキーマ）
- sepsis-3 厳密導出、人工呼吸詳細、尿量24h窓化、§7残り予測子、包含/除外コホート自動化、大規模IO最適化。
