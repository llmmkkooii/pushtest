#!/usr/bin/env node
/* Build a bookmarklet from bookmarklet.src.js
 *
 * Usage: node build.js
 *
 * Strategy: state-aware comment stripping only (no whitespace gymnastics,
 * no keyword regex). Newlines survive into the URL as %0A, which the
 * browser parses fine. Bookmark URL fields accept ~32KB on modern browsers.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'bookmarklet.src.js');
const OUT = path.join(__dirname, 'bookmarklet.txt');

const src = fs.readFileSync(SRC, 'utf8');

// State-aware stripper: tracks string literals + regex literals so that
// `://` inside 'obsidian://new' is not mistaken for a // comment.
function strip(input) {
  let out = '';
  let i = 0;
  const n = input.length;
  // Track the previous non-whitespace char to disambiguate `/` (regex vs divide)
  let prevSig = '';
  const setPrev = (s) => {
    for (let k = s.length - 1; k >= 0; k--) {
      const c = s[k];
      if (c !== ' ' && c !== '\t' && c !== '\n' && c !== '\r') { prevSig = c; return; }
    }
  };
  while (i < n) {
    const c = input[i];
    const next = input[i + 1];

    // Line comment — only outside strings (we're outside here by construction)
    if (c === '/' && next === '/') {
      while (i < n && input[i] !== '\n') i++;
      continue;
    }
    // Block comment
    if (c === '/' && next === '*') {
      i += 2;
      while (i < n - 1 && !(input[i] === '*' && input[i + 1] === '/')) i++;
      i += 2;
      continue;
    }
    // Regex literal — `/` is a regex if it follows an operator/keyword position
    if (c === '/' && /[^A-Za-z0-9_)\]]/.test(prevSig || '=')) {
      // Heuristic: treat `/` here as regex literal opener
      out += c; i++;
      while (i < n) {
        const ch = input[i];
        out += ch;
        if (ch === '\\' && i + 1 < n) { out += input[i + 1]; i += 2; continue; }
        if (ch === '[') {
          // Skip char class; `/` inside `[...]` is literal
          i++;
          while (i < n && input[i] !== ']') {
            out += input[i];
            if (input[i] === '\\' && i + 1 < n) { out += input[i + 1]; i += 2; continue; }
            i++;
          }
          if (i < n) { out += input[i]; i++; }
          continue;
        }
        if (ch === '/') { i++; break; }
        i++;
      }
      // Consume regex flags
      while (i < n && /[gimsuy]/.test(input[i])) { out += input[i]; i++; }
      prevSig = '/';
      continue;
    }
    // String literal
    if (c === "'" || c === '"' || c === '`') {
      const quote = c;
      out += c; i++;
      while (i < n) {
        const ch = input[i];
        out += ch;
        if (ch === '\\' && i + 1 < n) { out += input[i + 1]; i += 2; continue; }
        if (ch === quote) { i++; break; }
        i++;
      }
      prevSig = quote;
      continue;
    }
    out += c;
    if (c !== ' ' && c !== '\t' && c !== '\n' && c !== '\r') prevSig = c;
    i++;
  }
  return out;
}

let code = strip(src).trim();

const bookmarklet = 'javascript:' + encodeURIComponent(code);

fs.writeFileSync(OUT, bookmarklet + '\n', 'utf8');

process.stderr.write(`[build] wrote ${OUT}\n`);
process.stderr.write(`[build] source after strip: ${code.length} chars\n`);
process.stderr.write(`[build] bookmarklet URL:    ${bookmarklet.length} chars\n`);
