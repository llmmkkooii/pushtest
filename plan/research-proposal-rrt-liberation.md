# Research Proposal: Prediction of Liberation and Kidney Recovery after Dialysis in Critically Ill Patients — IHD-focused, with CRRT Comparison

> Project: ICU 透析(IHD)離脱の予測モデル開発＋多施設外部検証、CRRTとのモダリティ比較、二重アウトカム
> Stage: research-ideation → RQ精緻化（PICO fixed, 2026-06-11 更新）
> Archetype: Uchino et al., Crit Care Med 2009;37(9):2576-82（BEST Kidney, CRRT離脱の元祖）
> Companion: [literature-review-rrt-liberation.md](literature-review-rrt-liberation.md) / [data-access-playbook.md](data-access-playbook.md)
> Last updated: 2026-06-11

---

## 1. Working Title

Prediction of successful liberation from intermittent haemodialysis and subsequent kidney
recovery in critically ill patients with acute kidney injury: development, multi-database
external validation, and comparison with continuous renal replacement therapy.

## 2. Background & Rationale

- **Uchino 2009（BEST Kidney, CRRT）** が「離脱前尿量が成功の最強予測因子（AUROC 0.808、利尿薬なしで0.845）」を定量化した原型。以降の DOnE RRT・UNDERSCORE・ML研究はすべてこの延長。
- しかし **離脱研究はほぼ CRRT 中心**で、**IHD（間欠的血液透析）に特化した離脱基準・予測は空白**。LIBERATE-D（JAMA 2026）が IHD の保存的戦略をホット化した今、IHD離脱の予測は時宜を得る。
- 加えて、既存研究は「短期離脱(weaning)」か「長期回復(recovery)」のどちらか一方に閉じており、**両者を同一コホートで橋渡しした研究は乏しい**（Liu 2021が示唆のみ）。
- 回復予測モデルも弱い（Lee 2019, c-index 0.64・外部検証なし）。

## 3. Research Questions（確定）

- **RQ1（主・IHD）**: 重症AKIで IHD を受け離脱を試みた成人ICU患者で、日常診療データに基づく
  予測モデルは、(a) 短期離脱成功、(b) 90日の腎回復（透析非依存）を、開発コホート(MIMIC-IV)と
  独立外部コホート(eICU-CRD ± AmsterdamUMCdb)で頑健に予測できるか。
- **RQ2（モダリティ比較）**: 離脱成功・回復の予測因子と予測性能は、IHD と CRRT で異なるか。
- **RQ3（定義ロバストネス）**: 性能・予測因子は離脱/回復の定義によりどう変わるか。

## 4. Hypotheses

- H1: IHD離脱予測モデルは外部コホートで臨床的に有用な識別能（AUROC ≥ 0.75）を維持する。
- H2: モデルは Uchino型（尿量単独）・UNDERSCORE・Lee 2019 を上回る、または同等で較正が優れる。
- H3: 主要予測因子は IHD と CRRT で部分的に異なる（特に IHD では離脱前尿量の重みが変わりうる）。
- H4: 短期離脱成功は 90日腎回復と関連する（Liu 2021を多施設で確認）。

## 5. Design & Data Sources

- 後ろ向きコホート、予測モデル開発＋外部検証（TRIPOD-AI / PROBAST 準拠）。
- **開発**: MIMIC-IV（RRTイベントを procedureevents/inputevents から再構成；IHD/CRRT を判別）
- **外部検証**: eICU-CRD（treatment/dialysis テーブル）、(可能なら) AmsterdamUMCdb
- **将来拡張**: STARRT-AKI（90日透析依存あり）等の共有RCTデータを回復アウトカムのRCT級外部検証に（data-access-playbook参照）
- credentialed data はローカルのみ・外部AIに渡さない（PHI境界）。

## 6. Population & Modality

- **主軸 = IHD**、**比較群 = CRRT**（SLEDは感度分析）
- 包含: 成人(≥18)、ICU、AKI、RRT施行、**離脱試行あり**
- 除外: 入院前から慢性透析/ESRD、RRT中の死亡、ICU滞在<24h、データ不備
- **IHD「離脱試行」の操作的定義（確定・本研究の肝）**:
  - **RRTエピソード** = 連続セッション群（セッション間ギャップ ≤ 閾値）。ICUのIHDは連日〜隔日が多く、
    **>72h の途絶は“スケジュール”でなく“中止意図”を反映**。
  - **離脱試行** = エピソード末尾（最後のセッション=中止の意思決定点）= **予測時点(landmark)**。
  - **予測因子の測定窓** = 離脱試行直前24h（Uchino 2009と整合: 離脱前24h尿量）。
  - **閾値 = 主要72h、感度分析 48/72/96h**。
  - **CRRT** = off 連続 ≥24h で1試行（既存パイプライン踏襲）→ モダリティ間で整合。
  - **immortal-time対策**: 予測時点を中止点に固定(landmark)、予測因子はそれ以前のみ。
    閾値条件付け(>閾値オフ=試行)の影響は閾値感度分析で評価。

