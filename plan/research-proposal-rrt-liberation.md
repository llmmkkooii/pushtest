# Research Proposal: Multi-Database External Validation of a CRRT Liberation Prediction Model

> Project: ICU における CRRT 離脱（liberation）予測モデルの多施設外部検証＋定義ロバストネス解析
> Stage: research-ideation → research question 確定（PICO fixed）
> Companion: [literature-review-rrt-liberation.md](literature-review-rrt-liberation.md)
> Last updated: 2026-06-11

---

## 1. Working Title

Development and multi-database external validation of a prediction model for successful
liberation from continuous renal replacement therapy (CRRT) in critically ill patients
with acute kidney injury: a robustness analysis across liberation definitions.

## 2. Background & Gap（詳細は文献レビュー参照）

- CRRT 離脱の最適タイミングに合意なし。離脱前**尿量**が最頑健な単一指標だが閾値・定義が非標準化（DOnE RRT 2020; Delphi 2025）。
- 多変量スコア **UNDERSCORE**（Chaïbi 2026, Intensive Care Med）が唯一の外部検証済み（導出AUC 0.86→外部0.73）。
- ML研究（Popoff 2025; Sheng 2024; Zhong 2024 等）は RF/XGBoost が最良で収束。しかし:
  - **eICU-CRD（米・多施設）を外部検証に使った研究が存在しない**（空白②）
  - 「離脱成功」の**定義が72h〜14日でバラバラ**で比較不能（空白①）
  - 較正(calibration)・decision curve を揃えた実装志向研究が乏しい

## 3. Research Question（確定）

重症AKIでCRRTを受け離脱を試みた成人ICU患者において、日常診療データに基づく離脱成功
予測モデルは、開発コホート(MIMIC-IV)と独立した複数の外部コホート(eICU-CRD,
AmsterdamUMCdb)で頑健に機能するか。また、その性能と予測因子は離脱の定義によって
どう変わるか。

## 4. Hypotheses

- H1: 日常データのみで構築した離脱予測モデルは、外部コホートでも臨床的に有用な識別能
  （AUROC ≥ 0.75）を維持する。
- H2: モデルは UNDERSCORE および尿量単独を上回る、または同等で較正が優れる。
- H3: 予測性能・主要予測因子は離脱定義（72h/7日/14日/退院時透析非依存）により系統的に
  変化し、その差は定量化・可視化できる。

## 5. Design & Data Sources

- 後ろ向きコホート、予測モデル開発＋外部検証（TRIPOD-AI / PROBAST 準拠）。
- **開発**: MIMIC-IV（RRTイベントは procedureevents/inputevents・派生 crrt 概念から再構成）
- **外部検証**: eICU-CRD（treatment/dialysis テーブル）、AmsterdamUMCdb（CRRT記録）
- 各DBは PhysioNet 等の DUA + CITI training 取得後にローカル解析（外部AIサービスへ投入しない）

## 6. Population

- **対象RRT**: CRRT 中心（IHD/SLED は感度分析）
- 包含: 成人(≥18)、ICU、AKI、CRRT施行、**離脱試行あり**（CRRT停止が一定時間継続）
- 除外: 入院前から慢性透析/ESRD、CRRT中の死亡、ICU滞在<24h、データ不備
- 「離脱試行」の運用定義（要詰め）: CRRT停止が連続 ≥ X 時間（例 ≥24h）継続したエピソード

## 7. Candidate Predictors（離脱試行時点で得られる日常変数）

- 腎: 尿量（離脱前 24h・直近）、Cr、BUN、尿中Cr（取得可能なら）
- 全身: 非腎SOFA、昇圧薬使用、侵襲的人工呼吸、乳酸
- 代謝/体液: HCO₃、累積/直近水分バランス、体重変化
- 治療背景: CRRT継続期間、入院時敗血症性ショック、基礎Cr（推定）
- ※ UNDERSCORE 6項目（CRRT期間・敗血症性ショック・基礎Cr・昇圧薬・人工呼吸・尿量）を内包

## 8. Outcome

- **主要定義**: 離脱試行後 **7日間 RRT 再開なし**（UNDERSCORE/文献整合、ベンチマーク比較が素直）
- **感度分析定義**:
  - 72時間 RRT 再開なし
  - 14日透析非依存 ＋ 生存（LIBERATE-D 型）
  - 退院時 透析非依存 ＋ 生存
- 競合リスク（死亡）の扱いを明記（死亡を失敗に含める／競合リスク解析の双方を提示）

## 9. Comparators（ベンチマーク）

1. **UNDERSCORE スコア**（外部スコアの直接再現）
2. **尿量単独**（最頑健な単一指標）
3. 開発モデル（解釈可能ロジスティック＋ RF/XGBoost ベンチマーク）

## 10. Statistical / Modeling Plan

- 特徴量: 事前指定＋臨床的妥当性で選択（データ駆動選択は感度分析）
- モデル: 解釈可能なロジスティック回帰を主、RF/XGBoost を性能上限の参照に
- 評価: **識別能(AUROC/AUPRC)＋較正(calibration plot, slope/intercept)＋臨床的有用性(decision curve)**
- 外部検証: 各DBで再学習せず固定モデルを適用（true external validation）
- 欠測: 多重代入（パターン報告）、感度分析
- 報告: TRIPOD-AI、バイアス評価は PROBAST
- 再現性: seed固定、Hydra/uv で設定管理、コホート抽出SQL/コードを公開

## 11. Novelty Pillars

1. eICU(多施設)＋Amsterdam(欧州)での**初の多施設・多大陸外部検証**（空白②）
2. **離脱定義のロバストネス解析**（空白①＝標準化問題に正面から）
3. **較正＋decision curve**まで提示（既存MLの欠落を補完）＋ UNDERSCORE 直接比較

## 12. Anticipated Limitations

- 後ろ向き・適応交絡（誰が・なぜ離脱を試みたか）
- DB間の CRRT 記録粒度の差（特に eICU）
- 「離脱試行」「再開」の操作的定義への依存
- 日本人/アジアコホートを含められない（JIPAD・自施設EHRに離脱情報なしのため）

## 13. Milestones / Next Steps

1. [ ] PhysioNet DUA + CITI（MIMIC-IV / eICU）、AmsterdamUMCdb アクセス申請
2. [ ] 「離脱試行・再開」操作的定義の確定（≥X時間）と各DBでの抽出ロジック設計
3. [ ] コホート抽出（MIMIC-IV）→ ベースライン記述（STROBE/TRIPOD フロー）
4. [ ] UNDERSCORE 再現 → ベンチマーク → 開発モデル
5. [ ] 外部検証（eICU, Amsterdam）→ 定義感度分析 → DCA/較正
6. [ ] 投稿先候補: Critical Care / Critical Care Medicine（定番）。設計が因果寄りに発展すれば ICM
