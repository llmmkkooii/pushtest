# Data Access Playbook: RRT Liberation Research

> Project: ICU RRT/透析離脱 臨床研究のデータ入手手順
> Companion: [research-proposal-rrt-liberation.md](research-proposal-rrt-liberation.md) / [literature-review-rrt-liberation.md](literature-review-rrt-liberation.md)
> Last updated: 2026-06-11

---

## 0. 全体像（2 Tier）

| Tier | データ | 状態 | 期間 | 費用 |
|---|---|---|---|---|
| **Tier 1: 公開ICU DB** | MIMIC-IV・eICU-CRD | ✅ **取得済み** | — | 無料 |
| | AmsterdamUMCdb | 未（外部検証候補） | 数週 | 無料 |
| **Tier 2: 共有RCTデータ** | STARRT-AKI・AKIKI/2・ATN 等 | 未（申請ベース） | 数か月 | 通常無料/共同研究 |

設計方針: **Tier 1で第1弾を即着手 → Tier 2を並行申請して外部検証/回復アウトカムを強化**。

---

## 1. Tier 1: 公開ICU DB（参考・取得済み含む）

- **MIMIC-IV / eICU-CRD**: PhysioNet credentialed access（CITI "Data or Specimens Only Research" → credentialing → DUA）。**取得済み**。
- **AmsterdamUMCdb**: Amsterdam UMC / ESICM 窓口にリクエスト → EULA署名 → データアクセス委員会承認。※最新の申請ポータルURLは要確認。
- 補足候補: HiRID・SICdb（PhysioNet、同手順）。

---

## 2. Tier 2: 共有RCTデータ（本ドキュメントの主眼）

### 2.1 STARRT-AKI（最優先・最大規模 n=3,019・90日透析依存あり）

- **方式**: 試験 Co-Chairs へ直接メール提案（The George Institute 方針準拠）
- **連絡先**:
  - Sean Bagshaw … `bagshaw@ualberta.ca`
  - Ron Wald … `Ron.Wald@unityhealth.to`
- **手順**:
  1. コンセプト提案書を作成（specific aims＋方法論的に妥当な解析計画）
  2. Co-Chairs 2名へメール送付
  3. data sharing & access agreement 署名
  4. 用途限定確認 → データ受領
- **時期**: 主要・副次解析出版(2020)＋2年経過済み＝**現在申請可能**
- 参考: https://www.georgeinstitute.org/data-sharing-policy

### 2.2 AKIKI / AKIKI2（UNDERSCOREの母体・仏多施設）

- **方式**: スポンサー APHP ＋科学委員会の正式審査（STARRT-AKIより手続きやや重い）
- **連絡先**:
  - Didier Dreyfuss … `didier.dreyfuss@aphp.fr`（検証済み）
  - Stéphane Gaudry（筆頭/責任、Hôpital Avicenne, Bobigny）にもCC。※最新メールは直近AKIKI論文で確認
- **手順**:
  1. コンセプト提案書（specific aims・解析計画・**利益相反なしを明記**）
  2. 責任著者へメール提案
  3. スポンサー・科学委員会が審査（科学的妥当性＋競合研究がないこと）
  4. data access agreement ＋ **守秘義務契約** 署名
  5. **セキュアなオンラインプラットフォーム**でデータ移譲

### 2.3 ATN（米VA/NIH, n=1,124・強度試験）

- **方式**: NIDDK Central Repository (R4R) 申請
- **手順**: https://repository.niddk.nih.gov でATN（NCT00076219）検索 → データリクエスト（**ancillary study**）→ **シニアPIを正式申請者** → IRB承認/免除＋RMDA/DUA署名

### 2.4 RENAL（ANZICS, n≈1,500）・ELAIN/RICH（独, Zarbock）

- RENAL: George Institute / ANZICS CTG 経由（STARRT-AKIと同系窓口）
- ELAIN/RICH: 責任著者 Alexander Zarbock（University of Münster）へ ancillary 解析提案（penKid解析の共同実績あり）

### 2.5 IPDMA 連合（近道の選択肢）

- 開始タイミングIPDMA（Gaudry, Lancet 2020）— AKIKI/ELAIN/IDEAL-ICU/STARRT-AKI統合済み
- IMPROVE-AKI（強度試験, 8試験中7試験 n=3,682）— RENAL/ATN統合済み・**透析非依存への回復**をアウトカム化
- → 個別申請より、連合に新規解析の問いを提案する方が速いことがある

### 2.6 Vivli（本テーマには不向き・予備）

- 製薬企業の敗血症/ARDS薬剤治験が中心。**RRT離脱の主要RCTは非収載**。
- 3段階審査（管理者チェック→提供者審査→独立パネル）→DUA→セキュア環境（無料）。
- 用途: 将来 敗血症/ARDS等へ広げる際の追加コホート。実物は vivli.org で直接メタデータ検索。

---

## 3. 共通の鍵：コンセプト提案書（1〜2ページ）

どの経路でもこれ1枚が勝負を決める。

| 項目 | 内容 |
|---|---|
| タイトル | 提案する二次解析の題目 |
| 背景・ギャップ | なぜこの問いか |
| **Specific aims / 仮説** | 限定的・明確に |
| なぜこの試験データか | 必要変数がそこにある理由 |
| 解析計画 (SAP) | アウトカム定義・統計手法・サブグループ |
| 要求変数リスト | 具体的変数名 |
| チーム・役割 | **シニアPI必須** |
| 著者・出版方針 | 原試験グループとの共著想定 |
| COI・資金 | 利益相反なしを明記（特にAKIKI） |
| データセキュリティ | 保管・廃棄計画 |

---

## 4. 事前チェックリスト

- [ ] 京大の**シニアPI**を共同申請者/責任者に確保
- [ ] 京大IRBへ該当性確認（脱識別公開DBの二次利用／RCT二次解析）
- [ ] **「透析離脱」の定義確定**（②回復型=透析非依存 等）← 提案書aimsの前提
- [ ] コンセプト提案書（英文）作成
- [ ] STARRT-AKI: Co-Chairs へメール
- [ ] AKIKI: Dreyfuss/Gaudry へメール（APHP審査）
- [ ] ATN: NIDDK-CR 申請

---

## 5. 推奨シーケンス

1. **いま**: Tier 1（取得済みMIMIC/eICU）で第1弾の解析設計に着手
2. **並行**: 「透析離脱」定義を確定 → コンセプト提案書作成
3. **早期に種まき**: STARRT-AKI（直接・最有力）へ提案、続いてAKIKI/ATN
4. 第1弾の結果が出た段階で、RCT級外部検証として統合
