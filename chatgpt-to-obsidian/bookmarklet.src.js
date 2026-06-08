/* ChatGPT → Obsidian Quick-Save Bookmarklet (readable source)
 *
 * Saves the current ChatGPT conversation as a markdown note into
 *   ObsidianVault/Chats/ChatGPT/_manual/YYYY-MM-DD_<topic>.md
 * matching the existing _template.md exactly.
 *
 * - Vault: ObsidianVault (registered at /Users/llmmkkooii/ObsidianVault)
 * - Always saves the full conversation
 * - Always copies the full markdown to the clipboard as a safety net
 *   (so long conversations still work even when the obsidian:// URI is too big)
 *
 * Build the minified bookmarklet with `node build.js` and paste the result
 * into a browser bookmark URL field.
 */
(function () {
  'use strict';

  const VAULT = 'ObsidianVault';
  const FOLDER = 'Chats/ChatGPT/_manual';
  // Practical Obsidian URI ceiling on macOS (~8KB). Leave headroom.
  const URI_MAX = 7500;

  // -------- Minimal HTML → Markdown --------
  function htmlToMd(node) {
    if (!node) return '';
    if (node.nodeType === 3) return node.textContent;
    if (node.nodeType !== 1) return '';
    const tag = node.tagName.toLowerCase();
    const kids = () => Array.from(node.childNodes).map(htmlToMd).join('');
    // Filter out interactive UI cruft (Copy, Edit, voice buttons, etc.)
    if (node.getAttribute && (
      node.getAttribute('role') === 'button' ||
      node.getAttribute('aria-hidden') === 'true' ||
      /\bsr-only\b/.test(node.className || '')
    )) return '';
    switch (tag) {
      case 'script': case 'style': case 'noscript': case 'button': case 'svg': return '';
      case 'br': return '\n';
      case 'hr': return '\n\n---\n\n';
      case 'strong': case 'b': return '**' + kids().trim() + '**';
      case 'em': case 'i': return '*' + kids().trim() + '*';
      case 'del': case 's': return '~~' + kids().trim() + '~~';
      case 'code': {
        const parent = node.parentElement;
        if (parent && parent.tagName.toLowerCase() === 'pre') return node.textContent;
        return '`' + node.textContent + '`';
      }
      case 'pre': {
        const code = node.querySelector('code');
        let lang = '';
        if (code) {
          const cls = Array.from(code.classList).find(c => c.startsWith('language-'));
          if (cls) lang = cls.slice(9);
          else if (code.getAttribute('data-language')) lang = code.getAttribute('data-language');
        }
        // ChatGPT often wraps code blocks with header bars ("Copy code", language tag)
        // that appear as leading text. Strip a leading "Copy code" line if present.
        let txt = (code ? code.textContent : node.textContent).replace(/\n+$/, '');
        txt = txt.replace(/^\s*(Copy code|コピーする|Copy)\s*\n/, '');
        return '\n\n```' + lang + '\n' + txt + '\n```\n\n';
      }
      case 'h1': return '\n\n# ' + kids().trim() + '\n\n';
      case 'h2': return '\n\n## ' + kids().trim() + '\n\n';
      case 'h3': return '\n\n### ' + kids().trim() + '\n\n';
      case 'h4': return '\n\n#### ' + kids().trim() + '\n\n';
      case 'h5': return '\n\n##### ' + kids().trim() + '\n\n';
      case 'h6': return '\n\n###### ' + kids().trim() + '\n\n';
      case 'p': return '\n\n' + kids().trim() + '\n\n';
      case 'blockquote':
        return '\n\n' + kids().trim().split('\n').map(l => '> ' + l).join('\n') + '\n\n';
      case 'ul': case 'ol': {
        const isOl = tag === 'ol';
        const items = Array.from(node.children)
          .filter(c => c.tagName.toLowerCase() === 'li')
          .map((li, i) => {
            const marker = isOl ? (i + 1) + '.' : '-';
            const inner = Array.from(li.childNodes).map(htmlToMd).join('')
              .trim().replace(/\n/g, '\n  ');
            return marker + ' ' + inner;
          });
        return '\n\n' + items.join('\n') + '\n\n';
      }
      case 'a': {
        const href = node.getAttribute('href') || '';
        return '[' + kids().trim() + '](' + href + ')';
      }
      case 'img': {
        const src = node.getAttribute('src') || '';
        const alt = node.getAttribute('alt') || '';
        return '![' + alt + '](' + src + ')';
      }
      case 'table': {
        const rows = Array.from(node.querySelectorAll('tr'));
        if (!rows.length) return kids();
        const cells = rows.map(r => Array.from(r.children).map(c =>
          htmlToMd(c).replace(/\|/g, '\\|').replace(/\n+/g, ' ').trim()
        ));
        const cols = Math.max.apply(null, cells.map(c => c.length));
        const lines = cells.map(c =>
          '| ' + Array.from({ length: cols }, (_, i) => c[i] || '').join(' | ') + ' |'
        );
        const sep = '| ' + Array.from({ length: cols }, () => '---').join(' | ') + ' |';
        lines.splice(1, 0, sep);
        return '\n\n' + lines.join('\n') + '\n\n';
      }
      default: return kids();
    }
  }

  // -------- Extract conversation --------
  const msgs = document.querySelectorAll('[data-message-author-role]');
  if (!msgs.length) {
    alert('ChatGPT のメッセージが見つかりませんでした。\n会話画面 (chatgpt.com/c/...) で実行してください。');
    return;
  }

  const parts = [];
  msgs.forEach(m => {
    const role = m.getAttribute('data-message-author-role');
    const header = role === 'user' ? '## User'
                 : role === 'assistant' ? '## Assistant'
                 : '## ' + (role || 'message');
    const md = htmlToMd(m)
      .replace(/[ \t]+\n/g, '\n')      // strip trailing whitespace per line
      .replace(/\n{3,}/g, '\n\n')      // collapse runs of blank lines
      .trim();
    if (md) parts.push(header + '\n\n' + md);
  });

  if (!parts.length) {
    alert('メッセージ本文を抽出できませんでした。');
    return;
  }

  // -------- Title --------
  let title = document.title.replace(/^ChatGPT(\s*[-–—]\s*)?/, '').trim();
  if (!title || title === 'ChatGPT') {
    const active = document.querySelector('a[aria-current="page"], nav [aria-current="true"]');
    if (active) title = active.textContent.trim();
  }
  if (!title) title = 'Untitled ChatGPT conversation';

  const userTitle = prompt('保存するタイトル (=ファイル名トピック):', title);
  if (userTitle === null) return;
  title = (userTitle.trim() || title);

  const reason = (prompt('Why kept (なぜ重要か、1行で。空欄可):', '') || '').trim();

  // -------- Filename --------
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const date = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
  const topic = title
    .replace(/[\\\/:*?"<>|#%&{}$!'@+`=]/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  const filename = date + '_' + (topic || 'untitled');

  // -------- Frontmatter + body (matches _template.md exactly) --------
  const url = location.href;
  const yaml = [
    '---',
    'title: "' + title.replace(/"/g, '\\"') + '"',
    'source: chatgpt',
    'manual: true',
    'date: ' + date,
    'url: "' + url + '"',
    'tags:',
    '  - ai-chat',
    '  - manual',
    'aliases: []',
    'phi-source: false',
    '---',
    ''
  ].join('\n');

  const header = [
    '# ' + title,
    '',
    '> [!info] Manually saved from ChatGPT',
    '> - **Source**: ChatGPT (manual save, not quarterly export)',
    '> - **Share URL**: ' + url,
    '> - **Date**: ' + date,
    '> - **Why kept**: ' + (reason || '←後で使う見込み・理由を 1 行'),
    ''
  ].join('\n');

  const footer = [
    '',
    '## 自分のメモ',
    '',
    '- 重要ポイント:',
    '- 後で確認:',
    '- 関連 wiki: [[wiki/topics/]]',
    '',
    '## 関連',
    '',
    '- [[]]',
    ''
  ].join('\n');

  const body = yaml + header + '\n' + parts.join('\n\n') + '\n' + footer;

  // -------- Save --------
  const copy = (txt) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(txt);
    }
    const ta = document.createElement('textarea');
    ta.value = txt;
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } finally { document.body.removeChild(ta); }
    return Promise.resolve();
  };

  const file = FOLDER + '/' + filename;
  const fullUri = 'obsidian://new?vault=' + encodeURIComponent(VAULT)
                + '&file=' + encodeURIComponent(file)
                + '&content=' + encodeURIComponent(body);

  copy(body).then(() => {
    if (fullUri.length < URI_MAX) {
      window.location.href = fullUri;
    } else {
      const placeholder = '(本文はクリップボードに入っています。Cmd+V で貼り付けてください)';
      const stubUri = 'obsidian://new?vault=' + encodeURIComponent(VAULT)
                    + '&file=' + encodeURIComponent(file)
                    + '&content=' + encodeURIComponent(placeholder);
      window.location.href = stubUri;
      setTimeout(function () {
        alert('会話が長いため URL 経由で全文を送れませんでした。\n'
            + 'クリップボードに全文をコピー済みです。\n'
            + 'Obsidian で開いた空ノートに Cmd+V で貼り付けてください。');
      }, 200);
    }
  }, function () {
    alert('クリップボードへのコピーに失敗しました。');
  });
})();
