# Design: RRT UNDERSCORE-6 Feature Engineering (iteration 2, sub-project E)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Depends on: A (dev logistic model), B (eICU external validation)
> Specs: [A](2026-06-21-rrt-dev-logistic-model-design.md) / [B](2026-06-22-rrt-eicu-external-validation-design.md) / [iteration1](2026-06-21-rrt-liberation-pipeline-design.md)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-22

---

## 0. 位置づけとスコープ

iteration 2 の特徴量エンジニアリング・サブプロジェクト。現状 `build_features` は urine 1本の if/elif のみ。
本サブプロジェクトで **UNDERSCORE-6 予測子セット**（CRRT期間・敗血症性ショック・基礎Cr・昇圧薬・人工呼吸・尿量）を、
**特徴量registry** で DB非依存に実装し、MIMIC/eICU 双方の合成ソースを揃える。これにより開発ロジスティック(A)も
UNDERSCORE ベンチマークも eICU 外部検証(B)も「本来の6変数」で動く。すべて合成データ。credentialed data は使わない・コミットしない。

**Non-goals**:
- §7 の残り予測子（BUN/乳酸/HCO₃/水分バランス/体重変化/非腎SOFA 等）= 後段
- 実MIMIC/eICU SQL 抽出（実テーブルの実マッピング、実eICUの薬剤/呼吸器/診断テーブル）= 後段
- DCA(C)、定義感度(D)、MICE、AmsterdamUMCdb

## 1. 確定した設計判断（brainstorm 合意）

| 項目 | 決定 |
|---|---|
| 予測子セット | UNDERSCORE-6（urine, baseline_creatinine, crrt_duration_hours, sepsis_shock, vasopressor, mechanical_ventilation） |
| DB範囲 | DB非依存。MIMIC+eICU 双方に合成ソース（labs に creatinine 追加、flags 表追加） |
| アーキ | 特徴量registry（`register_feature`/`FEATURE_REGISTRY`）。`build_features(cohort, sources, predictors)` |
| 正準events | `BaseCohortBuilder.to_canonical_events` を追加（Mimic=恒等、Eicu=offset変換）。duration は正準events上で算出 |
| 後方互換 | `flags_csv` は任意(None)。二値特徴量は flags 欠如→0。単一特徴量スモークは不変で緑 |

## 2. アーキテクチャ

```
src/rrt_liberation/features/
├── __init__.py            # build_features, register_feature, FEATURE_REGISTRY export
├── builder.py             # build_features(cohort, sources, predictors) — registry駆動部
└── registry.py            # 新規: FEATURE_REGISTRY / register_feature / 6特徴量関数
src/rrt_liberation/cohort/
├── base.py                # + to_canonical_events(events)（既定=恒等）
├── mimic.py               # build が to_canonical_events 経由（恒等）
└── eicu.py                # to_canonical_events に offset変換を公開化、build が経由
tests/fixtures/synth.py    # + make_two_class_flags / make_eicu_flags、labs に creatinine(50912) 追加
conf/features/baseline.yaml # predictors: 6
conf/model/underscore.yaml  # coefficients: 6スロット(プレースホルダ0)
conf/cohort/{mimic,eicu}.yaml # + flags_csv
pipeline/run.py / validate.py # sources={labs,events(正準),flags} 構築、flags_csv 任意
```

registry の契約:
- `register_feature(name)` デコレータ → `FEATURE_REGISTRY[name] = fn`。
- 特徴量関数シグネチャ統一：`fn(cohort: DataFrame, sources: Dict[str, DataFrame]) -> pd.Series`（cohort行に整列、欠測NaN可）。
- `sources`：`{"labs": stay_id/itemid/valuenum, "events": 正準events, "flags": stay_id/sepsis_shock/vasopressor/mechanical_ventilation}`。
- `build_features(cohort, sources, predictors)`：predictors順に registry 参照→列追加。未登録予測子は警告＋NaN列。
- coding-style準拠（registry、200-400行、型ヒント、logger、`__all__`）。`model=*`・cohort・内部/外部検証は不変。

## 3. 6特徴量の操作的定義

各 `fn(cohort, sources) -> Series`（cohort行＝離脱試行）。

| 特徴量 | 型 | ソース | 定義 |
|---|---|---|---|
| `urine_output_24h` | 連続 | labs | itemid 226559 を stay_id 平均（既存ロジック移設）。stay平均（24h窓化は次段） |
| `baseline_creatinine` | 連続 | labs | itemid 50912(Cr) を stay_id **最小値**（基礎腎機能の保存的代理）。欠測NaN |
| `crrt_duration_hours` | 連続(期間) | events(正準) | **試行時点まで**のCRRT稼働総時間(h)。各区間 `max(0, min(endtime, attempt_time) − starttime)` を合算。per-attempt（attempt_time依存） |
| `sepsis_shock` | 二値 | flags | flags の該当列を stay_id 結合。flags欠如/該当stayなし→0 |
| `vasopressor` | 二値 | flags | 同上 |
| `mechanical_ventilation` | 二値 | flags | 同上 |

