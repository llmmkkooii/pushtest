# ChatGPT → Obsidian Quick-Save Bookmarklet

ChatGPT の重要な会話を **ブラウザのブックマーク 1 クリック** で Obsidian に保存します。
あなたの既存運用 (`Chats/ChatGPT/_manual/_template.md`) に完全準拠した形式で書き出します。

## 何が起きるか

ChatGPT の会話画面でブックマークレットをクリックすると:

1. ページ内の会話全体を抽出してマークダウン化
2. タイトル確認用ダイアログ (初期値はチャットのタイトル)
3. "Why kept" (なぜ重要か) を聞く 1 行ダイアログ ※空欄可
4. 全文をクリップボードにコピー (安全網)
5. `obsidian://new` URI で Obsidian を起動し、下記の場所に新規ノート作成

```
~/ObsidianVault/Chats/ChatGPT/_manual/YYYY-MM-DD_<topic>.md
```

frontmatter / 本文は `_manual/_template.md` と同形式 (`manual: true`, `## User` / `## Assistant`, `自分のメモ` / `関連` セクション付き)。

## インストール (Safari / Chrome / Firefox / Arc 共通)

1. このフォルダで一度だけビルド:
   ```bash
   cd chatgpt-to-obsidian
   node build.js
   ```
   `bookmarklet.txt` が生成されます (1 行の `javascript:...`)。

2. ブラウザのブックマークバーで右クリック → 「新しいブックマークを追加」
   - 名前: `📥 ChatGPT → Obsidian`
   - URL: `bookmarklet.txt` の中身を**まるごとコピペ**

3. 完了。ChatGPT (`chatgpt.com/c/...`) を開いた状態でブックマークをクリックすればOK。

> 初回のみ、ブラウザが `obsidian://` を開いてよいか確認します。「常に許可」にしておくと以後ノンストップ。

## 動作確認

```bash
# Node の構文チェック
node --check bookmarklet.src.js

# 仮想 ChatGPT ページでの抽出テスト (jsdom 必要)
npm install --prefix /tmp jsdom   # 一度だけ
node /tmp/bm_smoke.js             # ← `/tmp/bm_smoke.js` がある場合
```

## 保存ファイル例

```yaml
---
title: "SGLT2阻害薬の腎保護効果"
source: chatgpt
manual: true
date: 2026-05-21
url: "https://chatgpt.com/c/abc-123-test"
tags:
  - ai-chat
  - manual
aliases: []
phi-source: false
---
# SGLT2阻害薬の腎保護効果

> [!info] Manually saved from ChatGPT
> - **Source**: ChatGPT (manual save, not quarterly export)
> - **Share URL**: https://chatgpt.com/c/abc-123-test
> - **Date**: 2026-05-21
> - **Why kept**: SGLT2の機序を後でメモに使う

## User

…

## Assistant

…

## 自分のメモ
- 重要ポイント:
- 後で確認:
- 関連 wiki: [[wiki/topics/]]

## 関連
- [[]]
```

これで `["manual": "true"]` で絞り込めば「自分が選んだ重要会話のみ」が一覧化されます。

## 注意点

| 項目 | 内容 |
|------|------|
| **同日複数保存** | 同じトピック名だと Obsidian 側で既存ノートを開くだけになります。タイトル確認ダイアログで末尾を変えるか、後で `-2`, `-3` にリネームしてください。 |
| **長い会話 (>7.5KB)** | URI 経由では送れないので、空ノートを作って通知を出します。クリップボードに全文入っているので Cmd+V してください。 |
| **PHI を含む会話** | このブックマークレットはデフォルト `phi-source: false` で書き出します。PHI を含む場合は保存後に `phi-source: true` に手動変更し、本文を deidentify してください (テンプレ規約通り)。 |
| **ChatGPT の DOM 変更** | ChatGPT が UI を大きく変えた場合、メッセージ抽出が失敗することがあります。その場合 `[data-message-author-role]` セレクタ部分を調整してください。 |
| **vault 名固定** | `bookmarklet.src.js` 冒頭の `VAULT = 'ObsidianVault'` を変えてリビルドすると別 vault に向きます。 |

## 仕組み (内部)

- **抽出**: `[data-message-author-role]` を `querySelectorAll` で取得、`role` 属性で User/Assistant を判別
- **マークダウン化**: 内蔵の最小 HTML→Markdown 変換 (見出し / コード / リスト / リンク / 表 / 引用)
- **送信**: `obsidian://new?vault=...&file=...&content=...` (URL エンコード)
- **保険**: 常にクリップボードへ全文コピー (失敗時に手で貼れるように)

## ファイル

- `bookmarklet.src.js` — 編集可能な可読ソース
- `build.js` — 状態機械でコメントを除去し `javascript:` URL に変換
- `bookmarklet.txt` — ブラウザに貼る最終形 (commit してもしなくても可)
