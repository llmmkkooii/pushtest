# Literature Review: Liberation from Renal Replacement Therapy in Critical Care

> Project: ICU における腎代替療法(RRT/KRT)からの離脱(liberation/weaning/discontinuation)
> Databases of interest: MIMIC-IV, eICU-CRD (+ candidate: AmsterdamUMCdb, SICdb)
> Status: 文献レビュー先行フェーズ（research-ideation）
> Last updated: 2026-06-11

---

## 1. Scope & Question

- **対象集団**: 重症AKIで RRT を要した成人ICU患者
- **関心アウトカム**: RRT からの「離脱成功」（一定期間 RRT を再要しない／生存）
- **目的**: 既存研究の到達点とギャップを特定し、MIMIC/eICU を用いた研究の差別化軸を決める

---

## 2. Research Maturity Map（成熟度）

研究の系譜は4世代に整理できる。

| 世代 | 時期 | 中心テーマ | 到達点 |
|---|---|---|---|
| ① 単一予測因子 | 〜2020 | 尿量・尿中Cr・利尿薬反応 | 尿量が最頑健（ただし閾値非標準化） |
| ② バイオマーカー | 2020〜 | penKid/PENK, uNGAL, cystatin C | 尿量に上乗せ価値はあるが単独では凌駕せず |
| ③ 多変量臨床スコア | 2024〜 | UNDERSCORE | 初の外的検証スコア |
| ④ 機械学習＋公開DB | 2024〜 | MIMIC-IV ベース ML | 急速に飽和、定義バラバラ・外的検証不足 |

そして 2026 に **離脱を主要評価項目にした初の RCT（LIBERATE-D）** が登場。

---

## 2.5 平易版マスター表（Journal付き・臨床医向け）

> 精度の読み方: AUROC 0.7=まあまあ / 0.8=良い / 0.9=非常に良い（0.5=コイン投げ）

| 分類 | 論文 (年) | Journal | 何をした研究か | ひとことで言うと | 強さ |
|---|---|---|---|---|---|
| 総説/メタ解析 | Katulka 2020 (DOnE RRT) | Critical Care | 23研究をまとめた | 「尿量が一番の手がかり。でも閾値も定義もバラバラ」 | ★★★ |
| | Klouche 2024 | J Clin Med | 総説 | 「尿量 >500mL/日で離脱を考えよ」 | ★★ |
| | Xu 2025 | Critical Care | バイオマーカー16研究のメタ解析 | 「尿中NGALが比較的安定(0.80)。でも未確立」 | ★★★ |
| | Raina/Kashani 2025 (Delphi) | Critical Care | 専門家の合意形成 | 「標準化された定義もモデルも無い。尿量>400mL/日・2時間Crクリアランス>23が目安」 | ★★★ |
| 単一指標 | Viallet 2016 | Ann Intensive Care | 54人で検証 | 「24時間尿中クレアチニン ≥5.2mmol/日で84%成功(0.86)」 | ★★ |
| | Jeon 2018 | Critical Care | 1176人 | 「離脱前日の尿量＋利尿薬が成功を予測」 | ★★ |
| バイオマーカー | von Groote 2022 | Critical Care | ELAIN試験の再解析 | 「血中penKidが低いと早く離脱できる」 | ★★ |
| | von Groote 2023 | Critical Care | 多施設で再検証 | 「penKidは有効だが尿量に負ける」 | ★★ |
| | Tichy 2024 | Int J Mol Sci | 心臓外科後20人 | 「PENK 126.7で離脱予測(0.80)」 | ★ |
| 臨床スコア | Chaïbi 2026 (UNDERSCORE/DOORS) | Intensive Care Medicine | RCT2本の再解析＋外部検証 | 「6項目スコアで離脱を予測。唯一の外部検証済み」 | ★★★ |
| 機械学習 | Popoff 2025 | Scientific Reports | 仏＋MIMIC | 「日常データだけで予測可、他国でも一応通用(0.72)」 | ★★★ |
| | Liang 2024 | Renal Failure | 単施設976人 | 「FST(利尿薬負荷試験)陽性＋尿量が有効、RF/XGBで高精度」 | ★★ |
| | Sheng 2024 | BMC Nephrology | MIMIC 599人 | 「尿量・SOFA・HCO₃・血圧・BUNが効く要因」 | ★ |
| | Zhong 2024 | iScience | MIMIC＋中国 | 「XGBoostでオンライン計算機化」 | ★★ |
| | Kashani 2024 (抄録) | JASN (抄録) | — | 「ML離脱モデル(詳細未公開)」 | ★ |
| 介入試験 | Liu 2026 (LIBERATE-D) | JAMA | 221人RCT | 「透析を控えめにすると腎回復が早まる(ただし要追試)」 | ★★★ |
| | Ice/Shawwa 2026 | J Crit Care | パイロット67人 | 「標準化フォームだけでは成功率は上がらない」 | ★★ |
| 小児 | Stenson 2024 (WE-ROCK) | Intensive Care Medicine | 32施設622人 | 「小児でも尿量・短いCRRT期間が成功と関連」 | ★★ |

