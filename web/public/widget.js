/**
 * Synkora Agent Widget
 * Embeddable AI chat widget using Shadow DOM for full CSS isolation.
 * Usage: SynkoraWidget.init({ widgetId, apiKey, containerId, apiUrl })
 */
(function (global) {
  "use strict";

  if (global.SynkoraWidget) return;

  // Capture script origin at load time (document.currentScript is only available synchronously)
  var _scriptOrigin = (function () {
    try {
      var s = document.currentScript || (function () {
        var scripts = document.getElementsByTagName("script");
        return scripts[scripts.length - 1];
      }());
      return s && s.src ? new URL(s.src).origin : "";
    } catch (e) { return ""; }
  }());

  // ─── Helpers ─────────────────────────────────────────────────────────────────

  function uid() {
    return Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function esc(t) {
    return String(t || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function hexToRgb(hex) {
    hex = (hex || "").replace(/^#/, "");
    if (hex.length === 3) hex = hex.split("").map(function (c) { return c + c; }).join("");
    if (hex.length !== 6) return "255,68,79";
    var n = parseInt(hex, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255].join(",");
  }

  function darkenHex(hex, amount) {
    hex = (hex || "").replace(/^#/, "");
    if (hex.length === 3) hex = hex.split("").map(function (c) { return c + c; }).join("");
    if (hex.length !== 6) return "#c8102e";
    var n = parseInt(hex, 16);
    var r = Math.max(0, ((n >> 16) & 255) - amount);
    var g = Math.max(0, ((n >> 8) & 255) - amount);
    var b = Math.max(0, (n & 255) - amount);
    return "#" + [r, g, b].map(function (v) { return v.toString(16).padStart(2, "0"); }).join("");
  }

  function timeNow() {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // ─── Markdown Parser ─────────────────────────────────────────────────────────

  function inlineMd(raw) {
    if (!raw) return "";
    var ph = [];
    var s = raw;

    // Protect inline code first
    s = s.replace(/`([^`\n]+)`/g, function (_, c) {
      ph.push("<code>" + esc(c) + "</code>");
      return "\x00" + (ph.length - 1) + "\x00";
    });

    // Images
    s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function (_, alt, src) {
      if (!/^(https?:\/\/|\/|data:image\/)/.test(src)) return esc(alt || "");
      ph.push('<img src="' + esc(src) + '" alt="' + esc(alt) + '" class="snkr-img" loading="lazy">');
      return "\x00" + (ph.length - 1) + "\x00";
    });

    // Links
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, href) {
      if (!/^(https?:\/\/|mailto:|\/)/i.test(href)) return esc(label);
      ph.push('<a href="' + esc(href) + '" target="_blank" rel="noopener noreferrer">' + esc(label) + '</a>');
      return "\x00" + (ph.length - 1) + "\x00";
    });

    // Escape remaining text
    s = esc(s);

    // Bold
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/__(.+?)__/g, "<strong>$1</strong>");
    // Italic
    s = s.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    s = s.replace(/_([^_\n\s][^_\n]*)_/g, "<em>$1</em>");
    // Strikethrough
    s = s.replace(/~~(.+?)~~/g, "<del>$1</del>");

    // Restore placeholders
    s = s.replace(/\x00(\d+)\x00/g, function (_, i) { return ph[+i]; });
    return s;
  }

  function parseCells(line) {
    return line.split("|")
      .map(function (c) { return c.trim(); })
      .filter(function (c, i, a) {
        return !(i === 0 && c === "") && !(i === a.length - 1 && c === "");
      });
  }

  function mdParse(text, streaming) {
    if (!text) return "";

    // Close unclosed code fence during streaming for clean partial render
    var fences = (text.match(/^```/gm) || []).length;
    if (streaming && fences % 2 !== 0) text += "\n```";

    var lines = text.split("\n");
    var out = "";
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      // ── Fenced code block ──────────────────────────────────────────
      var fm = line.match(/^```(\w*)\s*$/);
      if (fm) {
        var lang = fm[1];
        var codeLines = [];
        i++;
        while (i < lines.length && !lines[i].match(/^```\s*$/)) {
          codeLines.push(lines[i]);
          i++;
        }
        i++; // skip closing ```
        out += '<div class="snkr-pre">' +
          '<div class="snkr-code-hdr">' +
            '<span class="snkr-lang-tag">' + (lang ? esc(lang) : "") + '</span>' +
            '<button class="snkr-copy-btn">Copy</button>' +
          '</div>' +
          '<pre><code>' + esc(codeLines.join("\n")) + '</code></pre>' +
          '</div>';
        continue;
      }

      // ── Table ──────────────────────────────────────────────────────
      if (line.includes("|") && i + 1 < lines.length && /^\|?[\s:\-|]+\|/.test(lines[i + 1])) {
        var headers = parseCells(line);
        i += 2; // skip header + separator
        var tHtml = '<div class="snkr-table-wrap"><table><thead><tr>';
        headers.forEach(function (h) { tHtml += "<th>" + inlineMd(h) + "</th>"; });
        tHtml += "</tr></thead><tbody>";
        while (i < lines.length && lines[i].includes("|")) {
          tHtml += "<tr>";
          parseCells(lines[i]).forEach(function (c) { tHtml += "<td>" + inlineMd(c) + "</td>"; });
          tHtml += "</tr>";
          i++;
        }
        out += tHtml + "</tbody></table></div>";
        continue;
      }

      // ── Heading ────────────────────────────────────────────────────
      var hm = line.match(/^(#{1,6})\s+(.+)$/);
      if (hm) {
        var lvl = hm[1].length;
        out += "<h" + lvl + ">" + inlineMd(hm[2]) + "</h" + lvl + ">";
        i++;
        continue;
      }

      // ── Blockquote ─────────────────────────────────────────────────
      if (/^>\s?/.test(line)) {
        var bqLines = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          bqLines.push(lines[i].replace(/^>\s?/, ""));
          i++;
        }
        out += "<blockquote>" + bqLines.map(inlineMd).join("<br>") + "</blockquote>";
        continue;
      }

      // ── Unordered list ─────────────────────────────────────────────
      if (/^[-*+]\s+/.test(line)) {
        out += "<ul>";
        while (i < lines.length && /^[-*+]\s+/.test(lines[i])) {
          out += "<li>" + inlineMd(lines[i].replace(/^[-*+]\s+/, "")) + "</li>";
          i++;
        }
        out += "</ul>";
        continue;
      }

      // ── Ordered list ───────────────────────────────────────────────
      if (/^\d+\.\s+/.test(line)) {
        out += "<ol>";
        while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
          out += "<li>" + inlineMd(lines[i].replace(/^\d+\.\s+/, "")) + "</li>";
          i++;
        }
        out += "</ol>";
        continue;
      }

      // ── Horizontal rule ────────────────────────────────────────────
      if (/^[-*_]{3,}\s*$/.test(line.trim())) {
        out += "<hr>";
        i++;
        continue;
      }

      // ── Blank line ─────────────────────────────────────────────────
      if (line.trim() === "") { i++; continue; }

      // ── Paragraph ──────────────────────────────────────────────────
      var pLines = [];
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        !lines[i].match(/^#{1,6}\s/) &&
        !lines[i].match(/^[-*+]\s+/) &&
        !lines[i].match(/^\d+\.\s+/) &&
        !lines[i].match(/^>\s?/) &&
        !lines[i].match(/^```/) &&
        !/^[-*_]{3,}\s*$/.test(lines[i].trim()) &&
        !lines[i].includes("|")
      ) {
        pLines.push(lines[i]);
        i++;
      }
      if (pLines.length) {
        out += "<p>" + pLines.map(inlineMd).join("<br>") + "</p>";
      }
    }

    return out;
  }

  // ─── Shadow DOM CSS ───────────────────────────────────────────────────────────

  var CSS = `
    @font-face { font-family: 'Inter'; font-style: normal; font-weight: 400; font-display: swap; src: url('__FONT_ORIGIN__/fonts/inter-400.woff2') format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family: 'Inter'; font-style: normal; font-weight: 500; font-display: swap; src: url('__FONT_ORIGIN__/fonts/inter-500.woff2') format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family: 'Inter'; font-style: normal; font-weight: 600; font-display: swap; src: url('__FONT_ORIGIN__/fonts/inter-600.woff2') format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family: 'Inter'; font-style: normal; font-weight: 700; font-display: swap; src: url('__FONT_ORIGIN__/fonts/inter-700.woff2') format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :host { all: initial; }

    /* ── Toggle FAB ──────────────────── */
    #snkr-toggle {
      position: fixed; bottom: 28px; right: 28px; z-index: 2147483647;
      width: 60px; height: 60px; border-radius: 50%; border: none;
      background: linear-gradient(135deg, var(--snkr-c, #ff444f) 0%, var(--snkr-cd, #c8102e) 100%);
      box-shadow: 0 4px 20px rgba(var(--snkr-rgb, 255,68,79), 0.45), 0 2px 8px rgba(0,0,0,0.2);
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none;
      transition: transform 0.2s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.2s ease;
    }
    #snkr-toggle:hover {
      transform: scale(1.1);
      box-shadow: 0 8px 28px rgba(var(--snkr-rgb, 255,68,79), 0.55), 0 4px 12px rgba(0,0,0,0.25);
    }
    #snkr-toggle:active { transform: scale(0.96); }
    #snkr-toggle svg { pointer-events: none; }
    #snkr-toggle::before {
      content: ''; position: absolute; inset: -4px; border-radius: 50%;
      border: 2px solid rgba(var(--snkr-rgb, 255,68,79), 0.4);
      animation: snkr-pulse 2.4s ease-out infinite;
    }
    @keyframes snkr-pulse {
      0%   { transform: scale(1);    opacity: 0.7; }
      70%  { transform: scale(1.35); opacity: 0; }
      100% { transform: scale(1.35); opacity: 0; }
    }

    /* ── Panel ───────────────────────── */
    #snkr-panel {
      position: fixed; bottom: 104px; right: 28px; z-index: 2147483646;
      width: 420px; height: 660px; background: #fff; border-radius: 20px;
      overflow: hidden; display: none; flex-direction: column;
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      font-size: 14px; line-height: 1.5; color: #111827;
      box-shadow: 0 0 0 1px rgba(0,0,0,0.05), 0 20px 60px rgba(0,0,0,0.18), 0 6px 20px rgba(0,0,0,0.08);
      transform-origin: bottom right;
      transition: width 0.25s ease, height 0.25s ease;
    }
    #snkr-panel.open {
      display: flex;
      animation: snkr-slidein 0.26s cubic-bezier(0.34,1.4,0.64,1) both;
    }
    #snkr-panel.snkr-expanded { width: 600px; height: 820px; }
    @keyframes snkr-slidein {
      from { opacity: 0; transform: scale(0.88) translateY(16px); }
      to   { opacity: 1; transform: scale(1)    translateY(0); }
    }

    /* ── Home Screen ─────────────────── */
    #snkr-home { display: flex; flex-direction: column; flex: 1; min-height: 0; }
    #snkr-home-hero {
      background: linear-gradient(160deg, var(--snkr-c, #ff444f) 0%, var(--snkr-cd, #c8102e) 100%);
      padding: 22px 20px 24px; position: relative; flex-shrink: 0;
    }
    #snkr-home-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
    #snkr-home-avatar {
      width: 48px; height: 48px; border-radius: 50%;
      background: rgba(255,255,255,0.25); border: 3px solid rgba(255,255,255,0.5);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; font-weight: 700; color: #fff; overflow: hidden; flex-shrink: 0;
    }
    #snkr-home-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
    #snkr-home-close {
      background: rgba(255,255,255,0.2); border: none; cursor: pointer; color: #fff;
      width: 30px; height: 30px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s; flex-shrink: 0;
    }
    #snkr-home-close:hover { background: rgba(255,255,255,0.35); }
    #snkr-home-greeting {
      font-size: 24px; font-weight: 800; color: #fff; line-height: 1.25;
      letter-spacing: -0.02em;
    }
    #snkr-home-greeting .snkr-greeting-sub {
      display: block; font-size: 20px; font-weight: 700; opacity: 0.88; margin-top: 2px;
    }
    #snkr-home-body {
      flex: 1; overflow-y: auto; padding: 16px 14px;
      background: #f3f4f6; display: flex; flex-direction: column; gap: 10px;
    }
    #snkr-home-body::-webkit-scrollbar { width: 4px; }
    #snkr-home-body::-webkit-scrollbar-track { background: transparent; }
    #snkr-home-body::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 4px; }
    #snkr-start-btn {
      width: 100%; padding: 16px 18px; background: #fff; border: 1px solid #e5e7eb;
      border-radius: 14px; cursor: pointer; outline: none;
      display: flex; align-items: center; justify-content: space-between;
      font-size: 14px; font-weight: 600; color: #111827; font-family: inherit;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      transition: box-shadow 0.15s, border-color 0.15s;
    }
    #snkr-start-btn:hover {
      border-color: var(--snkr-c, #ff444f);
      box-shadow: 0 3px 12px rgba(var(--snkr-rgb, 255,68,79), 0.15);
    }
    #snkr-start-btn-icon {
      width: 32px; height: 32px; border-radius: 50%;
      background: var(--snkr-c, #ff444f); display: flex;
      align-items: center; justify-content: center; flex-shrink: 0;
    }
    .snkr-suggestions-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    }
    .snkr-home-chip {
      display: flex; flex-direction: column; align-items: flex-start;
      padding: 12px 12px 14px; border-radius: 14px;
      background: #fff; border: 1px solid #e5e7eb;
      cursor: pointer; font-family: inherit; text-align: left; outline: none;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
      transition: box-shadow 0.15s, border-color 0.15s; gap: 6px;
    }
    .snkr-home-chip:hover { border-color: var(--snkr-c, #ff444f); box-shadow: 0 3px 10px rgba(var(--snkr-rgb,255,68,79),0.12); }
    .snkr-chip-icon {
      width: 34px; height: 34px; border-radius: 10px; background: #f3f4f6;
      display: flex; align-items: center; justify-content: center;
      font-size: 17px; flex-shrink: 0; margin-bottom: 2px;
    }
    .snkr-chip-title { font-size: 12.5px; font-weight: 700; color: #111827; line-height: 1.3; }
    .snkr-chip-desc { font-size: 11.5px; color: #6b7280; line-height: 1.35; }
    #snkr-home-branding {
      text-align: center; padding: 8px; font-size: 11px; color: #9ca3af;
      font-family: inherit; flex-shrink: 0; background: #f3f4f6;
    }
    #snkr-home-branding a { color: var(--snkr-c, #ff444f); text-decoration: none; font-weight: 500; }

    /* ── Chat Screen ─────────────────── */
    #snkr-chat { display: none; flex-direction: column; flex: 1; min-height: 0; }
    #snkr-chat.active { display: flex; }

    /* Chat Header */
    #snkr-header {
      padding: 0 12px; height: 64px;
      display: flex; align-items: center; gap: 8px;
      border-bottom: 1px solid #f0f0f0; flex-shrink: 0;
      background: #fff; position: relative;
    }
    #snkr-back {
      background: #f3f4f6; border: none; cursor: pointer; color: #374151;
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s; flex-shrink: 0;
    }
    #snkr-back:hover { background: #e5e7eb; }
    #snkr-avatar {
      width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
      background: rgba(var(--snkr-rgb, 255,68,79), 0.1);
      border: 2px solid rgba(var(--snkr-rgb, 255,68,79), 0.18);
      display: flex; align-items: center; justify-content: center;
      font-size: 15px; font-weight: 700; color: var(--snkr-c, #ff444f);
      overflow: hidden;
    }
    #snkr-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
    #snkr-hdr-info { flex: 1; min-width: 0; }
    #snkr-hdr-name {
      font-size: 14px; font-weight: 700; color: #111827;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    #snkr-hdr-status {
      font-size: 11px; color: #6b7280;
      display: flex; align-items: center; gap: 4px;
    }
    #snkr-hdr-status::before {
      content: ''; width: 7px; height: 7px; border-radius: 50%;
      background: #22c55e; display: inline-block; flex-shrink: 0;
    }
    #snkr-menu-wrap { position: relative; flex-shrink: 0; }
    #snkr-menu-btn {
      background: #f3f4f6; border: none; cursor: pointer; color: #374151;
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s;
    }
    #snkr-menu-btn:hover { background: #e5e7eb; }
    #snkr-menu-dropdown {
      display: none; position: absolute; top: 40px; right: 0; z-index: 10;
      background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.13); min-width: 210px; overflow: hidden;
    }
    #snkr-menu-dropdown.open { display: block; }
    .snkr-menu-item {
      display: flex; align-items: center; gap: 12px; padding: 13px 16px;
      cursor: pointer; font-size: 14px; color: #111827; font-family: inherit;
      background: transparent; border: none; width: 100%; text-align: left;
      outline: none; transition: background 0.1s;
    }
    .snkr-menu-item:hover { background: #f9fafb; }
    .snkr-menu-item:not(:last-child) { border-bottom: 1px solid #f3f4f6; }
    .snkr-menu-item svg { flex-shrink: 0; }
    #snkr-close {
      background: #f3f4f6; border: none; cursor: pointer; color: #374151;
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s; flex-shrink: 0;
    }
    #snkr-close:hover { background: #e5e7eb; }

    /* Messages */
    #snkr-messages {
      flex: 1; overflow-y: auto; padding: 20px 16px; display: flex;
      flex-direction: column; gap: 4px; background: #fff;
    }
    #snkr-messages::-webkit-scrollbar { width: 4px; }
    #snkr-messages::-webkit-scrollbar-track { background: transparent; }
    #snkr-messages::-webkit-scrollbar-thumb { background: #e5e7eb; border-radius: 4px; }

    .snkr-row { display: flex; flex-direction: column; gap: 4px; animation: snkr-in 0.18s ease both; margin-bottom: 10px; }
    @keyframes snkr-in { from { opacity:0; transform:translateY(5px); } to { opacity:1; transform:none; } }
    .snkr-row.user  { align-items: flex-end; }
    .snkr-row.agent { align-items: flex-start; }
    .snkr-row.error { align-items: flex-start; }

    .snkr-bubble {
      max-width: 80%; padding: 12px 16px; border-radius: 20px;
      font-size: 14px; line-height: 1.65; word-break: break-word;
    }
    .snkr-row.user .snkr-bubble {
      background: #1e293b; color: #fff; border-bottom-right-radius: 5px;
    }
    .snkr-row.agent .snkr-bubble {
      background: #f3f4f6; color: #111827; border-bottom-left-radius: 5px;
    }
    .snkr-row.error .snkr-bubble {
      background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; border-radius: 12px;
    }
    .snkr-ts {
      font-size: 11px; color: #9ca3af; padding: 0 4px;
    }

    /* ── Bubble Rich Content ─────────── */
    .snkr-bubble p { margin: 0 0 7px; }
    .snkr-bubble p:last-child { margin-bottom: 0; }
    .snkr-bubble strong { font-weight: 600; }
    .snkr-bubble em { font-style: italic; }
    .snkr-bubble del { text-decoration: line-through; opacity: 0.65; }
    .snkr-bubble h1, .snkr-bubble h2, .snkr-bubble h3,
    .snkr-bubble h4, .snkr-bubble h5, .snkr-bubble h6 {
      font-weight: 700; color: #111827; margin: 12px 0 5px; line-height: 1.3;
    }
    .snkr-bubble h1:first-child, .snkr-bubble h2:first-child, .snkr-bubble h3:first-child { margin-top: 0; }
    .snkr-bubble h1 { font-size: 17px; }
    .snkr-bubble h2 { font-size: 15px; }
    .snkr-bubble h3 { font-size: 14px; }
    .snkr-bubble h4, .snkr-bubble h5, .snkr-bubble h6 { font-size: 13px; }
    .snkr-bubble ul, .snkr-bubble ol { margin: 4px 0 7px 18px; padding: 0; }
    .snkr-bubble li { margin: 3px 0; }
    .snkr-bubble blockquote {
      border-left: 3px solid var(--snkr-c, #ff444f);
      padding: 6px 12px; margin: 8px 0; color: #6b7280;
      font-style: italic; background: #f9fafb; border-radius: 0 6px 6px 0;
    }
    .snkr-bubble hr { border: none; border-top: 1px solid #e5e7eb; margin: 10px 0; }
    .snkr-bubble code {
      background: rgba(0,0,0,0.07); padding: 2px 5px; border-radius: 4px;
      font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px;
    }
    .snkr-row.user .snkr-bubble code { background: rgba(255,255,255,0.18); }
    .snkr-pre { margin: 8px 0; border-radius: 10px; overflow: hidden; background: #0f172a; }
    .snkr-code-hdr {
      background: #1e293b; padding: 7px 12px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .snkr-lang-tag {
      font-size: 11px; color: #64748b;
      font-family: 'SF Mono', 'Fira Code', monospace;
      text-transform: uppercase; letter-spacing: 0.06em;
    }
    .snkr-copy-btn {
      background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
      color: #94a3b8; border-radius: 5px; padding: 2px 9px;
      font-size: 11px; cursor: pointer; font-family: inherit;
      transition: background 0.15s, color 0.15s;
    }
    .snkr-copy-btn:hover { background: rgba(255,255,255,0.18); color: #e2e8f0; }
    .snkr-bubble pre {
      background: #0f172a; color: #e2e8f0; padding: 12px 14px;
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 12px; overflow-x: auto; white-space: pre; line-height: 1.6;
    }
    .snkr-bubble pre code { background: none; padding: 0; color: inherit; font-size: inherit; }
    .snkr-table-wrap { overflow-x: auto; margin: 8px 0; border-radius: 8px; border: 1px solid #e5e7eb; }
    .snkr-bubble table { border-collapse: collapse; width: 100%; font-size: 13px; }
    .snkr-bubble th, .snkr-bubble td { border-bottom: 1px solid #e5e7eb; padding: 7px 11px; text-align: left; white-space: nowrap; }
    .snkr-bubble th { background: #f9fafb; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb; }
    .snkr-bubble tr:last-child td { border-bottom: none; }
    .snkr-bubble tr:nth-child(even) td { background: #f9fafb; }
    .snkr-img { max-width: 100%; border-radius: 8px; margin: 6px 0; display: block; cursor: zoom-in; border: 1px solid #e5e7eb; }
    .snkr-bubble a { color: var(--snkr-c, #ff444f); text-decoration: none; }
    .snkr-bubble a:hover { text-decoration: underline; }

    /* ── Streaming cursor ────────────── */
    .snkr-bubble.streaming::after {
      content: '▋'; display: inline;
      animation: snkr-blink 0.7s step-end infinite;
      color: var(--snkr-c, #ff444f); font-size: 0.85em; margin-left: 1px;
    }
    @keyframes snkr-blink { 0%,100%{opacity:1} 50%{opacity:0} }

    /* ── Typing indicator ────────────── */
    #snkr-typing {
      display: flex; align-items: center; gap: 4px; padding: 13px 16px;
      background: #f3f4f6; border-radius: 20px; border-bottom-left-radius: 5px;
      width: fit-content;
    }
    #snkr-typing span {
      width: 7px; height: 7px; border-radius: 50%; background: #9ca3af; display: inline-block;
    }
    #snkr-typing span:nth-child(1) { animation: snkr-dot 1.2s -0.32s infinite ease-in-out; }
    #snkr-typing span:nth-child(2) { animation: snkr-dot 1.2s -0.16s infinite ease-in-out; }
    #snkr-typing span:nth-child(3) { animation: snkr-dot 1.2s 0s    infinite ease-in-out; }
    @keyframes snkr-dot {
      0%,80%,100% { transform: scale(0.6); background: #9ca3af; }
      40%         { transform: scale(1);   background: var(--snkr-c, #ff444f); }
    }

    /* ── Footer ──────────────────────── */
    #snkr-footer {
      padding: 10px 14px 14px; background: #fff;
      border-top: 1px solid #f0f0f0; flex-shrink: 0;
    }
    #snkr-input-box {
      border: 1.5px solid #e5e7eb; border-radius: 18px; background: #fff;
      transition: border-color 0.15s, box-shadow 0.15s; overflow: hidden;
    }
    #snkr-input-box:focus-within {
      border-color: var(--snkr-c, #ff444f);
      box-shadow: 0 0 0 3px rgba(var(--snkr-rgb,255,68,79),0.1);
    }
    #snkr-input {
      display: block; width: 100%; border: none; outline: none; background: transparent;
      font-family: 'Inter', system-ui, sans-serif; font-size: 14px; color: #111827;
      resize: none; max-height: 120px; min-height: 22px; line-height: 1.5;
      padding: 14px 16px 6px;
    }
    #snkr-input::placeholder { color: #9ca3af; }
    #snkr-input:disabled { opacity: 0.6; cursor: not-allowed; }
    #snkr-footer-row {
      display: flex; align-items: center; justify-content: flex-end;
      padding: 4px 8px 6px; gap: 8px;
    }
    #snkr-send {
      width: 34px; height: 34px; border-radius: 50%; border: none;
      background: #d1d5db; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      padding: 0; flex-shrink: 0; outline: none;
      transition: background 0.15s, transform 0.15s, box-shadow 0.15s;
    }
    #snkr-send.snkr-send-active {
      background: var(--snkr-c, #ff444f);
      box-shadow: 0 2px 10px rgba(var(--snkr-rgb,255,68,79),0.35);
    }
    #snkr-send.snkr-send-active:hover { transform: scale(1.08); }
    #snkr-send:disabled { opacity: 0.4; cursor: not-allowed; }

    /* ── Branding ────────────────────── */
    #snkr-branding {
      text-align: center; padding: 6px 0 2px; font-size: 11px; color: #9ca3af;
      font-family: 'Inter', system-ui, sans-serif; flex-shrink: 0;
    }
    #snkr-branding a { color: var(--snkr-c, #ff444f); text-decoration: none; font-weight: 500; }
    #snkr-branding a:hover { text-decoration: underline; }

    /* ── Loading skeleton ────────────── */
    #snkr-loading {
      flex: 1; display: flex; align-items: center; justify-content: center;
      background: #fff; flex-direction: column; gap: 12px;
    }
    .snkr-sk { background: #e5e7eb; border-radius: 8px; animation: snkr-sk 1.4s ease-in-out infinite; }
    @keyframes snkr-sk { 0%,100%{opacity:0.5} 50%{opacity:1} }

    /* ── Notification badge ──────────── */
    #snkr-badge {
      position: absolute; top: -6px; right: -6px; width: 20px; height: 20px;
      border-radius: 50%; background: #ef4444; color: #fff; font-size: 11px; font-weight: 700;
      display: none; align-items: center; justify-content: center;
      border: 2px solid #fff; pointer-events: none;
      animation: snkr-badge-in 0.25s cubic-bezier(0.34,1.56,0.64,1) both;
    }
    #snkr-badge.show { display: flex; }
    @keyframes snkr-badge-in { from { transform: scale(0); } to { transform: scale(1); } }

    /* ── Sherlock investigation panel ── */
    .snkr-sherlock { margin-bottom: 10px; display: flex; flex-direction: column; gap: 3px; align-self: flex-start; max-width: 92%; }
    .snkr-sherlock-hdr {
      font-size: 10px; font-weight: 600; color: #9ca3af; letter-spacing: 0.06em;
      text-transform: uppercase; padding: 0 4px; margin-bottom: 1px;
    }
    .snkr-sherlock-step {
      display: flex; align-items: center; gap: 8px; padding: 6px 11px; border-radius: 10px;
      background: #eef2ff; border: 1px solid #c7d2fe; font-size: 12px; color: #4338ca;
      animation: snkr-in 0.2s ease both;
    }
    .snkr-sherlock-step.done { background: #f0fdf4; border-color: #bbf7d0; color: #166534; }
    .snkr-sherlock-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: #6366f1; animation: snkr-sdot 1s ease-in-out infinite; }
    .snkr-sherlock-step.done .snkr-sherlock-dot { background: #22c55e; animation: none; }
    .snkr-sherlock-ms { margin-left: auto; font-size: 10px; color: #9ca3af; flex-shrink: 0; padding-left: 8px; }
    @keyframes snkr-sdot { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.35; transform:scale(0.7); } }

    /* ── Pioneer notification ────────── */
    .snkr-pioneer {
      padding: 12px 14px; border-radius: 12px; margin-bottom: 4px;
      background: linear-gradient(135deg, #fef9c3 0%, #fef08a 100%);
      border: 1px solid #fde047; font-size: 12px; color: #713f12; line-height: 1.5;
      display: flex; align-items: flex-start; gap: 10px;
      animation: snkr-in 0.3s ease both;
    }
    .snkr-pioneer-icon { font-size: 18px; flex-shrink: 0; }
    .snkr-pioneer-body { flex: 1; }
    .snkr-pioneer-body strong { display: block; font-weight: 700; font-size: 12.5px; margin-bottom: 2px; }
    .snkr-pioneer-close {
      background: none; border: none; cursor: pointer; padding: 0; outline: none;
      font-size: 13px; color: #92400e; opacity: 0.6; flex-shrink: 0; line-height: 1;
    }
    .snkr-pioneer-close:hover { opacity: 1; }

    /* ── Ambient probe bubble ────────── */
    #snkr-probe {
      position: fixed; bottom: 108px; right: 28px; z-index: 2147483645;
      max-width: 240px; padding: 11px 15px 11px 14px;
      background: #1e293b; color: #f8fafc; border-radius: 16px 16px 4px 16px;
      font-size: 13px; font-weight: 500; line-height: 1.45;
      box-shadow: 0 8px 28px rgba(0,0,0,0.22); cursor: pointer; font-family: inherit;
      animation: snkr-slidein 0.3s cubic-bezier(0.34,1.4,0.64,1) both; display: none;
    }
    #snkr-probe.show { display: block; }
    #snkr-probe::after {
      content: ''; position: absolute; bottom: -6px; right: 20px;
      border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 6px solid #1e293b;
    }

    /* ── Mobile ──────────────────────── */
    @media (max-width: 480px) {
      #snkr-panel { width: calc(100vw - 16px); height: calc(100dvh - 100px); right: 8px; bottom: 88px; border-radius: 16px; }
      #snkr-panel.snkr-expanded { width: calc(100vw - 16px); height: calc(100dvh - 100px); }
      #snkr-toggle { right: 16px; bottom: 20px; }
      #snkr-probe { right: 8px; max-width: calc(100vw - 88px); }
    }
  `;

  // ─── Icons ────────────────────────────────────────────────────────────────────

  var I = {
    chat:     '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    x:        '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    xsm:      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    send:     '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><line x1="22" y1="2" x2="11" y2="13" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/><polygon points="22 2 15 22 11 13 2 9 22 2" fill="#fff"/></svg>',
    back:     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
    dots:     '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>',
    expand:   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>',
    compress: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 3v5H3M21 8h-5V3M3 16h5v5M16 21v-5h5"/></svg>',
    download: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    arrow:    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>',
    chevron:  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
    check:    '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  };

  // ─── Widget ───────────────────────────────────────────────────────────────────

  function Widget(cfg) {
    this.widgetId       = cfg.widgetId;
    this.apiKey         = cfg.apiKey;
    this.apiUrl         = (cfg.apiUrl || "http://localhost:5001/api/v1").replace(/\/$/, "");
    this._user          = cfg.user || null;
    this._userHash      = cfg.userHash || null;
    // Stable session: identified users get a deterministic ID so history survives page reload
    this.sessionId      = (this._user && this._user.id) ? "eu_" + this._user.id : uid();
    this.conversationId = null;
    this.streaming      = false;
    this._isOpen        = false;
    this._agentBubble   = null;
    this._agentText     = "";
    this._typingEl      = null;
    // ── Feature state ─────────────────
    this._sherlockEl    = null;       // Feature 1: Sherlock panel element
    this._sherlockSteps = {};         // Feature 1: {toolName: stepEl}
    this._toolsUsed     = 0;          // Feature 1+3: tools called this turn
    this._backgrounded  = false;      // Feature 5: tab was hidden while streaming
    this._ambientFired  = {};         // Feature 4: which probes have fired
    this._pioneerKey    = "snkr_pioneer_" + (cfg.widgetId || "default");
    this._visHandler    = null;       // Feature 5: stored visibility handler
    this._cfg = {
      agentName: "AI Assistant",
      agentAvatar: "",
      agentDescription: "",
      welcomeMessage: "",
      placeholder: "Type a message…",
      primaryColor: "#ff444f",
      suggestions: [],
      brandingText: cfg.brandingText !== undefined ? cfg.brandingText : "Powered by AI",
      brandingUrl:  cfg.brandingUrl  || "",
    };

    this._mount();
    this._loadConfig();
  }

  Widget.prototype._mount = function () {
    var self = this;
    var color = "#ff444f";

    var host = document.createElement("div");
    host.id = "snkr-" + this.widgetId;
    host.style.setProperty("--snkr-c",   color);
    host.style.setProperty("--snkr-cd",  darkenHex(color, 50));
    host.style.setProperty("--snkr-rgb", hexToRgb(color));
    document.body.appendChild(host);
    this._host = host;

    var shadow = host.attachShadow({ mode: "open" });
    var styleEl = document.createElement("style");
    styleEl.textContent = CSS.replace(/__FONT_ORIGIN__/g, _scriptOrigin || "");
    shadow.appendChild(styleEl);

    // Toggle FAB
    var toggle = document.createElement("button");
    toggle.id = "snkr-toggle";
    toggle.setAttribute("aria-label", "Open chat");
    toggle.innerHTML = I.chat;
    // Feature 5: notification badge
    var badge = document.createElement("span");
    badge.id = "snkr-badge";
    badge.textContent = "1";
    toggle.appendChild(badge);
    this._badge = badge;
    shadow.appendChild(toggle);

    // Feature 4: ambient probe bubble (hidden by default)
    var probe = document.createElement("div");
    probe.id = "snkr-probe";
    probe.setAttribute("role", "button");
    probe.setAttribute("tabindex", "0");
    probe.addEventListener("click", function () { self.open(); probe.classList.remove("show"); });
    probe.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { self.open(); probe.classList.remove("show"); } });
    shadow.appendChild(probe);
    this._probe = probe;

    // Panel
    var panel = document.createElement("div");
    panel.id = "snkr-panel";
    panel.setAttribute("role", "dialog");

    // ── HOME SCREEN ─────────────────────────────────────────────────────
    var home = document.createElement("div");
    home.id = "snkr-home";

    var hero = document.createElement("div");
    hero.id = "snkr-home-hero";
    hero.innerHTML =
      '<div id="snkr-home-top">' +
        '<div id="snkr-home-avatar">🤖</div>' +
        '<button id="snkr-home-close" aria-label="Close">' + I.xsm + '</button>' +
      '</div>' +
      '<div id="snkr-home-greeting">' +
        'Hi there 👋' +
        '<span class="snkr-greeting-sub">How can we help?</span>' +
      '</div>';
    home.appendChild(hero);

    var homeBody = document.createElement("div");
    homeBody.id = "snkr-home-body";
    // "Start a conversation" button
    var startBtn = document.createElement("button");
    startBtn.id = "snkr-start-btn";
    startBtn.innerHTML =
      '<span>Send us a message</span>' +
      '<span id="snkr-start-btn-icon">' + I.arrow + '</span>';
    homeBody.appendChild(startBtn);

    var homeBranding = document.createElement("div");
    homeBranding.id = "snkr-home-branding";
    if (this._cfg.brandingText !== false) {
      var hbText = this._cfg.brandingText || "Powered by AI";
      var hbUrl  = this._cfg.brandingUrl;
      homeBranding.innerHTML = hbUrl
        ? hbText.replace(/^(Powered by )(.+)$/, '$1<a href="' + esc(hbUrl) + '" target="_blank" rel="noopener">$2</a>')
        : esc(hbText);
    }

    home.appendChild(homeBody);
    home.appendChild(homeBranding);
    panel.appendChild(home);

    // ── CHAT SCREEN ─────────────────────────────────────────────────────
    var chat = document.createElement("div");
    chat.id = "snkr-chat";

    // Chat header
    var header = document.createElement("div");
    header.id = "snkr-header";
    header.innerHTML =
      '<button id="snkr-back" aria-label="Back">' + I.back + '</button>' +
      '<div id="snkr-avatar">AI</div>' +
      '<div id="snkr-hdr-info">' +
        '<div id="snkr-hdr-name">AI Assistant</div>' +
        '<div id="snkr-hdr-status">Online</div>' +
      '</div>' +
      '<div id="snkr-menu-wrap">' +
        '<button id="snkr-menu-btn" aria-label="More options">' + I.dots + '</button>' +
        '<div id="snkr-menu-dropdown">' +
          '<button class="snkr-menu-item" id="snkr-expand-btn">' +
            I.expand + '<span>Expand window</span>' +
          '</button>' +
          '<button class="snkr-menu-item" id="snkr-download-btn">' +
            I.download + '<span>Download transcript</span>' +
          '</button>' +
        '</div>' +
      '</div>' +
      '<button id="snkr-close" aria-label="Close">' + I.xsm + '</button>';

    // Body (messages)
    var body = document.createElement("div");
    body.id = "snkr-body";
    body.style.cssText = "flex:1;display:flex;flex-direction:column;overflow:hidden;";

    var loading = document.createElement("div");
    loading.id = "snkr-loading";
    loading.innerHTML =
      '<div class="snkr-sk" style="width:120px;height:12px;"></div>' +
      '<div class="snkr-sk" style="width:80px;height:10px;margin-top:8px;"></div>';
    body.appendChild(loading);

    var messages = document.createElement("div");
    messages.id = "snkr-messages";
    messages.style.display = "none";
    body.appendChild(messages);

    // Footer with new design
    var footer = document.createElement("div");
    footer.id = "snkr-footer";
    var inputBox = document.createElement("div");
    inputBox.id = "snkr-input-box";
    var input = document.createElement("textarea");
    input.id = "snkr-input";
    input.rows = 1;
    input.placeholder = "Message…";
    input.setAttribute("aria-label", "Message");
    var footerRow = document.createElement("div");
    footerRow.id = "snkr-footer-row";
    var sendBtn = document.createElement("button");
    sendBtn.id = "snkr-send";
    sendBtn.setAttribute("aria-label", "Send");
    sendBtn.innerHTML = I.send;
    footerRow.appendChild(sendBtn);
    inputBox.appendChild(input);
    inputBox.appendChild(footerRow);
    footer.appendChild(inputBox);

    var branding = document.createElement("div");
    branding.id = "snkr-branding";
    if (this._cfg.brandingText !== false) {
      var bText = this._cfg.brandingText || "Powered by AI";
      var bUrl  = this._cfg.brandingUrl;
      branding.innerHTML = bUrl
        ? bText.replace(/^(Powered by )(.+)$/, '$1<a href="' + esc(bUrl) + '" target="_blank" rel="noopener">$2</a>')
        : esc(bText);
    }

    chat.appendChild(header);
    chat.appendChild(body);
    chat.appendChild(footer);
    chat.appendChild(branding);
    panel.appendChild(chat);

    shadow.appendChild(panel);

    // Save refs
    this._shadow   = shadow;
    this._toggle   = toggle;
    this._panel    = panel;
    this._home     = home;
    this._homeBody = homeBody;
    this._chat     = chat;
    this._body     = body;
    this._loading  = loading;
    this._messages = messages;
    this._input    = input;
    this._sendBtn  = sendBtn;
    this._expanded = false;

    // Code copy + image zoom (delegation)
    messages.addEventListener("click", function (e) {
      if (e.target.classList.contains("snkr-copy-btn")) {
        var btn = e.target;
        var pre = btn.closest(".snkr-pre");
        var code = pre && pre.querySelector("code");
        if (code && navigator.clipboard) {
          navigator.clipboard.writeText(code.innerText).then(function () {
            btn.textContent = "Copied!";
            setTimeout(function () { btn.textContent = "Copy"; }, 1500);
          }).catch(function () {
            btn.textContent = "Failed";
            setTimeout(function () { btn.textContent = "Copy"; }, 1500);
          });
        }
      }
      if (e.target.classList.contains("snkr-img")) {
        window.open(e.target.src, "_blank");
      }
    });

    // Toggle FAB
    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      self._isOpen ? self.close() : self.open();
    });

    // Home: close
    shadow.getElementById("snkr-home-close").addEventListener("click", function (e) {
      e.stopPropagation(); self.close();
    });
    // Home: start chat
    startBtn.addEventListener("click", function (e) {
      e.stopPropagation(); self._showChat();
    });

    // Chat: back
    shadow.getElementById("snkr-back").addEventListener("click", function (e) {
      e.stopPropagation(); self._showHome();
    });
    // Chat: close
    shadow.getElementById("snkr-close").addEventListener("click", function (e) {
      e.stopPropagation(); self.close();
    });

    // Chat: ... menu toggle
    shadow.getElementById("snkr-menu-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      shadow.getElementById("snkr-menu-dropdown").classList.toggle("open");
    });
    // Menu: expand
    shadow.getElementById("snkr-expand-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      self._toggleExpand();
      shadow.getElementById("snkr-menu-dropdown").classList.remove("open");
    });
    // Menu: download
    shadow.getElementById("snkr-download-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      self._downloadTranscript();
      shadow.getElementById("snkr-menu-dropdown").classList.remove("open");
    });

    // Send
    sendBtn.addEventListener("click", function (e) { e.stopPropagation(); self._send(); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); self._send(); }
    });
    input.addEventListener("input", function () {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 120) + "px";
      sendBtn.classList.toggle("snkr-send-active", input.value.trim().length > 0);
    });

    // Close panel on outside click, also close dropdown
    document.addEventListener("click", function (e) {
      if (self._isOpen && !panel.contains(e.target) && e.target !== host) {
        self.close();
      } else {
        var dd = shadow.getElementById("snkr-menu-dropdown");
        if (dd && !shadow.getElementById("snkr-menu-wrap").contains(e.target)) {
          dd.classList.remove("open");
        }
      }
    });
  };

  Widget.prototype._showHome = function () {
    this._home.style.display = "flex";
    this._chat.classList.remove("active");
  };

  Widget.prototype._showChat = function () {
    this._home.style.display = "none";
    this._chat.classList.add("active");
    this._input.focus();
  };

  Widget.prototype._toggleExpand = function () {
    this._expanded = !this._expanded;
    this._panel.classList.toggle("snkr-expanded", this._expanded);
    var expandBtn = this._shadow.getElementById("snkr-expand-btn");
    if (expandBtn) {
      expandBtn.innerHTML = (this._expanded ? I.compress : I.expand) + '<span>' + (this._expanded ? 'Collapse window' : 'Expand window') + '</span>';
    }
  };

  Widget.prototype._downloadTranscript = function () {
    var cfg = this._cfg;
    var rows = this._messages.querySelectorAll(".snkr-row");
    var lines = ["Conversation with " + cfg.agentName, new Date().toLocaleString(), "─".repeat(40), ""];
    rows.forEach(function (row) {
      var isUser = row.classList.contains("user");
      var bubble = row.querySelector(".snkr-bubble");
      var ts = row.querySelector(".snkr-ts");
      if (!bubble) return;
      var speaker = isUser ? "You" : cfg.agentName;
      var time = ts ? ts.textContent : "";
      lines.push("[" + speaker + (time ? " · " + time : "") + "]");
      lines.push(bubble.innerText || bubble.textContent || "");
      lines.push("");
    });
    var blob = new Blob([lines.join("\n")], { type: "text/plain" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "chat-transcript-" + new Date().toISOString().slice(0, 10) + ".txt";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); URL.revokeObjectURL(url); }, 1000);
  };

  // ── Load config ───────────────────────────────────────────────────────────────

  // ── Feature 1: Sherlock — animated investigation steps ───────────────────────

  Widget.prototype._sherlockStep = function (toolName, status, description, durationMs) {
    // Only show during active streaming
    if (!this.streaming) return;

    if (status === "started") {
      // Create the sherlock container on first tool call
      if (!this._sherlockEl) {
        var panel = document.createElement("div");
        panel.className = "snkr-sherlock";
        var hdr = document.createElement("div");
        hdr.className = "snkr-sherlock-hdr";
        hdr.textContent = "Investigating...";
        panel.appendChild(hdr);
        // Insert before typing indicator row, or at end of messages
        // _typingEl is already the .snkr-row wrapper returned by _typing()
        if (this._typingEl && this._typingEl.parentNode === this._messages) {
          this._messages.insertBefore(panel, this._typingEl);
        } else {
          this._messages.appendChild(panel);
        }
        this._sherlockEl    = panel;
        this._sherlockSteps = {};
      }
      var step = document.createElement("div");
      step.className = "snkr-sherlock-step";
      var dot = document.createElement("span");
      dot.className = "snkr-sherlock-dot";
      var label = document.createElement("span");
      label.textContent = description || ("Using " + toolName.replace(/_/g, " ") + "…");
      step.appendChild(dot);
      step.appendChild(label);
      this._sherlockEl.appendChild(step);
      this._sherlockSteps[toolName] = step;

    } else if (status === "completed" || status === "error") {
      var existing = this._sherlockSteps[toolName];
      if (existing) {
        existing.classList.add("done");
        var dotEl = existing.querySelector(".snkr-sherlock-dot");
        if (dotEl) dotEl.style.animation = "none";
        var spanEl = existing.querySelector("span:last-child");
        if (spanEl) spanEl.innerHTML = I.check + "&nbsp;" + esc(spanEl.textContent);
        if (durationMs) {
          var ms = document.createElement("span");
          ms.className = "snkr-sherlock-ms";
          ms.textContent = durationMs + "ms";
          existing.appendChild(ms);
        }
      }
    }
    this._scroll();
  };

  // ── Feature 4: Ambient page intelligence ──────────────────────────────────────

  Widget.prototype._setupAmbient = function () {
    var self = this;
    var cfg  = this._cfg;
    // Don't fire if widget is already open or ambient is explicitly disabled
    if (this._isOpen) return;

    // Trigger 1: time on page (60s)
    if (!this._ambientFired.time) {
      setTimeout(function () {
        if (!self._isOpen && !self._ambientFired.time) {
          self._ambientFired.time = true;
          self._probeUser("Need help with anything? I'm here to assist.");
        }
      }, 60000);
    }

    // Trigger 2: scroll depth (75% of page)
    if (!this._ambientFired.scroll) {
      var onScroll = function () {
        var pct = (window.scrollY + window.innerHeight) / document.documentElement.scrollHeight;
        if (pct >= 0.75 && !self._isOpen && !self._ambientFired.scroll) {
          self._ambientFired.scroll = true;
          window.removeEventListener("scroll", onScroll);
          self._probeUser("Looks like you've been exploring — can I answer any questions?");
        }
      };
      window.addEventListener("scroll", onScroll, { passive: true });
    }

    // Trigger 3: form abandonment (filled an input, then left without submitting)
    if (!this._ambientFired.form) {
      var focusedInput = null;
      var onFocusIn = function (e) {
        if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") && !e.target.closest("#snkr-" + self.widgetId)) {
          focusedInput = e.target;
        }
      };
      var onFocusOut = function (e) {
        if (focusedInput && e.target === focusedInput && focusedInput.value && !self._ambientFired.form) {
          // Give a 3s grace period — if they submit, no probe
          setTimeout(function () {
            if (!self._isOpen && !self._ambientFired.form && focusedInput && focusedInput.value) {
              self._ambientFired.form = true;
              self._probeUser("Stuck on the form? I can help you fill it out.");
              document.removeEventListener("focusin", onFocusIn);
              document.removeEventListener("focusout", onFocusOut);
            }
          }, 3000);
        }
      };
      document.addEventListener("focusin", onFocusIn);
      document.addEventListener("focusout", onFocusOut);
    }
  };

  Widget.prototype._probeUser = function (msg) {
    if (this._isOpen || !this._probe) return;
    this._probe.textContent = msg;
    this._probe.classList.add("show");
    // Auto-hide after 8s
    var self = this;
    setTimeout(function () { self._probe.classList.remove("show"); }, 8000);
  };

  // ── Feature 3: Knowledge Pioneer ─────────────────────────────────────────────

  Widget.prototype._checkPioneer = function () {
    try {
      var raw = localStorage.getItem(this._pioneerKey);
      if (!raw) return;
      var data = JSON.parse(raw);
      // Only show if stored within last 7 days and not already dismissed
      var age = Date.now() - (data.ts || 0);
      if (age > 7 * 24 * 60 * 60 * 1000) { localStorage.removeItem(this._pioneerKey); return; }

      // Show pioneer banner in home body
      if (this._shadow.getElementById("snkr-pioneer-banner")) return; // already shown
      var self = this;
      var banner = document.createElement("div");
      banner.id = "snkr-pioneer-banner";
      banner.className = "snkr-pioneer";
      banner.innerHTML =
        '<span class="snkr-pioneer-icon">🔭</span>' +
        '<div class="snkr-pioneer-body">' +
          '<strong>You sparked an investigation!</strong>' +
          'Your last question was complex enough that the AI used ' + data.toolsUsed + ' tool' + (data.toolsUsed !== 1 ? 's' : '') + ' to answer it. ' +
          'It may already be helping others.' +
        '</div>' +
        '<button class="snkr-pioneer-close" aria-label="Dismiss">&times;</button>';
      banner.querySelector(".snkr-pioneer-close").addEventListener("click", function (e) {
        e.stopPropagation();
        banner.parentNode && banner.parentNode.removeChild(banner);
        try { localStorage.removeItem(self._pioneerKey); } catch (_) {}
      });
      // Prepend to home body
      var homeBody = this._shadow.getElementById("snkr-home-body");
      if (homeBody && homeBody.firstChild) {
        homeBody.insertBefore(banner, homeBody.firstChild);
      } else if (homeBody) {
        homeBody.appendChild(banner);
      }
    } catch (_) {}
  };

  Widget.prototype._loadConfig = function () {
    var self = this;
    fetch(this.apiUrl + "/widgets/config", {
      headers: { "X-Widget-API-Key": this.apiKey },
    })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data) { self._applyConfig({}); return; }
        self._applyConfig({
          agentName:        data.agent_name || "",
          agentAvatar:      data.agent_avatar || "",
          agentDescription: data.agent_description || "",
          welcomeMessage:   (data.theme && data.theme.welcome_message) || "",
          placeholder:      (data.theme && data.theme.placeholder) || "",
          primaryColor:     (data.theme && data.theme.primary_color) || "",
          suggestions:      data.suggestion_prompts || [],
        });
      })
      .catch(function () { self._applyConfig({}); });
  };

  Widget.prototype._applyConfig = function (c) {
    var self = this;
    var cfg = this._cfg;
    cfg.agentName        = c.agentName        || "AI Assistant";
    cfg.agentAvatar      = c.agentAvatar      || "";
    cfg.agentDescription = c.agentDescription || "";
    cfg.welcomeMessage   = c.welcomeMessage   || ("Hi there 👋\nHow can we help?");
    cfg.placeholder      = c.placeholder      || "Message…";
    cfg.primaryColor     = c.primaryColor     || "#ff444f";
    cfg.suggestions      = Array.isArray(c.suggestions) ? c.suggestions : [];

    var color = cfg.primaryColor;
    this._host.style.setProperty("--snkr-c",   color);
    this._host.style.setProperty("--snkr-cd",  darkenHex(color, 50));
    this._host.style.setProperty("--snkr-rgb", hexToRgb(color));

    // Update chat header avatar + name
    var nameEl   = this._shadow.getElementById("snkr-hdr-name");
    var avatarEl = this._shadow.getElementById("snkr-avatar");
    if (nameEl) nameEl.textContent = cfg.agentName;
    if (avatarEl) {
      avatarEl.innerHTML = cfg.agentAvatar
        ? '<img src="' + esc(cfg.agentAvatar) + '" alt="' + esc(cfg.agentName) + '">'
        : cfg.agentName.charAt(0).toUpperCase();
    }

    // Update home screen avatar + greeting
    var homeAvatarEl   = this._shadow.getElementById("snkr-home-avatar");
    var homeGreetingEl = this._shadow.getElementById("snkr-home-greeting");
    if (homeAvatarEl) {
      homeAvatarEl.innerHTML = cfg.agentAvatar
        ? '<img src="' + esc(cfg.agentAvatar) + '" alt="' + esc(cfg.agentName) + '">'
        : cfg.agentName.charAt(0).toUpperCase();
    }
    if (homeGreetingEl) {
      var parts = cfg.welcomeMessage.split("\n");
      homeGreetingEl.innerHTML =
        esc(parts[0]) +
        (parts[1] ? '<span class="snkr-greeting-sub">' + esc(parts[1]) + '</span>' : '');
    }

    this._input.placeholder = cfg.placeholder;
    if (this._loading) this._loading.style.display = "none";
    this._messages.style.display = "flex";
    this._buildHomeSuggestions();
    // Feature 4: start ambient page observers after config loaded
    this._setupAmbient();
  };

  Widget.prototype._buildHomeSuggestions = function () {
    var self = this;
    var cfg = this._cfg;

    // Remove old suggestions section if any
    var old = this._shadow.getElementById("snkr-suggestions-section");
    if (old) old.parentNode.removeChild(old);

    if (!cfg.suggestions || cfg.suggestions.length === 0) return;

    var grid = document.createElement("div");
    grid.id = "snkr-suggestions-section";
    grid.className = "snkr-suggestions-grid";

    cfg.suggestions.forEach(function (s) {
      var title  = s.title  || (typeof s === "string" ? s : "");
      var prompt = s.prompt || s.title || (typeof s === "string" ? s : "");
      var desc   = s.description || "";
      var icon   = s.icon   || "";
      if (!title && !prompt) return;

      var chip = document.createElement("button");
      chip.className = "snkr-home-chip";
      chip.innerHTML =
        (icon ? '<div class="snkr-chip-icon">' + esc(icon) + '</div>' : '') +
        '<div class="snkr-chip-title">' + esc(title || prompt) + '</div>' +
        (desc ? '<div class="snkr-chip-desc">' + esc(desc) + '</div>' : '');

      chip.addEventListener("click", function (e) {
        e.stopPropagation();
        self._input.value = prompt;
        self._showChat();
        self._send();
      });
      grid.appendChild(chip);
    });

    // Insert after the start button
    var startBtn = this._shadow.getElementById("snkr-start-btn");
    if (startBtn && startBtn.parentNode) {
      startBtn.parentNode.insertBefore(grid, startBtn.nextSibling);
    }
  };

  // ── Open / Close ──────────────────────────────────────────────────────────────

  Widget.prototype.open = function () {
    this._isOpen = true;
    // Feature 5: clear notification badge
    this._badge.classList.remove("show");
    this._backgrounded = false;
    // Feature 4: hide ambient probe
    if (this._probe) this._probe.classList.remove("show");
    this._toggle.innerHTML = I.x;
    // Re-append badge (innerHTML replaced above)
    this._toggle.appendChild(this._badge);
    this._toggle.setAttribute("aria-label", "Close chat");
    this._panel.classList.add("open");
    // Always show home screen when opening (unless chat already has messages)
    if (this._messages.children.length === 0) {
      this._showHome();
      // Feature 3: check for pioneer notification
      this._checkPioneer();
    } else {
      this._showChat();
    }
  };

  Widget.prototype.close = function () {
    this._isOpen = false;
    this._toggle.innerHTML = I.chat;
    // Re-append badge after innerHTML replacement
    this._toggle.appendChild(this._badge);
    this._toggle.setAttribute("aria-label", "Open chat");
    this._panel.classList.remove("open");
    // Close dropdown if open
    var dd = this._shadow.getElementById("snkr-menu-dropdown");
    if (dd) dd.classList.remove("open");
  };

  // ── Messages ──────────────────────────────────────────────────────────────────

  Widget.prototype._hideEmpty = function () {
    this._messages.style.display = "flex";
  };

  Widget.prototype._row = function (type) {
    this._hideEmpty();
    // Switch to chat screen on first message
    if (!this._chat.classList.contains("active")) {
      this._showChat();
    }
    var row = document.createElement("div");
    row.className = "snkr-row " + type;
    var bubble = document.createElement("div");
    bubble.className = "snkr-bubble";
    row.appendChild(bubble);
    // Show "AgentName · time" below agent bubbles, just timestamp below user
    var ts = document.createElement("div");
    ts.className = "snkr-ts";
    if (type === "agent") {
      ts.textContent = this._cfg.agentName + " · " + timeNow();
    } else {
      ts.textContent = timeNow();
    }
    row.appendChild(ts);
    this._messages.appendChild(row);
    this._scroll();
    return bubble;
  };

  Widget.prototype._addAgent = function () {
    return this._row("agent");
  };

  Widget.prototype._addUser = function (text) {
    var b = this._row("user");
    b.textContent = text;
  };

  Widget.prototype._addError = function (text) {
    var b = this._row("error");
    b.textContent = text;
  };

  Widget.prototype._typing = function () {
    this._hideEmpty();
    var wrap = document.createElement("div");
    wrap.className = "snkr-row agent";
    var dots = document.createElement("div");
    dots.id = "snkr-typing";
    dots.innerHTML = "<span></span><span></span><span></span>";
    wrap.appendChild(dots);
    this._messages.appendChild(wrap);
    this._scroll();
    return wrap;
  };

  Widget.prototype._remove = function (el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
  };

  Widget.prototype._scroll = function () {
    this._messages.scrollTop = this._messages.scrollHeight;
  };

  Widget.prototype._busy = function (on) {
    this.streaming = on;
    this._sendBtn.disabled = on;
    this._input.disabled = on;
  };

  // ── Send & Stream ─────────────────────────────────────────────────────────────

  Widget.prototype._send = function () {
    var text = this._input.value.trim();
    if (!text || this.streaming) return;

    this._input.value = "";
    this._input.style.height = "auto";
    this._addUser(text);

    var self = this;
    this._typingEl = this._typing();
    this._busy(true);
    this._agentText   = "";
    this._agentBubble = null;
    // Feature 1+3: reset per-turn tool counter
    this._toolsUsed = 0;
    this._sherlockEl = null;
    this._sherlockSteps = {};
    // Feature 5: track if tab goes hidden during streaming
    this._backgrounded = false;
    if (this._visHandler) document.removeEventListener("visibilitychange", this._visHandler);
    this._visHandler = function () {
      if (document.hidden) self._backgrounded = true;
    };
    document.addEventListener("visibilitychange", this._visHandler);
    // Feature 5: request notification permission on first send (non-blocking)
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      try { Notification.requestPermission(); } catch (_) {}
    }

    fetch(this.apiUrl + "/widgets/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Widget-API-Key": this.apiKey,
      },
      body: JSON.stringify({
        message: text,
        session_id: this.sessionId,
        conversation_id: this.conversationId || undefined,
        user: this._user || undefined,
        user_hash: this._userHash || undefined,
      }),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.text().then(function (t) { throw new Error(t || "HTTP " + res.status); });
        }
        return res;
      })
      .then(function (res) {
        var reader = res.body.getReader();
        var dec    = new TextDecoder();
        var buf    = "";

        function pump() {
          return reader.read().then(function (r) {
            if (r.done) { self._finish(); return; }
            buf += dec.decode(r.value, { stream: true });
            var parts = buf.split("\n\n");
            buf = parts.pop();
            parts.forEach(function (p) {
              p.split("\n").forEach(function (line) {
                if (line.slice(0, 6) === "data: ") self._evt(line.slice(6));
              });
            });
            return pump();
          });
        }
        return pump();
      })
      .catch(function (err) {
        self._remove(self._typingEl);
        self._typingEl = null;
        self._remove(self._agentBubble);
        self._agentBubble = null;
        self._addError("Sorry, something went wrong. Please try again.");
        console.error("[SynkoraWidget]", err.message);
        self._finish();
      });
  };

  Widget.prototype._evt = function (raw) {
    var evt;
    try { evt = JSON.parse(raw); } catch (_) { return; }

    if (evt.type === "chunk" && evt.content) {
      // Remove typing dots on first chunk
      if (this._typingEl) {
        this._remove(this._typingEl);
        this._typingEl = null;
      }
      // Feature 1: collapse Sherlock panel when text starts flowing
      if (this._sherlockEl) {
        this._sherlockEl.style.opacity = "0.5";
        this._sherlockEl.style.transition = "opacity 0.4s";
      }
      this._agentText += evt.content;
      if (!this._agentBubble) {
        this._agentBubble = this._addAgent();
        this._agentBubble.classList.add("streaming");
      }
      if (!this._agentRenderTimer) {
        this._agentRenderTimer = setTimeout(() => {
          this._agentRenderTimer = null;
          if (this._agentBubble) {
            this._agentBubble.innerHTML = mdParse(this._agentText, true);
            this._scroll();
          }
        }, 50);
      }

    } else if (evt.type === "tool_status") {
      // Feature 1: Sherlock mode — live investigation steps
      this._sherlockStep(evt.tool_name || "tool", evt.status, evt.description, evt.duration_ms);
      if (evt.status === "started") { this._toolsUsed++; }

    } else if (evt.type === "done") {
      if (evt.metadata && evt.metadata.conversation_id) {
        this.conversationId = evt.metadata.conversation_id;
      }

    } else if (evt.type === "error") {
      var msg = evt.error || evt.content || "An error occurred.";
      if (this._agentBubble) {
        this._agentBubble.closest(".snkr-row").className = "snkr-row error";
        this._agentBubble.textContent = msg;
        this._agentBubble.classList.remove("streaming");
      } else {
        this._addError(msg);
      }
    }
  };

  Widget.prototype._finish = function () {
    // Remove typing dots if stream ended before any chunk (error case)
    if (this._typingEl) {
      this._remove(this._typingEl);
      this._typingEl = null;
    }
    // Final clean render without streaming flag, remove cursor
    if (this._agentRenderTimer) {
      clearTimeout(this._agentRenderTimer);
      this._agentRenderTimer = null;
    }
    if (this._agentBubble) {
      this._agentBubble.innerHTML = mdParse(this._agentText, false);
      this._agentBubble.classList.remove("streaming");
    }
    // Save text before nulling (needed for Feature 5 notification body)
    var _lastAgentText = this._agentText;
    this._busy(false);
    this._agentBubble = null;
    this._agentText   = "";

    // Feature 1: fade out sherlock panel after 2s
    if (this._sherlockEl) {
      var sEl = this._sherlockEl;
      this._sherlockEl = null;
      this._sherlockSteps = {};
      setTimeout(function () {
        sEl.style.opacity = "0";
        sEl.style.transition = "opacity 0.4s";
        setTimeout(function () { if (sEl.parentNode) sEl.parentNode.removeChild(sEl); }, 450);
      }, 2000);
    }

    // Feature 3: store pioneer session if tools were used
    if (this._toolsUsed > 0 && this.conversationId) {
      try {
        var pioneer = { convId: this.conversationId, toolsUsed: this._toolsUsed, ts: Date.now() };
        localStorage.setItem(this._pioneerKey, JSON.stringify(pioneer));
      } catch (_) {}
    }
    this._toolsUsed = 0;

    // Feature 5: show notification badge if tab was hidden
    if (this._visHandler) {
      document.removeEventListener("visibilitychange", this._visHandler);
      this._visHandler = null;
    }
    if (this._backgrounded && !this._isOpen) {
      this._badge.classList.add("show");
      // Also try browser Notification if permission granted
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        try {
          new Notification(this._cfg.agentName + " replied", {
            body: (_lastAgentText || "Your answer is ready.").replace(/<[^>]+>/g, "").slice(0, 100),
            icon: this._cfg.agentAvatar || undefined,
          });
        } catch (_) {}
      }
    }
    this._backgrounded = false;
    this._input.focus();
  };

  // ─── Public API ────────────────────────────────────────────────────────────────
  //
  // SynkoraWidget.init(cfg)
  //
  // Required options:
  //   widgetId  {string}  — Widget UUID from the Synkora dashboard
  //   apiKey    {string}  — Widget API key from the Synkora dashboard
  //
  // Optional options:
  //   apiUrl    {string}  — Override the Synkora API base URL (default: auto-detected)
  //
  // ── Identity Verification (recommended for authenticated SaaS apps) ──────────
  //
  //   user      {object}  — Logged-in user context. When provided, conversations are
  //                         scoped to this user so history persists across sessions.
  //     user.id       {string}  REQUIRED — Your platform's unique user ID
  //     user.name     {string}  Optional display name shown in Synkora dashboard
  //     user.email    {string}  Optional user email
  //     user.orgId    {string}  Optional org/workspace ID — used for agent routing
  //     user.orgName  {string}  Optional org display name
  //
  //   userHash  {string}  — HMAC-SHA256 signature of the user's ID, computed on your
  //                         server using the widget's identity secret.
  //                         Required when identity_verification_required=true on the widget.
  //
  //   HOW TO GENERATE userHash (server-side only — never in the browser):
  //
  //     Node.js:
  //       const crypto = require("crypto");
  //       const hash = crypto
  //         .createHmac("sha256", WIDGET_IDENTITY_SECRET)
  //         .update(user.id)
  //         .digest("hex");
  //
  //     Python:
  //       import hmac, hashlib
  //       hash = hmac.new(
  //           WIDGET_IDENTITY_SECRET.encode(),
  //           user_id.encode(),
  //           hashlib.sha256
  //       ).hexdigest()
  //
  //     Ruby:
  //       require "openssl"
  //       hash = OpenSSL::HMAC.hexdigest("SHA256", WIDGET_IDENTITY_SECRET, user_id)
  //
  //     PHP:
  //       $hash = hash_hmac("sha256", $userId, $widgetIdentitySecret);
  //
  //   ⚠  The WIDGET_IDENTITY_SECRET is shown once when you create the widget (or after
  //      regenerating it via POST /api/v1/widgets/{id}/regenerate-identity-secret).
  //      Store it as a server-side environment variable — never expose it to the browser.
  //
  // ── Agent Routing ────────────────────────────────────────────────────────────
  //
  //   When enable_agent_routing=true is set on the widget and user.orgId is provided,
  //   Synkora looks up a pre-configured route table (managed via the widget routes API)
  //   to pick the agent for that org. This lets different customer orgs get different
  //   agents (different knowledge bases, system prompts, tools) from a single widget.
  //   Orgs without a route fall back to the widget's default agent.
  //
  // ── Examples ─────────────────────────────────────────────────────────────────
  //
  //   Basic (anonymous, no identity verification):
  //     SynkoraWidget.init({
  //       widgetId: "your-widget-id",
  //       apiKey:   "swk_...",
  //     });
  //
  //   With identified user (no verification enforced):
  //     SynkoraWidget.init({
  //       widgetId: "your-widget-id",
  //       apiKey:   "swk_...",
  //       user: { id: "usr_123", name: "Alice", email: "alice@acme.com", orgId: "acme" },
  //     });
  //
  //   With identity verification enabled (userHash required):
  //     // 1. Your server computes: hash = HMAC-SHA256(WIDGET_IDENTITY_SECRET, user.id)
  //     // 2. Your server passes the hash to the page (e.g. in a <script> or API response)
  //     SynkoraWidget.init({
  //       widgetId:  "your-widget-id",
  //       apiKey:    "swk_...",
  //       user:      { id: "usr_123", name: "Alice", orgId: "acme" },
  //       userHash:  "{{ server_computed_hash }}",
  //     });
  //
  // ─────────────────────────────────────────────────────────────────────────────

  global.SynkoraWidget = {
    _i: {},
    init: function (cfg) {
      if (!cfg || !cfg.widgetId || !cfg.apiKey) {
        console.error("[SynkoraWidget] widgetId and apiKey are required.");
        return;
      }
      if (this._i[cfg.widgetId]) return;
      var w = new Widget(cfg);
      this._i[cfg.widgetId] = w;
      return w;
    },
    open:  function (id) { var w = this._i[id]; if (w) w.open(); },
    close: function (id) { var w = this._i[id]; if (w) w.close(); },
  };

})(window);
