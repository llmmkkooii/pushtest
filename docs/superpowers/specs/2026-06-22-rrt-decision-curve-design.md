# Design: RRT Decision Curve Analysis (iteration 2, sub-project C)

> Project: ICU CRRT 離脱予測モデルの多施設外部検証
> Depends on: A (dev logistic model), E (UNDERSCORE-6 features)
> Specs: [A](2026-06-21-rrt-dev-logistic-model-design.md) / [iteration1](2026-06-21-rrt-liberation-pipeline-design.md)
> Stage: brainstorming design → approved → next: writing-plans
> Date: 2026-06-22

---

## 0. 位置づけとスコープ

iteration 2 の decision curve analysis（DCA）。`evaluation/dca.py` の stub（`decision_curve` が `NotImplementedError`）を実装し、
Vickers net benefit を出力。開発ロジスティックモデル学習経路（run.py logistic）に net benefit 曲線を配線する。
proposal §10「較正＋decision curve まで提示（既存MLの欠落補完）」を満たす。すべて合成データ。credentialed data は使わない・コミットしない。

**Non-goals**: eICU外部検証(validate.py)へのDCA配線、臨床的行動マッピング（成功予測 vs 失敗回避）の精緻化、H2比較、§7残り予測子、MICE、AmsterdamUMCdb。

## 1. 確定した設計判断（brainstorm 合意）

| 項目 | 決定 |
|---|---|
| スコープ | `decision_curve` 実装 ＋ run.py(logistic) 配線（validate は次段） |
| 数式 | Vickers net benefit。treat-all / treat-none を参照線に |
| 陽性クラス | caller が渡す y/p の陽性=1 をイベント。run.py は y=success, p=P(success) |
| 閾値グリッド | 既定 `np.arange(0.01, 1.00, 0.01)`（0.01–0.99）、引数で上書き可 |
| 出力 | `dca.csv`（閾値×3系列）＋ `dca.png`（曲線） |

## 2. アーキテクチャ

```
src/rrt_liberation/evaluation/dca.py        # stub→実装: decision_curve(y, p, thresholds=None), save_dca_plot(curve, path)
src/rrt_liberation/evaluation/__init__.py   # decision_curve / save_dca_plot をexport
pipeline/run.py                             # logistic経路に dca.csv + dca.png 出力を追加
tests/test_dca.py                           # 新規
tests/test_pipeline_smoke.py                # 既存6変数logisticスモークに dca.csv 生成アサート追加
```
- `decision_curve` は決定的（seed不要）。新しいモデル・離脱ロジックは書かない。
- run.py の logistic 経路にのみ配線（model=underscore・single-class経路・validate.py・cohort・他評価は不変）。
- coding-style準拠（型ヒント・logger・`__all__`・ファイル200-400行内）。

## 3. net benefit の定義

`decision_curve(y, p, thresholds=None) -> Dict[str, object]`:
- y：0/1 二値（陽性=イベント）。p：陽性確率。thresholds：既定 `np.arange(0.01, 1.00, 0.01)`。
- 各閾値 pt（p ≥ pt を陽性判定）:
  - `NB_model(pt) = TP/N − (FP/N)·(pt/(1−pt))`（TP=判定陽性かつ真陽性、FP=判定陽性かつ偽陽性、N=全症例）
  - treat-all: `NB_all(pt) = prevalence − (1−prevalence)·(pt/(1−pt))`
  - treat-none: `NB_none = 0`
- 返り値:
```python
{
  "thresholds": [...], "net_benefit_model": [...],
  "net_benefit_all": [...], "net_benefit_none": [...],  # 全0
  "prevalence": float,
}
```
陽性クラス：`decision_curve` は y/p の陽性=1 をイベントとして計算（クラス選択は呼び出し側）。run.py logistic は y=success(離脱成功=1)・p=P(success) を渡す。臨床行動マッピングの解釈は次段。
端点：pt→1 で odds→∞ により NB が大きく負（標準）。既定グリッド0.99止まりで発散回避。決定的。

`save_dca_plot(curve, path)`：thresholds 横軸、model/all/none を3本プロット（既存 `save_calibration_plot` と同じ Agg backend・headless・parent dir 作成）。

## 4. パイプライン配線・出力

run.py の logistic 経路（`save_calibration_plot(...)` 付近）に追加:
```python
from rrt_liberation.evaluation import decision_curve, save_dca_plot  # 既存importに追加
...
dca = decision_curve(y, model.predict_proba(feats[predictors]))
write_csv(pd.DataFrame({
    "threshold": dca["thresholds"],
    "net_benefit_model": dca["net_benefit_model"],
    "net_benefit_all": dca["net_benefit_all"],
    "net_benefit_none": dca["net_benefit_none"],
}), output_dir / "dca.csv")
save_dca_plot(dca, output_dir / "dca.png")
```
- 出力 `dca.csv`＋`dca.png` を `outputs/`（gitignore）に。logistic 経路のみ（学習で2クラス確定済み）。
- `run_pipeline` の戻り値・他経路は不変。`evaluation/__init__.py` に decision_curve/save_dca_plot を export 追加。

## 5. テスト戦略

合成・既知データ（実PHIなし）、`tests/test_dca.py`:
| 検証 | 内容 |
|---|---|
| treat-none=0 | 全閾値で net_benefit_none が0 |
| prevalence | y の陽性割合と一致 |
| 手計算一致 | y=[0,0,1,1], p=[0.1,0.2,0.8,0.9] で特定閾値の NB_model/NB_all を手計算と突合 |
| treat-all公式 | `NB_all(pt)=prevalence−(1−prevalence)·pt/(1−pt)` 一致 |
| 完全分離 model≥all | 完全分離データで中庸閾値の NB_model ≥ NB_all |
| グリッド | 既定 0.01–0.99／thresholds 引数で上書き可 |
| 決定性 | 同入力で2回同一 |
| plot | `save_dca_plot` が PNG をローカル生成（parent dir・headless） |

統合：既存6変数 logistic スモークに `dca.csv` 生成アサートを追加。検証ループ：`ruff → mypy src pipeline tests → pytest` 緑。後方互換：既存全テスト・他経路不変。

## 6. 次段（このspecの外）

- eICU外部検証(validate.py)へのDCA配線、臨床行動マッピング、H2（UNDERSCORE/尿量比較）、§7残り予測子、MICE、実データ抽出、AmsterdamUMCdb。
