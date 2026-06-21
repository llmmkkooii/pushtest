# Design: RRT Liberation Analysis Pipeline (1st workflow)

> Project: ICU CRRT 離脱（liberation）予測モデルの多施設外部検証
> Companion: [research-proposal-rrt-liberation.md](../../../plan/research-proposal-rrt-liberation.md),
> [data-access-playbook.md](../../../plan/data-access-playbook.md),
> [literature-review-rrt-liberation.md](../../../plan/literature-review-rrt-liberation.md)
> Origin: 「Strategic Implementation of AI Agent Plugins and APIs for Business Automation」の
> "Data Analytics" 柱を、研究ワークフロー自動化（データ解析パイプライン）として具体化したもの。
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-21

---

## 0. 目的とスコープ

資料が薦める業務自動化ツール群の大半（Computer Use / Security Review / Web→Markdown /
引用付き調査 / ノーコード自動化）は既にこのClaude Code環境に存在する。純粋な新規価値は
「既存部品を1本の再現可能ワークフローに束ねる」ことにある。1本目として **RRT離脱外部検証
研究の、config駆動・再現可能な解析パイプライン基盤** を `tools/rrt-liberation/` に新規構築する。

資料の「読込→統計→図表→レポート」は、本研究では
**「コホート抽出→特徴量→モデル→較正/DCA→TRIPODレポート」** に対応する。

**Non-goals（今回やらないこと）**:
- 開発モデル（logistic / RF / XGBoost）の学習実装（registry予約のみ）
- eICU / AmsterdamUMCdb での外部検証実走（base/config予約のみ）
- decision curve（DCA）の実装（interfaceのみ）
- 離脱定義感度分析（72h/14d）の実走（config枠のみ）

---

## 1. アーキテクチャ

`tools/rrt-liberation/` に uv プロジェクトとして新規作成。Hydra でステージを合成し、
factory/registry で各段の実装を差し替え可能にする。coding-style ルール準拠
（200-400行/ファイル、`@dataclass(frozen=True)` config、型ヒント、logger、factory/registry）。

```
tools/rrt-liberation/
├── pyproject.toml              # uv管理。deps: pandas, scikit-learn, statsmodels,
│                               #   numpy, pyyaml, hydra-core, matplotlib, (xgboost任意)
├── README.md                   # 実行方法・PHI境界・再現手順
├── .gitignore                  # data/, outputs/ を除外（credentialed data混入防止）
├── conf/                       # Hydra設定（全パラメータここに集約・immutable）
│   ├── config.yaml             # defaults合成 + seed=42
│   ├── cohort/                 # mimic.yaml / eicu.yaml / amsterdam.yaml
│   ├── liberation/             # def_7d.yaml / def_72h.yaml / def_14d.yaml
│   ├── features/               # baseline.yaml（事前指定変数セット）
│   ├── model/                  # logistic.yaml / rf.yaml / xgboost.yaml / underscore.yaml
│   └── eval/                   # discrimination + calibration + dca
├── src/rrt_liberation/
│   ├── __init__.py
│   ├── cohort/                 # ① コホート抽出（DB横断インターフェース）
│   │   ├── __init__.py         #   CohortFactory / register_cohort
│   │   ├── base.py             #   BaseCohortBuilder（抽象）
│   │   ├── mimic.py            #   MIMIC-IV（procedureevents/inputevents→crrt再構成）
│   │   └── eicu.py             #   eICU（treatment/dialysis）※base/stub
│   ├── liberation/             # ② 離脱試行・再開の操作的定義（本研究の肝）
│   │   ├── __init__.py         #   LiberationDefFactory
│   │   └── rules.py            #   ≥X時間停止継続 / 7d・72h・14d 再開判定
│   ├── features/               # ③ 特徴量構築（離脱試行時点の日常変数）
│   │   ├── __init__.py
│   │   └── builder.py
│   ├── model/                  # ④ モデル（factory）
│   │   ├── __init__.py         #   ModelFactory / register_model
│   │   ├── base.py
│   │   ├── logistic.py         #   主モデル（解釈可能）※stub
│   │   ├── tree.py             #   RF/XGBoost（性能上限参照）※stub
│   │   └── underscore.py       #   UNDERSCORE再現（ベンチマーク・1本目で実装）
│   ├── evaluation/             # ⑤ 評価（results-analysisスキル準拠）
│   │   ├── __init__.py
│   │   ├── discrimination.py   #   AUROC/AUPRC + bootstrap CI
│   │   ├── calibration.py      #   calibration plot, slope/intercept
│   │   └── dca.py              #   decision curve ※interfaceのみ
│   ├── reporting/              # ⑥ レポート（results-reportスキル準拠）
│   │   └── report.py           #   STROBE/TRIPODフロー図 + Table 1 + 図表束
│   └── utils/
│       ├── seed.py             #   set_seed（reproducibilityルール）
│       └── io.py               #   ローカルI/O（外部送信なし）
├── pipeline/
│   └── run.py                  # Hydra @main：cohort→features→model→eval→report
├── tests/                      # pytest（合成データで各段検証、実PHI不使用）
│   └── fixtures/               # synthetic_*.csv（MIMIC/eICUスキーマ模倣・実値なし）
└── outputs/                    # Hydra自動保存（gitignore）
```

設計の要点:
- DB差し替えは config + registry で吸収（`run.py cohort=eicu` で外部検証へ切替、
  同一固定モデルを適用 = true external validation）。