## 7. Outcomes（二重アウトカム）

- **短期（Uchino型・co-primary）**: 離脱試行後 **7日間 RRT 再開なし**
  - 感度分析: 72時間／14日
- **長期（回復・co-primary）**: **90日の透析非依存（生存かつRRT非依存）= 腎回復**
  - 感度分析: 退院時透析非依存（LIBERATE-D型）／1年
- 競合リスク（死亡）の扱いを明記（死亡=失敗 と 競合リスク解析 の双方）

## 8. Comparators（ベンチマーク）

1. **Uchino型 尿量単独**（離脱前24h尿量、AUROC基準 0.808 を再現・比較）
2. **UNDERSCORE**（多変量weaningスコア）
3. **Lee 2019**（90日回復予測、c-index 0.64）
4. 開発モデル（解釈可能ロジスティック ＋ RF/XGBoost 参照）

## 9. Candidate Predictors（離脱試行時点で得られる日常変数）

- 腎: 尿量（離脱前24h・直近）、Cr、BUN、尿中Cr（取得可能なら）
- 全身: 非腎SOFA、昇圧薬、侵襲的人工呼吸、乳酸
- 代謝/体液: HCO₃、累積/直近水分バランス、体重変化
- 治療背景: RRT継続期間、入院時敗血症性ショック、基礎Cr（推定）、**モダリティ(IHD/CRRT)**
- 回復用追加: 基礎eGFR、入院前Hb、肝疾患・心不全・CKD（Lee 2019因子）

## 10. Statistical / Modeling Plan

- モデル: 解釈可能ロジスティック回帰を主、RF/XGBoost を参照
- 評価: **識別能(AUROC/AUPRC)＋較正(calibration)＋臨床的有用性(decision curve)**
- 外部検証: 各DBで再学習せず固定モデルを適用（true external validation）
- モダリティ比較: IHD/CRRT別にモデル係数・性能を提示、交互作用検定
- 二重アウトカム: 短期離脱→90日回復の連関（H4）も解析
- 欠測: 多重代入（MICE）、感度分析
- 報告: TRIPOD-AI、バイアス評価 PROBAST、再現性: seed固定・uv/Hydra・抽出コード公開

## 11. Novelty Pillars

1. **IHD特化の離脱予測**（Uchino 2009のIHD版が存在しない空白）＋ **CRRTとのモダリティ比較**
2. **短期離脱と90日腎回復を同一コホートで橋渡し**（二重アウトカム）
3. **eICU(多施設)での初の外部検証** ＋ **離脱/回復定義のロバストネス解析**
4. **較正＋decision curve** まで提示、Uchino/UNDERSCORE/Lee 2019 を直接ベンチマーク

## 12. Anticipated Limitations

- 後ろ向き・適応交絡（誰が・なぜ離脱を試みたか）
- **IHD「離脱試行」定義の難しさ**（間欠性ゆえ）→ 操作的定義の感度分析で対応
- DB間の RRTモダリティ記録粒度の差（特に eICU の IHD/CRRT 判別）
- 90日回復は MIMIC/eICU では退院後追跡が限定的 → 退院時透析非依存を主に、90日はRCTデータで補完
- 日本人コホートを含められない（JIPAD・自施設EHRに離脱情報なし）

## 13. Milestones / Next Steps

1. [ ] 「離脱試行・再開」操作的定義の確定（IHD: ≥X日, CRRT: ≥Y時間）と各DB抽出ロジック
2. [ ] MIMIC-IV で IHD/CRRT 判別 → コホート抽出 → ベースライン記述（TRIPODフロー）
3. [ ] Uchino型(尿量)・UNDERSCORE・Lee 2019 を再現 → ベンチマーク → 開発モデル
4. [ ] 外部検証（eICU ± Amsterdam）→ モダリティ比較 → 定義感度分析 → DCA/較正
5. [ ] 短期離脱→90日回復の連関解析（H4）
6. [ ] 回復アウトカムのRCT級外部検証に向け STARRT-AKI 等へコンセプト提案
7. 投稿先候補: Critical Care / Critical Care Medicine（Uchino 2009と同誌系）。回復・因果寄りなら ICM

## 14. 既存パイプラインとの関係

`tools/rrt-liberation/` の解析パイプラインは現状 **CRRT・7日離脱** で実装済み（合成スケルトン＋
MIMIC/eICU抽出層）。本改訂で **(a) IHDモダリティの追加・判別、(b) 90日回復アウトカム、
(c) Uchino尿量・Lee 2019ベンチマーク** を拡張対象に加える。既存のCRRT・7日離脱は「CRRT比較群・
短期アウトカム」として本設計に内包される（破棄しない）。