設計判断:
- `crrt_duration_hours` は **per-attempt**（同一stay複数試行で各試行時点まで打ち切り）。`label_outcome`/`find_attempts` の `attempt_time` を使用。UNDERSCORE「CRRT期間」を離脱試行時点で正しく表現。
- 二値の欠測=0（記録なし＝非該当）。欠測フラグは作らない（0が意味を持つ）。
- lab系（urine/baseline_creatinine）の欠測はNaN→Preprocessor(2A)が中央値代入＋`*_missing`フラグ。
- `baseline_creatinine`=最小値（後ろ向き設計の標準近似、proposal §7「基礎Cr(推定)」）。
- すべて正準sources上で動く＝MIMIC/eICU共通。

## 4. config・パイプライン配線（後方互換）

正準events の取得:
- `BaseCohortBuilder.to_canonical_events(events) -> DataFrame`（既定=恒等）。Mimic=恒等、Eicu=offset変換（既存 `_to_canonical` を公開化、`build` も内部で使用）。
- パイプライン：`sources["events"] = builder.to_canonical_events(raw_events)` で DB非依存に正準events。

sources 組み立て（run.py / validate.py）:
```
raw_events = read_csv(events_csv); labs = read_csv(labs_csv)
cohort = builder.build(raw_events, horizon)
sources = {"labs": labs, "events": builder.to_canonical_events(raw_events)}
if flags_csv: sources["flags"] = read_csv(flags_csv)
feats = build_features(cohort, sources, predictors)
```
- `run_pipeline` / `run_external_validation` に `flags_csv: Optional=None` 追加。
- 二値特徴量関数は `sources.get("flags")` 欠如→0（lenient）。既存の単一特徴量スモーク（urineのみ・flags無し）は不変で緑。

config 変更:
- `conf/cohort/{mimic,eicu}.yaml`: `flags_csv: ${paths.data_dir}/{mimic,eicu}/flags.csv`。
- `conf/features/baseline.yaml`: predictors 6変数。
- `conf/model/underscore.yaml`: coefficients 6スロット（プレースホルダ0、Chaïbi 2026 から転記）。
- `main`: `flags_csv=cfg.cohort.flags_csv` を渡す。

後方互換の波及:
- `build_features(cohort, labs, predictors)` → `(cohort, sources, predictors)`。直接呼ぶのは `test_features.py` のみ→更新。
- run.py/validate.py 内部で sources 構築（関数経由スモークは flags_csv 省略で不変）。
- urine 既存ロジックは `urine_output_24h` 特徴量関数へ移設（重複排除）。model=underscore/logistic・cohort・内部/外部検証は不変。

## 5. テスト戦略

合成ソース（実PHIなし）。

合成fixture拡張:
- `make_two_class_labs`/`make_eicu_labs` に creatinine(itemid 50912) 追加（一部欠測）。
- `make_two_class_flags`/`make_eicu_flags`: canonical flags 表（`stay_id, sepsis_shock, vasopressor, mechanical_ventilation` 0/1、決定的）。

ユニット（`tests/test_feature_registry.py`）:
| 対象 | 検証 |
|---|---|
| registry | register/未登録→警告+NaN列/predictors順・行数保存 |
| urine_output_24h | stay平均が既知値一致 |
| baseline_creatinine | stay最小値/欠測stayNaN |
| crrt_duration_hours | per-attempt 打ち切り `Σ max(0,min(end,attempt)−start)` 手計算一致/複数試行で異なる |
| 二値3種 | flags結合0/1/該当なし0/sources に flags無し→全0 |

DB非依存テスト: 同一特徴量群が Mimic/Eicu 両 cohort（to_canonical_events 経由）で同じ列を生成。

統合スモーク:
- `test_pipeline_smoke.py` に 6変数 logistic 経路追加（MIMIC labs+flags+creatinine）→ coefficients.csv 6行。
- 6変数 train→save→eICU external_validate が動く（DB非依存）。
- 既存スモーク（urineのみ・flags無し）は不変で緑。

検証ループ: `ruff → mypy src pipeline tests → pytest` 緑。再現性: 6変数 logistic 同seed2回で corrected AUROC・係数一致。

## 6. 次段（このspecの外）

- §7 残り予測子（BUN/乳酸/HCO₃/水分バランス/非腎SOFA 等）
- 実MIMIC/eICU SQL 抽出（実テーブル・実eICU薬剤/呼吸器/診断マッピング）
- 尿量の24h窓化、DCA(C)、定義感度(D)、MICE、AmsterdamUMCdb、UNDERSCORE/尿量の外部比較
