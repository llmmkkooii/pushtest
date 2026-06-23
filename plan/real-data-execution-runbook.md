# Real-Data Execution Runbook: RRT Liberation Pipeline

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Companion: [research-proposal-rrt-liberation.md](research-proposal-rrt-liberation.md) /
> [data-access-playbook.md](data-access-playbook.md) /
> pipeline: `tools/rrt-liberation/`（specs/plans は `docs/superpowers/`）
> Last updated: 2026-06-23

合成データで骨格化済みのパイプラインを **実データ（MIMIC-IV / eICU-CRD）** で動かすための手順書。
**これはあなた（PI/解析者）のオフライン作業**。Claudeはコードを書くが、credentialed data には触れない。

---

## 0. 絶対ルール（PHI境界）

- credentialed data（MIMIC-IV / eICU-CRD の患者レベル値）は **`tools/rrt-liberation/data/` 配下のみ**に置く（`.gitignore` 済み）。
- **実データ・実値・credentialed CSV を Claude や外部AI（NotebookLM/Gemini/Perplexity 等）に貼らない・渡さない**。
- Claude と共有してよいのは **集計済み非PHI出力のみ**（AUROC・較正係数・net benefit 等、`outputs/` の数値）。
- `outputs/` も `.gitignore` 済み。実データ由来の中間生成物をコミットしない。
- 解析は全てローカルで `uv run` 実行。

---

## 1. 事前チェックリスト

- [ ] PhysioNet credentialed access（CITI "Data or Specimens Only Research" → DUA）：**MIMIC-IV / eICU 取得済み**（data-access-playbook §1）。
- [ ] 京大 **シニアPI** を共同申請者/責任者に確保。
- [ ] 京大IRB 該当性確認（脱識別公開DBの二次利用）。
- [ ] uv 環境構築：`cd tools/rrt-liberation && uv sync`。
- [ ] `uv run pytest -q` が緑（合成データ上での健全性確認）。

---

## 2. UNDERSCORE 係数の転記（実データ前に必須）

`tools/rrt-liberation/conf/model/underscore.yaml` の係数は **プレースホルダ0**。実行前に
**Chaïbi et al., 2026 (Intensive Care Medicine)** から6変数＋切片の係数を転記する。

```yaml
# conf/model/underscore.yaml
coefficients:
  intercept: <原著の切片>
  urine_output_24h: <β>
  baseline_creatinine: <β>
  crrt_duration_hours: <β>
  sepsis_shock: <β>
  vasopressor: <β>
  mechanical_ventilation: <β>
```

- 単位・変数定義（尿量の単位、Crの単位、CRRT期間の時間/日）を原著と**一致**させること。パイプラインの特徴量単位（§4）と整合しないと係数が無意味になる。
- 転記後は `citation-verification` で原著との突合を推奨。係数はコードにハードコードせず config のみ。
- `benchmark.yaml` の `underscore_coefficients` も同じ値に更新（H2比較で使用）。

---

## 3. 実データ抽出 → CSV レイアウト（パイプラインが期待する正確なスキーマ）

実 SQL 抽出スクリプトは**未実装（次サブプロジェクト）**。下表のスキーマで CSV を生成し配置する。
**離脱試行・再開の操作的定義はコード側（`liberation/rules.py`）が担う**ので、抽出は「CRRT稼働区間」と「lab/flags」を素直に出すだけでよい。

### 3.1 MIMIC-IV（`data/mimic/`）

| ファイル | 必須列 | 内容 |
|---|---|---|
| `crrt_events.csv` | `subject_id, stay_id, starttime, endtime, modality` | **正準イベント**。CRRT稼働の各区間（開始/終了は ISO 日時）。procedureevents/inputevents・派生 crrt 概念から再構成 |
| `labs.csv` | `stay_id, itemid, valuenum` | **itemid 226559=尿量**、**itemid 50912=creatinine**（最低この2項目）。stay内の複数測定を行で持つ |
| `flags.csv` | `stay_id, sepsis_shock, vasopressor, mechanical_ventilation` | stayごと1行、各 0/1。診断/昇圧薬/人工呼吸の有無 |

### 3.2 eICU-CRD（`data/eicu/`）

| ファイル | 必須列 | 内容 |
|---|---|---|
| `crrt_events.csv` | `patientunitstayid, treatmentoffset, treatmentstopoffset, treatmentstring` | **eICU形**（分オフセット）。`EicuCohortBuilder` が正準化。treatment テーブルから CRRT を `treatmentstring` で**フィルタしてから**出す（現コードは定数 modality を当てるだけなので、CRRT以外を除外しておくこと） |
| `labs.csv` | `stay_id, itemid, valuenum` | **正準labsスキーマ**（`stay_id = patientunitstayid`、itemid 226559/50912 相当に**マッピング済み**）。eICUの lab テーブルから尿量・Crを抽出し itemid を付与 |
| `flags.csv` | `stay_id, sepsis_shock, vasopressor, mechanical_ventilation` | stayごと1行 0/1 |

