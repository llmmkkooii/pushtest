#!/bin/bash
# ChatGPT (or any source) → Obsidian quick-save
#
# Reads clipboard, asks for title + "why kept", and writes a markdown note to
# ~/ObsidianVault/Chats/ChatGPT/_manual/YYYY-MM-DD_<topic>.md matching the
# existing _manual/_template.md convention. Then opens the note in Obsidian.
#
# Designed to be triggered by a macOS Shortcuts / Automator hotkey, so it
# works in Atlas, Safari, Chrome, anywhere — no browser extension needed.
#
# Usage:
#   1. Select the ChatGPT conversation text and Cmd+C
#   2. Run this script (via hotkey)
#   3. Answer 2 dialogs
#   4. Obsidian opens the new note
set -euo pipefail

VAULT="ObsidianVault"
VAULT_PATH="$HOME/$VAULT"
FOLDER="Chats/ChatGPT/_manual"
DEST_DIR="$VAULT_PATH/$FOLDER"

# --- Read clipboard ---
BODY="$(pbpaste)"
if [[ -z "$BODY" ]]; then
  osascript -e 'display alert "クリップボードが空です" message "ChatGPT で会話をコピー (⌘C) してから実行してください。" as critical' >/dev/null 2>&1
  exit 1
fi

# --- Pick a default title from the first non-empty line of clipboard ---
DEFAULT_TITLE="$(printf '%s' "$BODY" | awk 'NF{print; exit}' | head -c 60)"
[[ -z "$DEFAULT_TITLE" ]] && DEFAULT_TITLE="ChatGPT conversation"

# --- Ask for title ---
TITLE=$(osascript <<EOF 2>/dev/null
try
  set theDefault to "$DEFAULT_TITLE"
  set theDialog to display dialog "保存するタイトル (=ファイル名トピック):" default answer theDefault buttons {"キャンセル","OK"} default button "OK" with title "ChatGPT → Obsidian"
  return text returned of theDialog
on error
  return ""
end try
EOF
)
[[ -z "$TITLE" ]] && exit 0

# --- Ask for "why kept" ---
REASON=$(osascript <<'EOF' 2>/dev/null
try
  set theDialog to display dialog "Why kept (なぜ重要か、1行で。空欄可):" default answer "" buttons {"スキップ","OK"} default button "OK" with title "ChatGPT → Obsidian"
  return text returned of theDialog
on error
  return ""
end try
EOF
)

# --- Build filename ---
DATE="$(date +%Y-%m-%d)"
TOPIC="$(printf '%s' "$TITLE" \
  | tr '/\\:*?"<>|#%&{}$!'"'"'@+`=' '-' \
  | tr -s ' \t' '-' \
  | tr -s '-' \
  | sed 's/^-//; s/-$//' \
  | cut -c1-60)"
[[ -z "$TOPIC" ]] && TOPIC="untitled"

mkdir -p "$DEST_DIR"
BASE="$DATE"_"$TOPIC"
FILEPATH="$DEST_DIR/$BASE.md"

# --- Avoid silent overwrite: append -2, -3, ... if the file exists ---
i=2
while [[ -e "$FILEPATH" ]]; do
  FILEPATH="$DEST_DIR/$BASE-$i.md"
  i=$((i + 1))
done

REASON_LINE="${REASON:-←後で使う見込み・理由を 1 行}"
TITLE_ESCAPED="${TITLE//\"/\\\"}"

# --- Write the note (matches _template.md convention) ---
cat > "$FILEPATH" <<EOF
---
title: "$TITLE_ESCAPED"
source: chatgpt
manual: true
date: $DATE
url: ""
tags:
  - ai-chat
  - manual
aliases: []
phi-source: false
---

# $TITLE

> [!info] Manually saved from ChatGPT
> - **Source**: ChatGPT (manual save via clipboard)
> - **Date**: $DATE
> - **Why kept**: $REASON_LINE

## 会話

$BODY

## 自分のメモ

- 重要ポイント:
- 後で確認:
- 関連 wiki: [[wiki/topics/]]

## 関連

- [[]]
EOF

# --- Open the new note in Obsidian ---
RELATIVE="${FILEPATH#$VAULT_PATH/}"
ENCODED_FILE=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "${RELATIVE%.md}")
open "obsidian://open?vault=$VAULT&file=$ENCODED_FILE"

# --- Notify ---
osascript -e "display notification \"$BASE.md を作成しました\" with title \"ChatGPT → Obsidian\" sound name \"Glass\"" >/dev/null 2>&1