### Journalから読み取れる構図
- トップ誌（JAMA, Intensive Care Medicine, Critical Care）が複数を占める＝集中治療の主要誌が注目するホットトピック。
- 介入・スコア研究は一流誌、ML予測研究は中堅〜専門誌に偏在。→ 単なるML予測モデルは載る雑誌のtierが下がりがち。因果(LIBERATE-D型)や外部検証付きスコアの方が高インパクト誌に届きやすい。
- Critical Care がこの離脱テーマの定番投稿先（6本）。最初の1本の現実的な投稿先候補。

---

## 3. Key Evidence by Theme

### 3.1 系統的レビュー / メタ解析（土台）

- **DOnE RRT** (Katulka et al., 2020, Critical Care): 23観察研究・16変数をレビュー。尿量が最頑健（感度66%/特異度74%）だが**閾値不一致で最適cut-off決定不能・外的検証ゼロ**と明示。
  https://consensus.app/papers/details/4b923d1e2c2f5cb1a39d7e9ab6b0f273/
- **Klouche et al., 2024** (J Clin Med): 離脱前尿量が最重要。diuresis >500 mL/day で離脱を検討。尿パラメータは要検証。
  https://consensus.app/papers/details/b2a85f4b57dc504e8b43e56cd4644ea0/
- **Xu et al., 2025** (Critical Care): バイオマーカーSR/MA、16研究3020例。uNGAL が最安定（AUC 0.80）。定義標準化と動的指標の統合を提言。
  https://consensus.app/papers/details/b254248a66885fd6a73379c1a5b61272/
- **Raina, Kashani et al., 2025** (Crit Care): CRRT離脱の**Delphiコンセンサス**。18研究。成人で **2時間Cr clearance >23 mL/min**、**尿量 >60 mL/hr または >400 mL/day**（利尿薬なし）が成功と相関。小児は尿量 >0.5 mL/kg/hr。標準化定義の欠如を公式に問題提起。
  DOI: 10.1186/s13054-025-05517-1

### 3.2 単一予測因子

- **尿量（離脱前）**: 最も研究され実臨床で最も使われる。閾値は研究間で不一致。
- **24時間尿中クレアチニン**: Viallet et al., 2016 (Ann Intensive Care), **≥5.2 mmol/day で84%成功, AUC 0.86**。
  https://consensus.app/papers/details/8d0d133b55aa520cb8931859dbdbaaab/
- **利尿薬反応性 + 離脱前日尿量**: Jeon et al., 2018 (Critical Care, n=1176)。乏尿例では day-1 尿量 125 mL/day がcut-off。
  https://consensus.app/papers/details/ef889c3fd9c05ad6a0db3a33b6b562f9/

### 3.3 バイオマーカー

- **proenkephalin A (penKid/PENK)**: von Groote 2022 (ELAIN事後解析) で有望
  https://consensus.app/papers/details/7d68326434af5634934a8c9d1837cdbe/ ;
  von Groote 2023 (RICH多施設外部検証, cutoff ~100 pmol/L, day3で有効だが**尿量に劣る**)
  https://consensus.app/papers/details/afd5c080c5b554deb442c20a4a6fa107/ ;
  Tichy 2024 (心臓外科後, cutoff 126.7 pmol/L, AUC 0.80)
  https://consensus.app/papers/details/b59e7cdfa09c5719965c7c34aed37733/
- **uNGAL / cystatin C**: メタ解析で uNGAL AUC 0.80（Xu 2025）。

### 3.4 多変量臨床スコア

- **UNDERSCORE** (Chaïbi et al., 2026, Intensive Care Medicine): AKIKI/AKIKI2（多施設RCT）事後解析から6変数（RRT期間・敗血症性ショック・基礎Cr・昇圧薬・人工呼吸・尿量）。**スイス独立コホートで外的検証された初の実用スコア**。導出AUC 0.86 → 外部0.73。保存的開始コホート由来でcase-mixに偏り。
  https://consensus.app/papers/details/0266050043aa5fc2873232c12deadd60/

### 3.5 機械学習 + 公開DB（飽和領域）