> 注: eICU の labs/flags は「正準スキーマに整える」のがあなたの抽出側の責任（現状コードはスキーマ非依存の正準化までしか持たない）。

---

## 4. 特徴量の近似（実データ反映時の注意）

現スケルトンの特徴量定義は近似が入っている。実データでは下記を意識（必要なら抽出/コードを精緻化）。

| 特徴量 | 現定義 | 実データでの注意 |
|---|---|---|
| `urine_output_24h` | **stay平均**（24h窓化されていない） | 本来は離脱試行**直前24h**の尿量。抽出で時間窓集計するか、コード側で per-attempt 窓化（次段） |
| `baseline_creatinine` | stay**最小**Cr（保存的代理） | 真の入院前Crが無い後ろ向き設計の標準近似。妥当性を方法に明記 |
| `crrt_duration_hours` | 試行時点までの稼働総時間（**per-attempt 打切り済**＝正しい） | そのまま実データで妥当 |
| `sepsis_shock`/`vasopressor`/`mechanical_ventilation` | flags表の二値（記録なし→0） | 実 diagnosis/medication/ventilation テーブルからの導出が必要。0=非該当の運用を明記 |

---

## 5. 実行シーケンス（実データ、ローカル `uv run`）

`paths.data_dir=data` 既定。係数転記（§2）と CSV 配置（§3）の後に実行。

```bash
cd tools/rrt-liberation

# 1) 開発モデル学習（MIMIC, 6変数）→ outputs/model_logistic.json ほか
uv run python -m pipeline.run model=logistic

# 2) 尿量単独モデル（H2用、別ディレクトリに保存して退避）
uv run python -m pipeline.run model=logistic 'features.predictors=[urine_output_24h]' paths.output_dir=outputs_urine
cp outputs_urine/model_logistic.json outputs/urine_model_logistic.json && rm -rf outputs_urine

# 3) eICU 外部検証（固定モデルを再学習せず適用）
uv run python -m pipeline.validate fixed_model_path=outputs/model_logistic.json cohort=eicu

# 4) 定義感度分析（72h/7d/14d, H3）
uv run python -m pipeline.sensitivity cohort=mimic

# 5) ベンチマーク比較（dev / urine / UNDERSCORE, H2）＋外部DCA
uv run python -m pipeline.benchmark cohort=eicu
```

**出力（`outputs/`、非PHI集計のみ）**: model_logistic.json, model_performance.json, coefficients.csv,
calibration.png, dca.png, dca.csv, external_validation.json, calibration_external.png, external_table1.csv,
definition_sensitivity.csv/.json, benchmark_comparison.csv, dca_external.csv/.png。
→ これら集計結果は Claude と共有して解釈・図表・原稿に使ってよい。

---

## 6. 再現性

- 乱数 seed は各エントリ既定 42（`seed=` で上書き可）。同seedで bootstrap・係数・AUROC は完全一致。
- Hydra が各実行の解決済み config を `outputs/<date>/<time>/.hydra/` に自動保存。
- `uv lock`／`pyproject.toml` で依存固定。実行環境（python/uv/sklearn 版）を記録。
- 抽出SQL・コホート定義・コードは TRIPOD-AI 再現性のため公開（実データは公開不可、コードと定義は公開）。

---

## 7. 報告（投稿時）

- **TRIPOD-AI**（予測モデル開発＋外部検証）、バイアス評価は **PROBAST**。
- 主要図表：STROBE/TRIPODフロー（flow.txt → 整形）、Table 1（external_table1.csv 等）、
  較正プロット、decision curve、benchmark 比較表（H2）、定義感度表（H3）。
- 投稿先候補：Critical Care / Critical Care Medicine（因果寄りに発展すれば ICM）。

---

## 8. 残タスク（スケルトン→実研究の差分）

- [ ] 実 MIMIC/eICU **SQL抽出スクリプト**（§3スキーマを出す、別サブプロジェクト）
- [ ] eICU の labs/flags **正準マッピング**＋ events の `treatmentstring` CRRTフィルタ
- [ ] 尿量の **24h窓化**、§7 残り予測子（BUN/乳酸/HCO₃/水分バランス/非腎SOFA）
- [ ] **MICE**（多重代入）、RF/XGBoost 参照モデル、退院時透析非依存定義、AmsterdamUMCdb 検証
- [ ] UNDERSCORE 係数転記（§2）＋ citation-verification

> 合成スケルトンは proposal の全仮説（H1=2B/H2/H3=D）・全新規性（①定義/②eICU外部/③較正+DCA）を網羅済み。
> 実データ価値はここから（§3抽出と§2係数が最初のゲート）。