- 離脱定義の感度分析は `liberation=def_72h` 等のoverrideで1コマンド切替（proposal H3）。

---

## 2. Walking skeleton（1本目に通す縦スライス）

1本目で **MIMIC-IV の1ステージ縦スライス**を端から端まで通す。残りはinterface確保＋stub。

**1本目で実装**:
1. `run.py` が Hydra config を読み、`set_seed(42)`、outputs にconfig自動保存。
2. `cohort=mimic` → `MimicCohortBuilder` が抽出済みCSV（開発は合成CSV）を読み、
   包含/除外を適用、離脱試行エピソードを抽出（`liberation=def_7d`）。
3. `features=baseline` → 事前指定変数（尿量・Cr・SOFA・昇圧薬・人工呼吸・CRRT期間 等）を構築。
4. `model=underscore` → UNDERSCORE再現を1本目のモデルに（公開係数で学習不要・即「数字が出る」）。
5. `evaluation` → discrimination（AUROC + bootstrap CI）と calibration plot を出力。
6. `reporting` → STROBE/TRIPODフロー図 + Table 1 + 図を `outputs/` に保存。

→ 「コホート→特徴量→ベンチマークスコア→識別能/較正→Table 1」が1コマンドで再現可能に回る
（proposal milestones step 3〜4前半に対応）。

**1本目はstub/interfaceのみ（次イテレーション）**:
- `model=logistic` / `tree`（registry登録、中身は `NotImplementedError`）
- `cohort=eicu` / 外部検証ループ（config + baseクラスのみ）
- `dca`（interfaceのみ）
- `liberation=def_72h/def_14d`（config枠のみ、実走は次段）

**なぜ UNDERSCORE を1本目のモデルにするか**: 係数が論文公開済み＝学習不要で即動き、
本研究のベンチマーク基準そのもの。骨格が「本物の数字」を出す状態で完成し、以降の開発モデルは
このベンチマークに対して評価される土台になる。

**1本目の Definition of Done**:
- `uv run python -m pipeline.run cohort=mimic liberation=def_7d model=underscore` が
  合成データで完走。
- `pytest` が緑。
- `outputs/` にフロー図・Table 1・AUROC値・calibration plot が生成される。

---

## 3. データ/PHI境界

資料の "Security Review" 柱であり、proposal §5「外部AIサービスへ投入しない」の構造的実装。
**Claudeはコードを書くが、credentialed dataの中身は取り込まない。**

| 層 | 中身 | Claude/外部AIの扱い |
|---|---|---|
| コード層 | `src/`, `conf/`, `pipeline/`, `tests/` | ✅ 読み書きOK（PHI非含有） |
| 合成データ層 | `tests/fixtures/synthetic_*.csv` | ✅ 生成・参照OK（人工データのみ） |
| 実データ層 | `data/mimic/`, `data/eicu/`（credentialed） | ❌ Claudeに渡さない。`.gitignore`＋ローカルのみ |

**構造的ガード**:
1. `.gitignore` で `data/` と `outputs/` を除外。
2. パイプライン開発・デバッグは全て合成データで行う（MIMIC/eICUの列名・型・分布のみ模倣、実値なし）。
3. 実データでの本番実行はユーザーがローカルで `uv run`。Claudeは集計済み非PHI出力（AUROC等）だけ解釈支援。
4. `utils/io.py` はローカルI/Oのみ。ネットワーク送信コードを置かない。
5. README に「PHI境界」節を明記。
6. credentialed dataは NotebookLM/Gemini/Perplexity 等いずれの外部サービスにも投入しない
   （既存 account guardrail と整合）。資料の Gemini API 等は公開文献の処理にのみ使う。

---

## 4. テスト戦略

実PHIを使わず、合成データでパイプラインの正しさを保証（TDD寄り）。

**合成データfixture**: `tests/fixtures/` に MIMIC/eICU スキーマ模倣の人工CSV生成ヘルパー。
既知の正解を仕込む（例：離脱試行3例・うち1例が5日目に再開＝7d定義で「失敗」1件）。seed固定で決定的。

**ユニットテスト**:
| 対象 | 検証内容 |
|---|---|
| `liberation/rules.py` | ≥X時間停止判定、7d/72h/14d再開フラグが既知正解と一致（最重点） |
| `cohort/mimic.py` | 包含/除外件数、エピソード境界 |
| `features/builder.py` | 変数の欠測・単位・離脱試行時点の時間窓 |
| `model/underscore.py` | 公開係数で既知入力→既知スコア（転記ミス検出） |
| `evaluation/*` | 既知ラベル/予測でAUROC・calibration slopeが手計算と一致、bootstrap CIの決定性 |

**統合テスト（スモーク）**: `test_pipeline_smoke.py` が合成データで端から端まで実行し、
`outputs/` にTable 1・AUROC・calibration plotが生成されることを確認（= 1本目のDoD）。

**検証ループ**: 実装後 `ruff check` → `mypy src/` → `pytest` を緑にしてからコミット（verification-loop）。

**再現性テスト**: 同seedで2回実行 → AUROC等が完全一致（reproducibilityルール）。

---

## 5. 次段（このspecの外、将来イテレーション）

1. 開発モデル（logistic主＋RF/XGBoost参照）の学習実装
2. eICU 外部検証（固定モデル適用）→ AmsterdamUMCdb
3. 離脱定義感度分析（72h/7d/14d/退院時）の実走 = proposal H3
4. DCA（decision curve）実装
5. 多重代入（欠測）、TRIPOD-AI report / PROBAST 評価の自動生成