| 研究 | データ源 | 定義 | n（成功率） | 最良モデル/AUROC | 外的検証 |
|---|---|---|---|---|---|
| Popoff 2025 (Sci Rep) | 仏2施設＋MIMIC-IV | 7日 | 仏 | RF 0.86→MIMIC 0.72 | ✅ MIMIC |
| Liang 2024 (Renal Failure) | 単施設 | 7日+生存 | 976 (36%) | RF/XGB 0.85–0.95 | ❌ |
| Sheng 2024 (BMC Nephrol) | MIMIC-IV | 72h | 599 (79%) | RF/XGB 〜0.87 | ❌ |
| Zhong 2024 (iScience) | MIMIC-IV＋中国 | timely | 758+320 | XGB 外部0.798 | ✅ 中国施設 |
| Kashani 2024 (JASN, 抄録) | Mayo系 | — | — | ML（詳細非公開） | — |

共通: 木系アンサンブル(RF/XGBoost)が一貫して最良。再現因子＝尿量・RRT期間・cystatin C/BUN・非腎SOFA・敗血症性ショック。

URLs:
- Popoff: https://consensus.app/papers/details/4033cbf8240852448510c013dd37638e/
- Liang: https://consensus.app/papers/details/a7914a66565b5ad1b253c279d468cc15/
- Sheng: https://consensus.app/papers/details/5dce525883f251788b54154c3f8f9d13/
- Zhong: https://consensus.app/papers/details/2e8b11e5f0325755b01d51c4da686e2d/
- Kashani: https://consensus.app/papers/details/d18b84864c605b77add1cc4773f2ac5f/

### 3.6 介入研究（RCT / 前向き）

- **LIBERATE-D** (Liu KD et al., JAMA 2026;335(4):326-335): 透析依存AKI・血行動態安定・IHD予定例で **保存的透析戦略 vs 従来戦略** を比較した多施設非盲検RCT。n=221。主要評価項目（退院時腎回復＝連続14日透析フリー＋生存）は保存的群64% vs 従来群50%（差13.8%, P=0.04）だが**調整後は非有意（OR1.56, P=0.15）**。仮説生成的。IHD/安定例限定、CRRT/重症例は未検討。
  DOI: 10.1001/jama.2025.21530 (PMC12595548)
- **Ice, Kashani, Shawwa et al., 2026** (J Crit Care): 標準化フォームによるCKRT離脱のパイロット。n=67。標準化は離脱成功率を改善せず。
  DOI: 10.1016/j.jcrc.2026.155505

### 3.7 小児

- **WE-ROCK** (Stenson et al., 2024, Intensive Care Medicine): 32施設7カ国、n=622。VIS・PELOD-2・離脱前尿量・短いCRRT期間が成功と関連。
  https://consensus.app/papers/details/8e36854df9065925be3bc0e82db5e931/

---

## 4. Gaps（差別化の余地）

1. **離脱成功の定義が非標準化**（72h / 7日 / 14日 / 退院まで が混在）→ メタ解析がcut-off決定に失敗。複数定義での感度分析自体が価値。
2. **真の外的検証の不足** — eICU-CRD を外部検証に使った離脱予測研究は空白。MIMIC開発→eICU検証→Amsterdam検証の三段階は未踏。
3. **時系列ダイナミクスの未活用** — 既存はスナップショット特徴量のみ。尿量トレンド・累積水分バランスの軌跡・Cr産生率動態は手薄。
4. **因果推論の空白** — 「離脱の試み」を介入とみなす target trial emulation はほぼ無い。LIBERATE-Dの大規模・CRRT/重症例への拡張余地。
5. **CRRT限定が多くRRT全般が手薄** — IHD/SLED統合モデルが少ない。
6. **臨床的有用性・較正の報告不足** — decision curve / calibration を揃えた実装志向研究が乏しい。

---

## 5. Implications / Candidate Directions

- **(A)** MIMIC-IV開発 → eICU/Amsterdam での厳密な多施設外部検証 ＋ 離脱定義の標準化・複数定義比較
- **(B)** 予測モデルで層別化し「どの患者に保存的戦略が有効か」を異質性解析(HTE)で検討（LIBERATE-D連携）
- **(C)** LIBERATE-D型 target trial emulation を CRRT/重症例へ拡張（因果）
- **(D)** 時系列特徴量（尿量軌跡・水分バランス）を活かした動的予測

推奨: (A)+(B) の組合せ（実現性×ギャップのバランス最良）、尖らせるなら (C)。

---

## 6. References（主要）

検証済み/重要文献は本文中に URL / DOI を併記。引用検証は citation-verification スキルで別途実施予定。
