/**
 * Synkora Agent Widget
 * Embeddable AI chat widget using Shadow DOM for full CSS isolation.
 * Usage: SynkoraWidget.init({ widgetId, apiKey, containerId, apiUrl })
 */
(function (global) {
  "use strict";

  if (global.SynkoraWidget) return;

  // Patch pushState/replaceState once so SPA navigations (which don't trigger a real
  // page load, and therefore no popstate) still emit a detectable event. Used by the
  // page-context-awareness feature to reset stale host-supplied context on navigation.
  (function () {
    ["pushState", "replaceState"].forEach(function (method) {
      var original = history[method];
      history[method] = function () {
        var result = original.apply(this, arguments);
        global.dispatchEvent(new Event("synkoralocationchange"));
        return result;
      };
    });
  }());

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
    if (hex.length !== 6) return "121,223,188";
    var n = parseInt(hex, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255].join(",");
  }

  function darkenHex(hex, amount) {
    hex = (hex || "").replace(/^#/, "");
    if (hex.length === 3) hex = hex.split("").map(function (c) { return c + c; }).join("");
    if (hex.length !== 6) return "#2d8b69";
    var n = parseInt(hex, 16);
    var r = Math.max(0, ((n >> 16) & 255) - amount);
    var g = Math.max(0, ((n >> 8) & 255) - amount);
    var b = Math.max(0, (n & 255) - amount);
    return "#" + [r, g, b].map(function (v) { return v.toString(16).padStart(2, "0"); }).join("");
  }

  function luminance(hex) {
    hex = (hex || "").replace(/^#/, "");
    if (hex.length === 3) hex = hex.split("").map(function (c) { return c + c; }).join("");
    if (hex.length !== 6) return 0.5;
    var n = parseInt(hex, 16);
    var r = ((n >> 16) & 255) / 255;
    var g = ((n >> 8) & 255) / 255;
    var b = (n & 255) / 255;
    r = r < 0.04045 ? r / 12.92 : Math.pow((r + 0.055) / 1.055, 2.4);
    g = g < 0.04045 ? g / 12.92 : Math.pow((g + 0.055) / 1.055, 2.4);
    b = b < 0.04045 ? b / 12.92 : Math.pow((b + 0.055) / 1.055, 2.4);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
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
      background: linear-gradient(135deg, var(--snkr-c, #79dfbc) 0%, var(--snkr-cd, #2d8b69) 100%);
      color: #171717;
      box-shadow: 0 8px 28px rgba(var(--snkr-rgb, 121,223,188), 0.34), 0 8px 18px rgba(23,23,23,0.18);
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none;
      transition: transform 0.2s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.2s ease;
    }
    #snkr-toggle:hover {
      transform: scale(1.1);
      box-shadow: 0 12px 34px rgba(var(--snkr-rgb, 121,223,188), 0.38), 0 6px 16px rgba(23,23,23,0.22);
    }
    #snkr-toggle:active { transform: scale(0.96); }
    #snkr-toggle svg { pointer-events: none; }
    #snkr-toggle::before {
      content: ''; position: absolute; inset: -4px; border-radius: 50%;
      border: 2px solid rgba(var(--snkr-rgb, 121,223,188), 0.34);
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
      width: 420px; height: 660px; background: #F8FAFC; border-radius: 24px;
      overflow: hidden; display: none; flex-direction: column;
      font-family: 'Avenir Next', 'Inter', system-ui, -apple-system, sans-serif;
      font-size: 14px; line-height: 1.5; color: #0F172A;
      border: 1px solid rgba(0,0,0,0.08);
      box-shadow: 0 30px 80px rgba(0,0,0,0.14), 0 10px 24px rgba(0,0,0,0.07);
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
      background: radial-gradient(circle at top right, rgba(var(--snkr-rgb, 121,223,188), 0.18), transparent 28%), linear-gradient(160deg, #171717 0%, #23221f 100%);
      padding: 22px 20px 24px; position: relative; flex-shrink: 0;
    }
    #snkr-home-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
    #snkr-home-avatar {
      width: 48px; height: 48px; border-radius: 50%;
      background: rgba(var(--snkr-rgb, 121,223,188), 0.16); border: 2px solid rgba(255,255,255,0.16);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; font-weight: 700; color: #fff; overflow: hidden; flex-shrink: 0;
    }
    #snkr-home-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
    #snkr-home-close {
      background: rgba(255,255,255,0.08); border: none; cursor: pointer; color: #fff;
      width: 30px; height: 30px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s; flex-shrink: 0;
    }
    #snkr-home-close:hover { background: rgba(255,255,255,0.16); }
    #snkr-home-greeting {
      font-size: 24px; font-weight: 800; color: #fff; line-height: 1.25;
      letter-spacing: -0.02em;
    }
    #snkr-home-greeting .snkr-greeting-sub {
      display: block; font-size: 20px; font-weight: 700; opacity: 0.88; margin-top: 2px;
    }
    #snkr-home-body {
      flex: 1; overflow-y: auto; padding: 16px 14px;
      background: #F8FAFC; display: flex; flex-direction: column; gap: 10px;
    }
    #snkr-home-body::-webkit-scrollbar { width: 4px; }
    #snkr-home-body::-webkit-scrollbar-track { background: transparent; }
    #snkr-home-body::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
    #snkr-start-btn {
      width: 100%; padding: 16px 18px; background: rgba(255,255,255,0.86); border: 1px solid rgba(23,23,23,0.08);
      border-radius: 18px; cursor: pointer; outline: none;
      display: flex; align-items: center; justify-content: space-between;
      font-size: 14px; font-weight: 600; color: #171717; font-family: inherit;
      box-shadow: 0 10px 26px rgba(23,23,23,0.06);
      transition: box-shadow 0.15s, border-color 0.15s;
    }
    #snkr-start-btn:hover {
      border-color: var(--snkr-c, #79dfbc);
      box-shadow: 0 14px 28px rgba(23,23,23,0.08);
    }
    #snkr-start-btn-icon {
      width: 32px; height: 32px; border-radius: 50%;
      background: var(--snkr-c, #79dfbc); display: flex;
      align-items: center; justify-content: center; flex-shrink: 0;
    }
    .snkr-suggestions-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    }
    .snkr-home-chip {
      display: flex; flex-direction: column; align-items: flex-start;
      padding: 12px 12px 14px; border-radius: 14px;
      background: rgba(255,255,255,0.86); border: 1px solid rgba(23,23,23,0.08);
      cursor: pointer; font-family: inherit; text-align: left; outline: none;
      box-shadow: 0 10px 24px rgba(23,23,23,0.05);
      transition: box-shadow 0.15s, border-color 0.15s; gap: 6px;
    }
    .snkr-home-chip:hover { border-color: var(--snkr-c, #79dfbc); box-shadow: 0 14px 28px rgba(23,23,23,0.08); }
    .snkr-chip-icon {
      width: 34px; height: 34px; border-radius: 10px; background: rgba(var(--snkr-rgb, 121,223,188), 0.12);
      display: flex; align-items: center; justify-content: center;
      font-size: 17px; flex-shrink: 0; margin-bottom: 2px;
    }
    .snkr-chip-title { font-size: 12.5px; font-weight: 700; color: #111827; line-height: 1.3; }
    .snkr-chip-desc { font-size: 11.5px; color: #64748B; line-height: 1.35; }
    #snkr-home-branding {
      text-align: center; padding: 8px; font-size: 11px; color: #64748B;
      font-family: inherit; flex-shrink: 0; background: #F8FAFC;
    }
    #snkr-home-branding a { color: #0F172A; text-decoration: none; font-weight: 600; }

    /* ── Chat Screen ─────────────────── */
    #snkr-chat { display: none; flex-direction: column; flex: 1; min-height: 0; }
    #snkr-chat.active { display: flex; }

    /* Chat Header */
    #snkr-header {
      padding: 0 12px; height: 64px;
      display: flex; align-items: center; gap: 8px;
      border-bottom: 1px solid rgba(0,0,0,0.07); flex-shrink: 0;
      background: #fff; position: relative;
    }
    #snkr-back {
      background: #F1F5F9; border: none; cursor: pointer; color: #64748B;
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s; flex-shrink: 0;
    }
    #snkr-back:hover { background: #E2E8F0; }
    #snkr-avatar {
      width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
      background: rgba(var(--snkr-rgb, 121,223,188), 0.12);
      border: 2px solid rgba(var(--snkr-rgb, 121,223,188), 0.24);
      display: flex; align-items: center; justify-content: center;
      font-size: 15px; font-weight: 700; color: #171717;
      overflow: hidden;
    }
    #snkr-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
    #snkr-hdr-info { flex: 1; min-width: 0; }
    #snkr-hdr-name {
      font-size: 14px; font-weight: 700; color: #111827;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    #snkr-hdr-status {
      font-size: 11px; color: #64748B;
      display: flex; align-items: center; gap: 4px;
    }
    #snkr-hdr-status::before {
      content: ''; width: 7px; height: 7px; border-radius: 50%;
      background: #22c55e; display: inline-block; flex-shrink: 0;
    }
    #snkr-menu-wrap { position: relative; flex-shrink: 0; }
    #snkr-menu-btn {
      background: #F1F5F9; border: none; cursor: pointer; color: #64748B;
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s;
    }
    #snkr-menu-btn:hover { background: #E2E8F0; }
    #snkr-menu-dropdown {
      display: none; position: absolute; top: 40px; right: 0; z-index: 10;
      background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 16px;
      box-shadow: 0 18px 46px rgba(0,0,0,0.12); min-width: 210px; overflow: hidden;
    }
    #snkr-menu-dropdown.open { display: block; }
    .snkr-menu-item {
      display: flex; align-items: center; gap: 12px; padding: 13px 16px;
      cursor: pointer; font-size: 14px; color: #0F172A; font-family: inherit;
      background: transparent; border: none; width: 100%; text-align: left;
      outline: none; transition: background 0.1s;
    }
    .snkr-menu-item:hover { background: #F8FAFC; }
    .snkr-menu-item:not(:last-child) { border-bottom: 1px solid rgba(0,0,0,0.06); }
    .snkr-menu-item svg { flex-shrink: 0; }
    #snkr-close {
      background: #F1F5F9; border: none; cursor: pointer; color: #64748B;
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background 0.15s; flex-shrink: 0;
    }
    #snkr-close:hover { background: #E2E8F0; }

    /* Messages */
    #snkr-messages {
      flex: 1; overflow-y: auto; padding: 16px 14px; display: flex;
      flex-direction: column; gap: 2px; background: #F8FAFC;
    }
    #snkr-messages::-webkit-scrollbar { width: 4px; }
    #snkr-messages::-webkit-scrollbar-track { background: transparent; }
    #snkr-messages::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }

    .snkr-row { display: flex; flex-direction: column; gap: 3px; animation: snkr-in 0.18s ease both; margin-bottom: 8px; }
    @keyframes snkr-in { from { opacity:0; transform:translateY(5px); } to { opacity:1; transform:none; } }
    .snkr-row.user  { align-items: flex-end; }
    .snkr-row.agent { align-items: flex-start; }
    .snkr-row.error { align-items: flex-start; }
    .snkr-row-inner { display: flex; align-items: flex-end; gap: 8px; max-width: 88%; }
    .snkr-row.user  .snkr-row-inner { flex-direction: row-reverse; }
    .snkr-row.agent .snkr-row-inner { flex-direction: row; }
    .snkr-row.error .snkr-row-inner { flex-direction: row; }

    /* ── Message avatars ────────── */
    .snkr-msg-avatar {
      width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
    }
    .snkr-agent-avatar { background: var(--snkr-c, #79dfbc); color: #fff; }
    .snkr-user-avatar  { background: #E2E8F0; color: #64748B; }

    .snkr-bubble {
      max-width: 100%; padding: 11px 15px; border-radius: 20px;
      font-size: 14px; line-height: 1.65; word-break: break-word;
    }
    .snkr-row.user .snkr-bubble {
      background: var(--snkr-c, #79dfbc); color: var(--snkr-fg, #fff); border-bottom-right-radius: 5px;
    }
    .snkr-row.agent .snkr-bubble {
      background: #F1F5F9; color: #0F172A; border-bottom-left-radius: 5px;
    }
    .snkr-row.error .snkr-bubble {
      background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; border-radius: 12px;
    }
    .snkr-ts {
      font-size: 11px; color: #94A3B8; padding: 0 4px;
    }
    .snkr-row.user  .snkr-ts { text-align: right; padding-right: 36px; }
    .snkr-row.agent .snkr-ts { padding-left: 36px; }

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
      border-left: 3px solid var(--snkr-c, #79dfbc);
      padding: 6px 12px; margin: 8px 0; color: #64748B;
      font-style: italic; background: #F8FAFC; border-radius: 0 6px 6px 0;
    }
    .snkr-bubble hr { border: none; border-top: 1px solid #E2E8F0; margin: 10px 0; }
    .snkr-bubble code {
      background: rgba(0,0,0,0.07); padding: 2px 5px; border-radius: 4px;
      font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px;
    }
    .snkr-row.user .snkr-bubble code { background: rgba(0,0,0,0.12); }
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
    .snkr-table-wrap { overflow-x: auto; margin: 8px 0; border-radius: 8px; border: 1px solid #E2E8F0; }
    .snkr-bubble table { border-collapse: collapse; width: 100%; font-size: 13px; }
    .snkr-bubble th, .snkr-bubble td { border-bottom: 1px solid #E2E8F0; padding: 7px 11px; text-align: left; white-space: nowrap; }
    .snkr-bubble th { background: #F8FAFC; font-weight: 600; color: #0F172A; border-bottom: 2px solid #E2E8F0; }
    .snkr-bubble tr:last-child td { border-bottom: none; }
    .snkr-bubble tr:nth-child(even) td { background: #F1F5F9; }
    .snkr-img { max-width: 100%; border-radius: 8px; margin: 6px 0; display: block; cursor: zoom-in; border: 1px solid #E2E8F0; }
    .snkr-bubble a { color: #0F172A; text-decoration: none; border-bottom: 1px solid var(--snkr-c, #79dfbc); }
    .snkr-bubble a:hover { text-decoration: underline; }

    /* ── Streaming cursor ────────────── */
    .snkr-bubble.streaming::after {
      content: '▋'; display: inline;
      animation: snkr-blink 0.7s step-end infinite;
      color: var(--snkr-c, #79dfbc); font-size: 0.85em; margin-left: 1px;
    }
    @keyframes snkr-blink { 0%,100%{opacity:1} 50%{opacity:0} }

    /* ── Typing indicator ────────────── */
    #snkr-typing {
      display: flex; align-items: center; gap: 4px; padding: 12px 15px;
      background: #F1F5F9; border-radius: 20px; border-bottom-left-radius: 5px;
      width: fit-content;
    }
    #snkr-typing span {
      width: 7px; height: 7px; border-radius: 50%; background: #94A3B8; display: inline-block;
    }
    #snkr-typing span:nth-child(1) { animation: snkr-dot 1.2s -0.32s infinite ease-in-out; }
    #snkr-typing span:nth-child(2) { animation: snkr-dot 1.2s -0.16s infinite ease-in-out; }
    #snkr-typing span:nth-child(3) { animation: snkr-dot 1.2s 0s    infinite ease-in-out; }
    @keyframes snkr-dot {
      0%,80%,100% { transform: scale(0.6); background: #9ca3af; }
      40%         { transform: scale(1);   background: var(--snkr-c, #79dfbc); }
    }

    /* ── Footer ──────────────────────── */
    #snkr-footer {
      padding: 10px 14px 14px; background: #fff;
      border-top: 1px solid rgba(0,0,0,0.07); flex-shrink: 0;
    }
    #snkr-input-box {
      border: 1.5px solid rgba(0,0,0,0.12); border-radius: 18px; background: #fff;
      transition: border-color 0.15s, box-shadow 0.15s; overflow: hidden;
    }
    #snkr-input-box:focus-within {
      border-color: var(--snkr-c, #79dfbc);
      box-shadow: 0 0 0 3px rgba(var(--snkr-rgb,121,223,188),0.14);
    }
    #snkr-input {
      display: block; width: 100%; border: none; outline: none; background: transparent;
      font-family: 'Avenir Next', 'Inter', system-ui, sans-serif; font-size: 14px; color: #0F172A;
      resize: none; max-height: 120px; min-height: 22px; line-height: 1.5;
      padding: 14px 16px 6px;
    }
    #snkr-input::placeholder { color: #94A3B8; }
    #snkr-input:disabled { opacity: 0.6; cursor: not-allowed; }
    #snkr-footer-row {
      display: flex; align-items: center; justify-content: space-between;
      padding: 4px 8px 6px; gap: 4px;
    }
    #snkr-footer-actions { display: flex; align-items: center; gap: 6px; }
    #snkr-send {
      width: 34px; height: 34px; border-radius: 50%; border: none;
      background: #d8d0c3; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      padding: 0; flex-shrink: 0; outline: none;
      transition: background 0.15s, transform 0.15s, box-shadow 0.15s;
    }
    #snkr-send.snkr-send-active {
      background: var(--snkr-c, #79dfbc);
      box-shadow: 0 2px 10px rgba(var(--snkr-rgb,121,223,188),0.35);
    }
    #snkr-send.snkr-send-active:hover { transform: scale(1.08); }
    #snkr-send:disabled { opacity: 0.4; cursor: not-allowed; }

    /* ── Branding ────────────────────── */
    #snkr-branding {
      text-align: center; padding: 6px 0 2px; font-size: 11px; color: #94A3B8;
      font-family: 'Avenir Next', 'Inter', system-ui, sans-serif; flex-shrink: 0;
    }
    #snkr-branding a { color: #0F172A; text-decoration: none; font-weight: 600; }
    #snkr-branding a:hover { text-decoration: underline; }

    /* ── Loading skeleton ────────────── */
    #snkr-loading {
      flex: 1; display: flex; align-items: center; justify-content: center;
      background: #F8FAFC; flex-direction: column; gap: 12px;
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

    /* ── HITL: Approval card ─────────── */
    .snkr-approval-card{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:12px;margin:8px 0;}
    .snkr-approval-header{font-size:12px;font-weight:600;color:#92400e;margin-bottom:6px;}
    .snkr-approval-header code{background:#fef3c7;padding:1px 4px;border-radius:4px;}
    .snkr-approval-args{font-size:11px;background:#fff;border:1px solid #e5e7eb;border-radius:6px;padding:8px;overflow:auto;max-height:120px;margin-bottom:8px;color:#374151;}
    .snkr-approval-actions{display:flex;gap:8px;}
    .snkr-approval-btn{padding:5px 14px;border-radius:6px;border:none;cursor:pointer;font-size:12px;font-weight:500;}
    .snkr-approve{background:#16a34a;color:#fff;}
    .snkr-approve:hover{background:#15803d;}
    .snkr-approve:disabled{background:#86efac;cursor:not-allowed;}
    .snkr-reject{background:#ef4444;color:#fff;}
    .snkr-reject:hover{background:#dc2626;}
    .snkr-reject:disabled{background:#fca5a5;cursor:not-allowed;}
    .snkr-approval-done{font-size:12px;color:#6b7280;font-style:italic;}

    /* ── HITL: Handoff banner ─────────── */
    .snkr-handoff-banner{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:10px 14px;margin:8px 0;font-size:13px;color:#166534;display:flex;align-items:center;gap:8px;}
    .snkr-handoff-icon{font-size:16px;}
    .snkr-system-note{font-size:12px;color:#6b7280;text-align:center;padding:8px;font-style:italic;}

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

    /* ── History ─────────────────────── */
    #snkr-history-section { margin-top: 12px; }
    .snkr-history-label-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; padding: 0 4px; }
    .snkr-history-label { font-size: 11px; font-weight: 600; color: rgba(0,0,0,0.38); text-transform: uppercase; letter-spacing: .06em; }
    .snkr-history-viewall { font-size: 11px; font-weight: 600; color: var(--snkr-c, #79dfbc); background: none; border: none; cursor: pointer; padding: 0; font-family: inherit; filter: brightness(0.75); transition: opacity .15s; }
    .snkr-history-viewall:hover { opacity: 0.7; }
    .snkr-history-empty { font-size: 12px; color: rgba(0,0,0,0.3); text-align: center; padding: 14px 8px; font-style: italic; }
    .snkr-history-item { display: flex; align-items: center; gap: 10px; padding: 9px 10px; border-radius: 12px; cursor: pointer; transition: background .15s; border: none; background: none; width: 100%; text-align: left; font-family: inherit; }
    .snkr-history-item:hover { background: rgba(0,0,0,0.05); }
    .snkr-history-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--snkr-c); flex-shrink: 0; opacity: 0.8; }
    .snkr-history-content { flex: 1; min-width: 0; }
    .snkr-history-preview { font-size: 13px; color: #111; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
    .snkr-history-time { font-size: 11px; color: rgba(0,0,0,0.38); margin-top: 1px; }
    .snkr-history-chevron { opacity: 0.25; flex-shrink: 0; }

    /* ── Voice recording UI ──────────── */
    #snkr-rec-indicator {
      display: none; align-items: center; gap: 6px;
      padding: 6px 12px; background: #fef2f2; border-radius: 20px;
      font-size: 11.5px; font-weight: 600; color: #ef4444; flex-shrink: 0;
    }
    #snkr-rec-indicator.show { display: flex; }
    #snkr-rec-timer { font-variant-numeric: tabular-nums; min-width: 28px; }
    .snkr-rec-wave { display: flex; align-items: center; gap: 2px; }
    .snkr-rec-wave span {
      display: inline-block; width: 3px; border-radius: 2px; background: #ef4444;
      animation: snkr-wave 0.9s ease-in-out infinite;
    }
    .snkr-rec-wave span:nth-child(1) { height: 8px; animation-delay: 0s; }
    .snkr-rec-wave span:nth-child(2) { height: 14px; animation-delay: .15s; }
    .snkr-rec-wave span:nth-child(3) { height: 10px; animation-delay: .3s; }
    .snkr-rec-wave span:nth-child(4) { height: 16px; animation-delay: .45s; }
    .snkr-rec-wave span:nth-child(5) { height: 8px; animation-delay: .6s; }
    @keyframes snkr-wave { 0%,100%{transform:scaleY(0.5)} 50%{transform:scaleY(1)} }

    /* ── Audio message bubble ─────────── */
    .snkr-audio-msg { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
    .snkr-audio-msg audio { height: 32px; outline: none; max-width: 200px; }
    .snkr-audio-label { font-size: 11px; color: rgba(23,23,23,0.5); white-space: nowrap; }

    /* ── Privacy bar ─────────────────── */
    #snkr-privacy-bar {
      display: none; align-items: center; justify-content: space-between; gap: 8px;
      padding: 8px 14px; background: #F1F5F9; border-bottom: 1px solid rgba(0,0,0,0.07);
      font-size: 11.5px; color: #64748B; flex-shrink: 0;
    }
    #snkr-privacy-bar.show { display: flex; }
    #snkr-privacy-bar a { color: #0F172A; font-weight: 600; text-decoration: none; border-bottom: 1px solid currentColor; }
    #snkr-privacy-bar a:hover { opacity: 0.7; }
    #snkr-privacy-close {
      background: none; border: none; cursor: pointer; color: #8a8175; padding: 2px;
      display: flex; align-items: center; border-radius: 4px; outline: none;
      transition: background .15s, color .15s; flex-shrink: 0;
    }
    #snkr-privacy-close:hover { background: rgba(23,23,23,0.08); color: #171717; }

    /* ── Page context bar (page-context-awareness UI) ── */
    /* A contained pill, not an edge-to-edge bar — on the chat screen it sits
       inside the footer, directly above the input; on the home screen it
       needs its own horizontal margin since it isn't nested in a padded
       container there. */
    .snkr-ctx-bar {
      display: none; flex-direction: column; flex-shrink: 0;
      background: rgba(var(--snkr-rgb,121,223,188),0.08);
      border: 1px solid rgba(var(--snkr-rgb,121,223,188),0.25);
      border-radius: 12px; margin: 0 14px 8px; overflow: hidden;
    }
    #snkr-footer .snkr-ctx-bar { margin-left: 0; margin-right: 0; }
    .snkr-ctx-bar.show { display: flex; }
    .snkr-ctx-bar-row { display: flex; align-items: center; gap: 8px; padding: 7px 12px; }
    .snkr-ctx-summary {
      flex: 1; display: flex; align-items: center; gap: 8px; min-width: 0;
      background: none; border: none; cursor: pointer; padding: 0; outline: none;
      font-family: inherit; text-align: left;
    }
    .snkr-ctx-icon { flex-shrink: 0; display: flex; color: var(--snkr-cd, #2d8b69); }
    .snkr-ctx-label {
      flex: 1; min-width: 0; font-size: 12.5px; font-weight: 600; color: #0F172A;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .snkr-ctx-chevron { flex-shrink: 0; display: flex; color: #64748B; transition: transform .15s ease; }
    .snkr-ctx-bar.open .snkr-ctx-chevron { transform: rotate(90deg); }
    .snkr-ctx-close {
      flex-shrink: 0; background: none; border: none; cursor: pointer; padding: 2px;
      display: flex; align-items: center; border-radius: 4px; color: #94A3B8; outline: none;
      transition: background .15s, color .15s;
    }
    .snkr-ctx-close:hover { background: rgba(0,0,0,0.08); color: #171717; }
    .snkr-ctx-detail {
      display: none; flex-direction: column; gap: 4px; padding: 0 12px 10px 34px;
      animation: snkr-in .15s ease both;
    }
    .snkr-ctx-bar.open .snkr-ctx-detail { display: flex; }
    .snkr-ctx-row { display: flex; gap: 6px; font-size: 11.5px; line-height: 1.4; }
    .snkr-ctx-row-k { color: #64748B; flex-shrink: 0; }
    .snkr-ctx-row-v { color: #171717; font-weight: 500; overflow-wrap: anywhere; }

    /* ── Chat chips (in-chat suggestions) */
    #snkr-chat-chips {
      display: none; padding: 0 16px 10px; flex-direction: column; gap: 8px; flex-shrink: 0;
    }
    #snkr-chat-chips.show { display: flex; }
    .snkr-chat-chips-label {
      font-size: 11px; font-weight: 600; color: rgba(0,0,0,0.3); text-transform: uppercase;
      letter-spacing: .06em; padding: 0 2px;
    }
    .snkr-chat-chips-row { display: flex; flex-wrap: wrap; gap: 6px; }
    .snkr-chat-chip-btn {
      display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px;
      border-radius: 20px; border: 1.5px solid rgba(var(--snkr-rgb,121,223,188),0.35);
      background: rgba(var(--snkr-rgb,121,223,188),0.07); cursor: pointer; font-family: inherit;
      font-size: 13px; font-weight: 500; color: #171717; outline: none;
      transition: background .15s, border-color .15s; white-space: nowrap;
    }
    .snkr-chat-chip-btn:hover {
      background: rgba(var(--snkr-rgb,121,223,188),0.15);
      border-color: rgba(var(--snkr-rgb,121,223,188),0.6);
    }

    /* ── Attach + Mic buttons ────────── */
    #snkr-attach-btn, #snkr-mic-btn {
      width: 30px; height: 30px; border-radius: 50%; border: none;
      background: transparent; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      padding: 0; flex-shrink: 0; outline: none; color: #94A3B8;
      transition: background .15s, color .15s;
    }
    #snkr-attach-btn:hover, #snkr-mic-btn:hover { background: #F1F5F9; color: #0F172A; }
    #snkr-mic-btn.recording {
      color: #ef4444; background: #fef2f2;
      animation: snkr-mic-pulse 1s ease-in-out infinite;
    }
    @keyframes snkr-mic-pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

    /* ── File preview chip ───────────── */
    #snkr-file-preview { display: none; padding: 8px 16px 0; }
    #snkr-file-preview.show { display: flex; }
    .snkr-file-chip {
      display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px;
      border-radius: 10px; background: #F1F5F9; border: 1px solid rgba(0,0,0,0.08);
      font-size: 12px; color: #0F172A; max-width: 100%;
    }
    .snkr-file-chip-icon { flex-shrink: 0; color: #64748B; }
    .snkr-file-chip-name {
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      max-width: 180px; font-weight: 500;
    }
    .snkr-file-remove {
      background: none; border: none; cursor: pointer; padding: 0; outline: none;
      color: #9e9690; display: flex; align-items: center; transition: color .15s; flex-shrink: 0;
    }
    .snkr-file-remove:hover { color: #ef4444; }

    /* ── End-chat banner ─────────────── */
    .snkr-ended-wrap {
      display: flex; flex-direction: column; align-items: center;
      padding: 24px 20px; text-align: center; animation: snkr-in .25s ease both;
    }
    .snkr-ended-ring {
      width: 44px; height: 44px; border-radius: 50%; background: #F1F5F9;
      display: flex; align-items: center; justify-content: center;
      margin-bottom: 12px; color: #64748B;
    }
    .snkr-ended-title { font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 4px; }
    .snkr-ended-sub { font-size: 13px; color: #64748B; margin-bottom: 16px; }
    .snkr-restart-btn {
      display: inline-flex; align-items: center; gap: 8px; padding: 10px 20px;
      border-radius: 14px; border: 1.5px solid rgba(var(--snkr-rgb,121,223,188),0.4);
      background: rgba(var(--snkr-rgb,121,223,188),0.08); cursor: pointer;
      font-family: inherit; font-size: 13px; font-weight: 600; color: #171717; outline: none;
      transition: background .15s, border-color .15s;
    }
    .snkr-restart-btn:hover {
      background: rgba(var(--snkr-rgb,121,223,188),0.16);
      border-color: rgba(var(--snkr-rgb,121,223,188),0.6);
    }
    .snkr-divider-line {
      display: flex; align-items: center; gap: 10px; width: 100%;
      margin: 8px 0 4px; padding: 0 16px;
    }
    .snkr-divider-line::before, .snkr-divider-line::after {
      content: ''; flex: 1; height: 1px; background: rgba(23,23,23,0.08);
    }
    .snkr-divider-line span { font-size: 11px; color: #9e9690; white-space: nowrap; }

    /* ── Menu item: danger ───────────── */
    .snkr-menu-item-danger { color: #c0392b; }
    .snkr-menu-item-danger:hover { background: #fff5f5; }
    .snkr-menu-separator { height: 1px; background: rgba(23,23,23,0.06); margin: 3px 0; }

    /* ── History overlay ─────────────── */
    #snkr-hist-overlay {
      position: absolute; inset: 0; z-index: 30; background: #F8FAFC;
      display: none; flex-direction: column; border-radius: 24px; overflow: hidden;
    }
    #snkr-hist-overlay.open {
      display: flex;
      animation: snkr-slidein .22s cubic-bezier(0.34,1.4,0.64,1) both;
    }
    #snkr-hist-overlay-hdr {
      padding: 0 14px; height: 64px; display: flex; align-items: center; gap: 10px;
      border-bottom: 1px solid rgba(0,0,0,0.07); flex-shrink: 0; background: #fff;
    }
    #snkr-hist-overlay-back {
      background: #F1F5F9; border: none; cursor: pointer; color: #64748B;
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      padding: 0; outline: none; transition: background .15s; flex-shrink: 0;
    }
    #snkr-hist-overlay-back:hover { background: #E2E8F0; }
    #snkr-hist-overlay-title { font-size: 14px; font-weight: 700; color: #0F172A; flex: 1; }
    #snkr-hist-overlay-body { flex: 1; overflow-y: auto; padding: 10px 12px; }
    #snkr-hist-overlay-body::-webkit-scrollbar { width: 4px; }
    #snkr-hist-overlay-body::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
    .snkr-hist-ol-empty {
      text-align: center; padding: 48px 20px; color: #94A3B8; font-size: 13px;
    }
    .snkr-hist-ol-item {
      display: flex; align-items: center; gap: 10px; padding: 10px 12px;
      border-radius: 14px; cursor: pointer; background: none; border: none;
      width: 100%; text-align: left; font-family: inherit; transition: background .15s;
    }
    .snkr-hist-ol-item:hover { background: #F1F5F9; }
    .snkr-hist-ol-dot {
      width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
      background: rgba(var(--snkr-rgb,121,223,188),0.12);
      display: flex; align-items: center; justify-content: center; color: #64748B;
    }
    .snkr-hist-ol-content { flex: 1; min-width: 0; }
    .snkr-hist-ol-preview {
      font-size: 13px; font-weight: 600; color: #111827;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .snkr-hist-ol-time { font-size: 11px; color: #9e9690; margin-top: 2px; }
    .snkr-hist-ol-chevron { opacity: 0.22; flex-shrink: 0; }

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
    chat:     '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    x:        '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
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
    newchat:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    attach:   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
    mic:      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>',
    micoff:   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>',
    history:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.95L1 10"/><polyline points="12 7 12 12 15 15"/></svg>',
    endchat:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    fileicon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>',
    shield:   '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    sparkle:  '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg>',
    person:   '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/></svg>',
  };

  // ─── Page context bar ───────────────────────────────────────────────────────
  // Visible UI for page-context-awareness (setContext/clearContext): a small
  // dismissible chip shown above the chat, so the visitor can see (and expand)
  // what record the host app has attached to the conversation — not just have
  // it silently sent to the agent. One instance is mounted on the home screen
  // and one on the chat screen; _syncContextBar() keeps both in sync.

  function _titleCase(key) {
    return String(key).replace(/[_-]+/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function _contextLabel(ctx) {
    if (!ctx) return "";
    if (typeof ctx.summary === "string" && ctx.summary) return ctx.summary;
    var kind = ctx.type || ctx.entity_type || ctx.page || null;
    return kind ? _titleCase(kind) : "Page context";
  }

  function _contextRows(ctx) {
    if (!ctx || typeof ctx !== "object") return [];
    // "type"/"entity_type"/"page" already surface as the chip's label — skip
    // whichever one actually supplied it so the expanded detail isn't redundant.
    var kindKey = ctx.type ? "type" : ctx.entity_type ? "entity_type" : ctx.page ? "page" : null;
    var rows = [];
    Object.keys(ctx).forEach(function (key) {
      if (key === "summary" || key === kindKey) return;
      var value = ctx[key];
      if (value === null || value === undefined || value === "") return;
      if (typeof value === "object") return; // keep the chip flat/simple
      rows.push({ label: _titleCase(key), value: String(value) });
    });
    return rows;
  }

  function _buildContextBarEl() {
    var root = document.createElement("div");
    root.className = "snkr-ctx-bar";

    var row = document.createElement("div");
    row.className = "snkr-ctx-bar-row";

    var summaryBtn = document.createElement("button");
    summaryBtn.type = "button";
    summaryBtn.className = "snkr-ctx-summary";
    summaryBtn.setAttribute("aria-expanded", "false");

    var icon = document.createElement("span");
    icon.className = "snkr-ctx-icon";
    icon.innerHTML = I.fileicon;

    var label = document.createElement("span");
    label.className = "snkr-ctx-label";

    var chevron = document.createElement("span");
    chevron.className = "snkr-ctx-chevron";
    chevron.innerHTML = I.chevron;

    summaryBtn.appendChild(icon);
    summaryBtn.appendChild(label);
    summaryBtn.appendChild(chevron);

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "snkr-ctx-close";
    closeBtn.setAttribute("aria-label", "Clear page context");
    closeBtn.innerHTML = I.xsm;

    row.appendChild(summaryBtn);
    row.appendChild(closeBtn);

    var detail = document.createElement("div");
    detail.className = "snkr-ctx-detail";

    root.appendChild(row);
    root.appendChild(detail);

    return { root: root, summaryBtn: summaryBtn, label: label, closeBtn: closeBtn, detail: detail };
  }

  // ─── Widget ───────────────────────────────────────────────────────────────────

  function Widget(cfg) {
    this.widgetId       = cfg.widgetId;
    this.apiKey         = cfg.apiKey;
    this.apiUrl         = (cfg.apiUrl || "http://localhost:5001/api/v1").replace(/\/$/, "");
    this._user          = cfg.user || null;
    this._userHash      = cfg.userHash || null;
    // Stable session IDs:
    //   Identified users  → deterministic "eu_{user.id}" (same across all page loads)
    //   Anonymous users   → persisted random ID in localStorage so the same visitor
    //                        is recognised across page reloads without login
    if (this._user && this._user.id) {
      this.sessionId = "eu_" + this._user.id;
    } else {
      var _anonKey = "snkr_anon_" + (cfg.widgetId || "default");
      var _anonId = null;
      try { _anonId = localStorage.getItem(_anonKey); } catch (_) {}
      if (!_anonId) {
        _anonId = uid();
        try { localStorage.setItem(_anonKey, _anonId); } catch (_) {}
      }
      this.sessionId = _anonId;
    }
    this.conversationId = null;
    this._serverHistoryLoaded = false;
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
    this._historyKey    = "snkr_hist_"    + (cfg.widgetId || "default");
    this._visHandler    = null;       // Feature 5: stored visibility handler
    this._handoffBanner = null;       // HITL: active handoff banner element
    this._handoffPollInterval = null; // HITL: polling timer during active handoff
    this._seenHandoffMsgIds = {};     // HITL: dedup operator messages during polling
    this._cfg = {
      agentName: "AI Assistant",
      agentAvatar: "",
      agentDescription: "",
      welcomeMessage: "",
      placeholder: "Type a message…",
      primaryColor: "#79dfbc",
      suggestions: [],
      brandingText:      cfg.brandingText !== undefined ? cfg.brandingText : "Powered by AI",
      brandingUrl:       cfg.brandingUrl  || "",
      privacyPolicyUrl:  cfg.privacyPolicyUrl  || "",
      privacyPolicyText: cfg.privacyPolicyText || "By chatting, you agree to our",
    };
    this._attachedFile  = null;
    this._micActive        = false;
    this._recognition      = null;
    this._mediaRecorder    = null;
    this._recTimerInterval = null;
    this._recStartTime     = 0;
    this._recChunks        = [];
    this._chatEnded        = false;

    // Page-context-awareness: host-supplied context describing what the end user is
    // currently looking at. Defaults to a baseline derived from the current page, and
    // resets to that baseline on SPA navigation (see _navChangeHandler below) so stale
    // context from a previous page doesn't leak into a new one.
    this._pageContext = this._basePageContext();
    this._hasCustomContext = false; // true only once the host calls setContext()
    this._ctxBarOpen = false;       // shared expand/collapse state for the context bar(s)
    this._ctxBars = [];             // populated by _mount() — {root,summaryBtn,label,closeBtn,detail}
    var self = this;
    this._navChangeHandler = function () {
      self._clearPageContext();
    };
    global.addEventListener("synkoralocationchange", this._navChangeHandler);
    global.addEventListener("popstate", this._navChangeHandler);
    global.addEventListener("hashchange", this._navChangeHandler);

    this._mount();
    this._loadConfig();
  }

  Widget.prototype._basePageContext = function () {
    return { url: location.href, title: document.title };
  };

  Widget.prototype._mount = function () {
    var self = this;
    var color = "#79dfbc";

    var host = document.createElement("div");
    host.id = "snkr-" + this.widgetId;
    host.style.setProperty("--snkr-c",   color);
    host.style.setProperty("--snkr-cd",  darkenHex(color, 50));
    host.style.setProperty("--snkr-rgb", hexToRgb(color));
    host.style.setProperty("--snkr-fg",  luminance(color) > 0.4 ? "#0F172A" : "#fff");
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

    var homeCtxBar = _buildContextBarEl();
    home.appendChild(homeCtxBar.root);

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
          '<button class="snkr-menu-item" id="snkr-newchat-btn">' +
            I.newchat + '<span>New chat</span>' +
          '</button>' +
          '<button class="snkr-menu-item" id="snkr-viewhistory-btn">' +
            I.history + '<span>Recent chats</span>' +
          '</button>' +
          '<button class="snkr-menu-item" id="snkr-expand-btn">' +
            I.expand + '<span>Expand window</span>' +
          '</button>' +
          '<button class="snkr-menu-item" id="snkr-download-btn">' +
            I.download + '<span>Download transcript</span>' +
          '</button>' +
          '<div class="snkr-menu-separator"></div>' +
          '<button class="snkr-menu-item snkr-menu-item-danger" id="snkr-endchat-btn">' +
            I.endchat + '<span>End chat</span>' +
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

    // File preview chip (shown when file attached, above input box)
    var filePreview = document.createElement("div");
    filePreview.id = "snkr-file-preview";

    // Hidden file input
    var fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.id = "snkr-file-input";
    fileInput.style.display = "none";
    fileInput.accept = "image/*,.pdf,.doc,.docx,.txt,.csv,.xlsx";

    var inputBox = document.createElement("div");
    inputBox.id = "snkr-input-box";
    var input = document.createElement("textarea");
    input.id = "snkr-input";
    input.rows = 1;
    input.placeholder = "Message…";
    input.setAttribute("aria-label", "Message");
    var footerRow = document.createElement("div");
    footerRow.id = "snkr-footer-row";

    // Left: attach button
    var attachBtn = document.createElement("button");
    attachBtn.id = "snkr-attach-btn";
    attachBtn.setAttribute("aria-label", "Attach file");
    attachBtn.innerHTML = I.attach;

    // Right: mic + send
    var footerActions = document.createElement("div");
    footerActions.id = "snkr-footer-actions";

    // Recording indicator (shown while mic is active)
    var recIndicator = document.createElement("div");
    recIndicator.id = "snkr-rec-indicator";
    recIndicator.innerHTML = '<div class="snkr-rec-wave"><span></span><span></span><span></span><span></span><span></span></div><span id="snkr-rec-timer">0:00</span>';

    var micBtn = document.createElement("button");
    micBtn.id = "snkr-mic-btn";
    micBtn.setAttribute("aria-label", "Voice input");
    micBtn.innerHTML = I.mic;
    // Show mic for both SpeechRecognition (transcription) and MediaRecorder (voice notes)
    if (!window.SpeechRecognition && !window.webkitSpeechRecognition && !window.MediaRecorder) {
      micBtn.style.display = "none";
    }

    var sendBtn = document.createElement("button");
    sendBtn.id = "snkr-send";
    sendBtn.setAttribute("aria-label", "Send");
    sendBtn.innerHTML = I.send;

    footerActions.appendChild(recIndicator);
    footerActions.appendChild(micBtn);
    footerActions.appendChild(sendBtn);
    footerRow.appendChild(attachBtn);
    footerRow.appendChild(fileInput);
    footerRow.appendChild(footerActions);
    inputBox.appendChild(input);
    inputBox.appendChild(footerRow);
    footer.appendChild(filePreview);
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

    // Privacy bar (between header and body)
    var privacyBar = document.createElement("div");
    privacyBar.id = "snkr-privacy-bar";
    var privacyText = document.createElement("span");
    privacyText.id = "snkr-privacy-text";
    var privacyClose = document.createElement("button");
    privacyClose.id = "snkr-privacy-close";
    privacyClose.setAttribute("aria-label", "Dismiss");
    privacyClose.innerHTML = I.xsm;
    privacyBar.appendChild(privacyText);
    privacyBar.appendChild(privacyClose);

    // Chat chips (suggestions inside chat, shown when empty)
    var chatChips = document.createElement("div");
    chatChips.id = "snkr-chat-chips";

    // Context chip sits directly above the input (like a "Context: X" pill
    // anchored to the composer), not up near the header — so it's mounted
    // inside the footer, right before the file-preview/input box.
    var chatCtxBar = _buildContextBarEl();
    footer.insertBefore(chatCtxBar.root, footer.firstChild);

    chat.appendChild(header);
    chat.appendChild(privacyBar);
    chat.appendChild(body);
    chat.appendChild(chatChips);
    chat.appendChild(footer);
    chat.appendChild(branding);
    panel.appendChild(chat);

    // History overlay (covers full panel)
    var histOverlay = document.createElement("div");
    histOverlay.id = "snkr-hist-overlay";
    var histHdr = document.createElement("div");
    histHdr.id = "snkr-hist-overlay-hdr";
    var histBack = document.createElement("button");
    histBack.id = "snkr-hist-overlay-back";
    histBack.setAttribute("aria-label", "Back");
    histBack.innerHTML = I.back;
    var histTitle = document.createElement("div");
    histTitle.id = "snkr-hist-overlay-title";
    histTitle.textContent = "Recent chats";
    histHdr.appendChild(histBack);
    histHdr.appendChild(histTitle);
    var histBody = document.createElement("div");
    histBody.id = "snkr-hist-overlay-body";
    histOverlay.appendChild(histHdr);
    histOverlay.appendChild(histBody);
    panel.appendChild(histOverlay);

    shadow.appendChild(panel);

    // Save refs
    this._shadow      = shadow;
    this._toggle      = toggle;
    this._panel       = panel;
    this._home        = home;
    this._homeBody    = homeBody;
    this._chat        = chat;
    this._body        = body;
    this._loading     = loading;
    this._messages    = messages;
    this._input       = input;
    this._sendBtn     = sendBtn;
    this._expanded    = false;
    this._privacyBar  = privacyBar;
    this._privacyText = privacyText;
    this._chatChips   = chatChips;
    this._filePreview = filePreview;
    this._fileInput   = fileInput;
    this._attachBtn   = attachBtn;
    this._micBtn      = micBtn;
    this._recIndicator = recIndicator;
    this._histOverlay = histOverlay;
    this._histBody    = histBody;
    this._ctxBars     = [homeCtxBar, chatCtxBar];

    // Page context bar: click the summary to expand/collapse details,
    // click the close button to clear the attached context.
    this._ctxBars.forEach(function (bar) {
      bar.summaryBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        self._ctxBarOpen = !self._ctxBarOpen;
        self._syncContextBar();
      });
      bar.closeBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        self._clearPageContext();
      });
    });
    this._syncContextBar();

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
    // Menu: new chat
    shadow.getElementById("snkr-newchat-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      shadow.getElementById("snkr-menu-dropdown").classList.remove("open");
      self._newChat();
    });
    // Menu: recent chats
    shadow.getElementById("snkr-viewhistory-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      shadow.getElementById("snkr-menu-dropdown").classList.remove("open");
      self._openHistoryOverlay();
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
    // Menu: end chat
    shadow.getElementById("snkr-endchat-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      shadow.getElementById("snkr-menu-dropdown").classList.remove("open");
      self._endChat();
    });

    // Privacy bar: dismiss
    privacyClose.addEventListener("click", function (e) {
      e.stopPropagation();
      self._dismissPrivacy();
    });

    // Attach: open file picker
    attachBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      fileInput.click();
    });
    fileInput.addEventListener("change", function () {
      var file = fileInput.files && fileInput.files[0];
      if (file) { self._setAttachedFile(file); }
      fileInput.value = "";
    });

    // Mic: toggle voice — stop active recording or start new one
    micBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (!self._micActive) {
        self._startMic();
      } else if (self._mediaRecorder) {
        self._stopVoiceNote();
      } else {
        self._stopMic();
      }
    });

    // History overlay: back
    histBack.addEventListener("click", function (e) {
      e.stopPropagation();
      self._closeHistoryOverlay();
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
    this._buildHistorySection();
  };

  Widget.prototype._showChat = function () {
    this._home.style.display = "none";
    this._chat.classList.add("active");
    this._updatePrivacyBar();
    this._updateChatChips();
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

  // ── Chat history + new session ────────────────────────────────────────────────

  Widget.prototype._saveToHistory = function () {
    var rows = this._messages.querySelectorAll(".snkr-row");
    if (rows.length === 0) return;
    // Use server conversation_id when available; fall back to client session_id so
    // anonymous sessions are also persisted.
    var histId = this.conversationId || ("ses_" + this.sessionId);
    var messages = [];
    rows.forEach(function (row) {
      var bubble = row.querySelector(".snkr-bubble");
      if (!bubble) return;
      messages.push({
        role: row.classList.contains("user") ? "user" : "agent",
        html: bubble.innerHTML,
      });
    });
    // Use first user message as preview
    var preview = "";
    for (var i = 0; i < messages.length; i++) {
      if (messages[i].role === "user") {
        var tmp = document.createElement("div");
        tmp.innerHTML = messages[i].html;
        preview = (tmp.innerText || tmp.textContent || "").slice(0, 80);
        break;
      }
    }
    try {
      var history = JSON.parse(localStorage.getItem(this._historyKey) || "[]");
      // Replace existing entry for the same ID
      history = history.filter(function (h) { return h.conversationId !== histId; });
      history.unshift({ conversationId: histId, preview: preview, timestamp: Date.now(), messages: messages });
      history = history.slice(0, 8);
      localStorage.setItem(this._historyKey, JSON.stringify(history));
    } catch (_) {}
  };

  Widget.prototype._newChat = function () {
    this._saveToHistory();
    this.conversationId = null;
    this.sessionId = uid();
    this._sherlockEl = null;
    this._sherlockSteps = {};
    this._toolsUsed = 0;
    this._chatEnded = false;
    this._serverHistoryLoaded = false;
    this._clearAttachedFile();
    while (this._messages.firstChild) { this._messages.removeChild(this._messages.firstChild); }
    this._showHome();
  };

  Widget.prototype._resumeConversation = function (item) {
    this.conversationId = item.conversationId;
    while (this._messages.firstChild) { this._messages.removeChild(this._messages.firstChild); }
    var self = this;
    (item.messages || []).forEach(function (m) {
      var bubble = self._row(m.role === "user" ? "user" : "agent");
      bubble.innerHTML = m.html;
    });
    this._showChat();
    this._scroll();
  };

  // ── Server history (identified users) ────────────────────────────────────────

  Widget.prototype._loadServerHistory = function (forceChat) {
    var self = this;
    var url = this.apiUrl + "/widgets/chat/history?external_user_id=" + encodeURIComponent(this._user.id);

    fetch(url, {
      headers: { "X-Widget-API-Key": this.apiKey },
    })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (json) {
        var data = json && json.data;
        var msgs = data && Array.isArray(data.messages) ? data.messages : [];
        var convId = data && data.conversation_id;

        if (msgs.length === 0) {
          // No server history — show home screen as usual, unless the caller
          // explicitly asked to land straight in the (empty) chat view.
          if (forceChat) {
            self._showChat();
          } else {
            self._showHome();
            self._checkPioneer();
          }
          return;
        }

        // Populate messages from server
        while (self._messages.firstChild) { self._messages.removeChild(self._messages.firstChild); }
        msgs.forEach(function (m) {
          // DB roles are uppercase enum values: USER, ASSISTANT, OPERATOR
          var roleRaw = (m.role && m.role.value) ? m.role.value : String(m.role || "");
          var roleUp = roleRaw.toUpperCase();
          var isUser = roleUp === "USER";
          var isOperator = roleUp === "OPERATOR";
          if (isOperator) {
            var opBubble = self._row("agent");
            opBubble.innerHTML = "<strong style=\"font-size:11px;color:#6b7280;display:block;margin-bottom:3px;\">Support</strong>" + mdParse(m.content || "", false);
          } else {
            var bubble = self._row(isUser ? "user" : "agent");
            bubble.innerHTML = isUser ? esc(m.content || "") : mdParse(m.content || "", false);
          }
        });

        // Persist to localStorage so "Recent chats" shows this conversation
        if (convId) {
          self.conversationId = convId;
          self._saveToHistory();
        }

        // Go straight to chat — user has an existing conversation
        self._showChat();
        self._scroll();
      })
      .catch(function () {
        // Network error: fall back to home screen, unless the caller explicitly
        // asked to land straight in the (empty) chat view.
        if (forceChat) {
          self._showChat();
        } else {
          self._showHome();
          self._checkPioneer();
        }
      });
  };

  Widget.prototype._buildHistorySection = function () {
    var old = this._shadow.getElementById("snkr-history-section");
    if (old) old.parentNode.removeChild(old);
    var history = [];
    try { history = JSON.parse(localStorage.getItem(this._historyKey) || "[]"); } catch (_) {}

    var self = this;
    var section = document.createElement("div");
    section.id = "snkr-history-section";

    // Header row: label + "View all" button
    var labelRow = document.createElement("div");
    labelRow.className = "snkr-history-label-row";
    var label = document.createElement("div");
    label.className = "snkr-history-label";
    label.textContent = "Recent conversations";
    var viewAll = document.createElement("button");
    viewAll.className = "snkr-history-viewall";
    viewAll.textContent = "View all";
    viewAll.addEventListener("click", function (e) {
      e.stopPropagation();
      self._openHistoryOverlay();
    });
    labelRow.appendChild(label);
    labelRow.appendChild(viewAll);
    section.appendChild(labelRow);

    if (history.length === 0) {
      var empty = document.createElement("div");
      empty.className = "snkr-history-empty";
      empty.textContent = "No previous conversations yet.";
      section.appendChild(empty);
    } else {
      history.slice(0, 5).forEach(function (item) {
        var btn = document.createElement("button");
        btn.className = "snkr-history-item";
        var age = Date.now() - (item.timestamp || 0);
        var timeStr = age < 60000 ? "Just now"
          : age < 3600000 ? Math.floor(age / 60000) + "m ago"
          : age < 86400000 ? Math.floor(age / 3600000) + "h ago"
          : Math.floor(age / 86400000) + "d ago";
        btn.innerHTML =
          '<span class="snkr-history-dot"></span>' +
          '<span class="snkr-history-content">' +
            '<div class="snkr-history-preview">' + esc(item.preview || "Conversation") + '</div>' +
            '<div class="snkr-history-time">' + esc(timeStr) + '</div>' +
          '</span>' +
          '<span class="snkr-history-chevron">' + I.chevron + '</span>';
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          self._resumeConversation(item);
        });
        section.appendChild(btn);
      });
    }

    var homeBody = this._shadow.getElementById("snkr-home-body");
    if (homeBody) homeBody.appendChild(section);
  };

  // ── Privacy bar ───────────────────────────────────────────────────────────────

  Widget.prototype._privacyDismissKey = function () {
    return "snkr_priv_" + (this.widgetId || "default");
  };

  Widget.prototype._updatePrivacyBar = function () {
    var cfg = this._cfg;
    if (!cfg.privacyPolicyUrl) return; // Not configured — don't show
    var dismissed = false;
    try { dismissed = !!localStorage.getItem(this._privacyDismissKey()); } catch (_) {}
    if (dismissed) return;

    var text = cfg.privacyPolicyText || "By chatting, you agree to our";
    this._privacyText.innerHTML =
      I.shield + " " + esc(text) + ' <a href="' + esc(cfg.privacyPolicyUrl) +
      '" target="_blank" rel="noopener noreferrer">Privacy Policy</a>';
    this._privacyBar.classList.add("show");
  };

  Widget.prototype._dismissPrivacy = function () {
    this._privacyBar.classList.remove("show");
    try { localStorage.setItem(this._privacyDismissKey(), "1"); } catch (_) {}
  };

  // ── Page context bar ─────────────────────────────────────────────────────────

  Widget.prototype._setPageContext = function (context) {
    this._pageContext = context || null;
    this._hasCustomContext = !!context;
    this._ctxBarOpen = false; // start collapsed on every new context
    this._syncContextBar();
  };

  Widget.prototype._clearPageContext = function () {
    this._pageContext = this._basePageContext();
    this._hasCustomContext = false;
    this._ctxBarOpen = false;
    this._syncContextBar();
  };

  Widget.prototype._syncContextBar = function () {
    if (!this._ctxBars) return; // called before _mount() finished wiring refs
    var ctx = this._hasCustomContext ? this._pageContext : null;
    var label = _contextLabel(ctx);
    var rows = _contextRows(ctx);
    var open = this._ctxBarOpen;

    this._ctxBars.forEach(function (bar) {
      bar.root.classList.toggle("show", !!ctx);
      bar.root.classList.toggle("open", !!ctx && open);
      bar.label.textContent = label;
      bar.summaryBtn.setAttribute("aria-expanded", open ? "true" : "false");

      while (bar.detail.firstChild) bar.detail.removeChild(bar.detail.firstChild);
      rows.forEach(function (row) {
        var r = document.createElement("div");
        r.className = "snkr-ctx-row";
        var k = document.createElement("span");
        k.className = "snkr-ctx-row-k";
        k.textContent = row.label + ":";
        var v = document.createElement("span");
        v.className = "snkr-ctx-row-v";
        v.textContent = row.value;
        r.appendChild(k);
        r.appendChild(v);
        bar.detail.appendChild(r);
      });
    });
  };

  // ── Chat chips (in-chat suggestions) ─────────────────────────────────────────

  Widget.prototype._updateChatChips = function () {
    var chips = this._chatChips;
    // Only show if no messages yet and suggestions configured
    var hasMessages = this._messages.querySelectorAll(".snkr-row").length > 0;
    var suggestions = this._cfg.suggestions || [];
    if (hasMessages || suggestions.length === 0 || this._chatEnded) {
      chips.classList.remove("show");
      return;
    }
    // Rebuild
    while (chips.firstChild) { chips.removeChild(chips.firstChild); }

    var label = document.createElement("div");
    label.className = "snkr-chat-chips-label";
    label.textContent = "Suggestions";
    chips.appendChild(label);

    var row = document.createElement("div");
    row.className = "snkr-chat-chips-row";
    var self = this;
    suggestions.slice(0, 6).forEach(function (s) {
      var btn = document.createElement("button");
      btn.className = "snkr-chat-chip-btn";
      btn.textContent = s.title || s;
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        chips.classList.remove("show");
        self._input.value = s.title || s;
        self._input.dispatchEvent(new Event("input"));
        self._send();
      });
      row.appendChild(btn);
    });
    chips.appendChild(row);
    chips.classList.add("show");
  };

  // ── End chat ──────────────────────────────────────────────────────────────────

  Widget.prototype._endChat = function () {
    if (this._chatEnded) return;
    this._chatEnded = true;
    this._saveToHistory();
    this._chatChips.classList.remove("show");

    // Show divider + ended banner in messages area
    var divider = document.createElement("div");
    divider.className = "snkr-divider-line";
    divider.innerHTML = "<span>Chat ended</span>";
    this._messages.appendChild(divider);

    var wrap = document.createElement("div");
    wrap.className = "snkr-ended-wrap";
    var self = this;
    wrap.innerHTML =
      '<div class="snkr-ended-ring">' + I.endchat + '</div>' +
      '<div class="snkr-ended-title">This conversation has ended</div>' +
      '<div class="snkr-ended-sub">Your chat history is saved above.</div>';
    var restartBtn = document.createElement("button");
    restartBtn.className = "snkr-restart-btn";
    restartBtn.innerHTML = I.newchat + " <span>Start new conversation</span>";
    restartBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      self._newChat();
      self._showChat();
    });
    wrap.appendChild(restartBtn);
    this._messages.appendChild(wrap);
    this._scroll();

    // Disable input
    this._input.disabled = true;
    this._sendBtn.disabled = true;
  };

  // ── History overlay ───────────────────────────────────────────────────────────

  Widget.prototype._openHistoryOverlay = function () {
    var self = this;
    var body = this._histBody;
    // Rebuild list
    while (body.firstChild) { body.removeChild(body.firstChild); }

    var history = [];
    try { history = JSON.parse(localStorage.getItem(this._historyKey) || "[]"); } catch (_) {}

    if (history.length === 0) {
      var empty = document.createElement("div");
      empty.className = "snkr-hist-ol-empty";
      empty.textContent = "No previous conversations yet.";
      body.appendChild(empty);
    } else {
      history.forEach(function (item) {
        var age = Date.now() - (item.timestamp || 0);
        var timeStr = age < 60000 ? "Just now"
          : age < 3600000 ? Math.floor(age / 60000) + "m ago"
          : age < 86400000 ? Math.floor(age / 3600000) + "h ago"
          : Math.floor(age / 86400000) + "d ago";

        var btn = document.createElement("button");
        btn.className = "snkr-hist-ol-item";
        btn.innerHTML =
          '<div class="snkr-hist-ol-dot">' + I.history + '</div>' +
          '<div class="snkr-hist-ol-content">' +
            '<div class="snkr-hist-ol-preview">' + esc(item.preview || "Conversation") + '</div>' +
            '<div class="snkr-hist-ol-time">' + esc(timeStr) + '</div>' +
          '</div>' +
          '<span class="snkr-hist-ol-chevron">' + I.chevron + '</span>';
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          self._closeHistoryOverlay();
          self._resumeConversation(item);
        });
        body.appendChild(btn);
      });
    }

    this._histOverlay.classList.add("open");
  };

  Widget.prototype._closeHistoryOverlay = function () {
    this._histOverlay.classList.remove("open");
  };

  // ── File attachment ───────────────────────────────────────────────────────────

  Widget.prototype._setAttachedFile = function (file) {
    this._attachedFile = file;
    var preview = this._filePreview;
    while (preview.firstChild) { preview.removeChild(preview.firstChild); }

    var chip = document.createElement("div");
    chip.className = "snkr-file-chip";
    var self = this;
    chip.innerHTML =
      '<span class="snkr-file-chip-icon">' + I.fileicon + '</span>' +
      '<span class="snkr-file-chip-name">' + esc(file.name) + '</span>';
    var removeBtn = document.createElement("button");
    removeBtn.className = "snkr-file-remove";
    removeBtn.setAttribute("aria-label", "Remove");
    removeBtn.innerHTML = I.xsm;
    removeBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      self._clearAttachedFile();
    });
    chip.appendChild(removeBtn);
    preview.appendChild(chip);
    preview.classList.add("show");
  };

  Widget.prototype._clearAttachedFile = function () {
    this._attachedFile = null;
    this._filePreview.classList.remove("show");
    while (this._filePreview.firstChild) {
      this._filePreview.removeChild(this._filePreview.firstChild);
    }
  };

  // ── Voice input ───────────────────────────────────────────────────────────────

  Widget.prototype._startRecIndicator = function () {
    var self = this;
    this._recStartTime = Date.now();
    this._recIndicator.classList.add("show");
    var timerEl = this._shadow.getElementById("snkr-rec-timer");
    this._recTimerInterval = setInterval(function () {
      var secs = Math.floor((Date.now() - self._recStartTime) / 1000);
      var m = Math.floor(secs / 60);
      var s = secs % 60;
      if (timerEl) timerEl.textContent = m + ":" + (s < 10 ? "0" : "") + s;
    }, 500);
  };

  Widget.prototype._stopRecIndicator = function () {
    this._recIndicator.classList.remove("show");
    if (this._recTimerInterval) {
      clearInterval(this._recTimerInterval);
      this._recTimerInterval = null;
    }
    var timerEl = this._shadow.getElementById("snkr-rec-timer");
    if (timerEl) timerEl.textContent = "0:00";
  };

  Widget.prototype._startMic = function () {
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    // If SpeechRecognition is available use it for real-time transcription.
    // Otherwise fall back to MediaRecorder to capture a voice note.
    if (SpeechRecognition) {
      this._startSpeechRecognition(SpeechRecognition);
    } else {
      this._startVoiceNote();
    }
  };

  Widget.prototype._startSpeechRecognition = function (SpeechRecognition) {
    if (!SpeechRecognition) return;
    // SpeechRecognition manages its own mic permission prompt — no getUserMedia
    // pre-flight needed. The onerror handler falls back to MediaRecorder if the
    // speech service is blocked or unavailable.
    this._doSpeechRecognition(SpeechRecognition);
  };

  Widget.prototype._doSpeechRecognition = function (SpeechRecognition) {
    var self = this;
    var rec = new SpeechRecognition();
    // continuous = true: keep listening until the user clicks stop.
    // With false the browser silently auto-stops after a brief pause.
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = navigator.language || "en-US";

    rec.onstart = function () {
      self._micActive = true;
      self._micBtn.classList.add("recording");
      self._micBtn.innerHTML = I.micoff;
      self._micBtn.setAttribute("aria-label", "Stop recording");
      self._startRecIndicator();
    };

    rec.onresult = function (e) {
      var transcript = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript;
      }
      self._input.value = transcript;
      self._input.style.height = "auto";
      self._input.style.height = Math.min(self._input.scrollHeight, 120) + "px";
      self._sendBtn.classList.toggle("snkr-send-active", transcript.trim().length > 0);
    };

    rec.onerror = function (e) {
      console.warn("[SynkoraWidget] SpeechRecognition error:", e.error);
      // no-speech is benign — keep listening, don't reset the UI
      if (e.error === "no-speech") return;
      // Null ref BEFORE stopping so onend doesn't loop back in
      self._recognition = null;
      try { rec.stop(); } catch (_) {}
      self._stopMicUI();
      // For any SpeechRecognition denial (not-allowed on HTTP, service-not-allowed,
      // network error), fall back to MediaRecorder voice note. MediaRecorder uses
      // getUserMedia which works on http://localhost. If the mic is truly blocked
      // at the OS/browser level, getUserMedia will fail and show the right message.
      self._startVoiceNote();
    };

    rec.onend = function () {
      // onend fires after manual stop AND after onerror.
      // If _micActive is already false, cleanup already ran — just auto-send.
      if (self._micActive) {
        self._recognition = null;
        self._stopMicUI();
      }
      if (self._input.value.trim()) { self._send(); }
    };

    this._recognition = rec;
    try {
      rec.start();
    } catch (_) {
      this._recognition = null;
      this._stopMicUI();
    }
  };

  Widget.prototype._stopMic = function () {
    // Null the reference first so the onend callback doesn't re-enter
    var rec = this._recognition;
    this._recognition = null;
    this._stopMicUI();
    if (rec) { try { rec.stop(); } catch (_) {} }
    // Auto-send whatever was transcribed
    if (this._input.value.trim()) { this._send(); }
  };

  Widget.prototype._stopMicUI = function () {
    this._micActive = false;
    this._micBtn.classList.remove("recording");
    this._micBtn.innerHTML = I.mic;
    this._micBtn.setAttribute("aria-label", "Voice input");
    this._stopRecIndicator();
  };

  Widget.prototype._showMicBlocked = function () {
    // Microphone blocked — could be OS-level (macOS System Settings → Privacy →
    // Microphone → enable the browser) or browser-level (site settings).
    var isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
    var msg = isMac
      ? "Allow mic: System Settings \u2192 Privacy \u2192 Microphone \u2192 enable your browser"
      : "Microphone blocked \u2014 check browser or OS permissions";
    var orig = this._input.placeholder;
    this._input.placeholder = msg;
    var self = this;
    setTimeout(function () { self._input.placeholder = self._cfg.placeholder || orig; }, 6000);
  };

  // ── Voice note (MediaRecorder fallback) ───────────────────────────────────────

  Widget.prototype._startVoiceNote = function () {
    if (!window.MediaRecorder || !navigator.mediaDevices) return;
    var self = this;

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {

      self._recChunks = [];
      var mr = new window.MediaRecorder(stream);
      self._mediaRecorder = mr;
      mr.ondataavailable = function (e) {
        if (e.data && e.data.size > 0) self._recChunks.push(e.data);
      };
      mr.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        self._stopMicUI();
        var blob = new Blob(self._recChunks, { type: mr.mimeType || "audio/webm" });
        var duration = Math.round((Date.now() - self._recStartTime) / 1000);
        var url = URL.createObjectURL(blob);
        self._addVoiceNoteBubble(url, duration);
        self._mediaRecorder = null;
        self._recChunks = [];
      };
      mr.start();
      self._micActive = true;
      self._micBtn.classList.add("recording");
      self._micBtn.innerHTML = I.micoff;
      self._micBtn.setAttribute("aria-label", "Stop recording");
      self._startRecIndicator();
    }).catch(function (err) {
      console.warn("[SynkoraWidget] getUserMedia error:", err && err.name, err && err.message);
      self._showMicBlocked();
    });
  };

  Widget.prototype._stopVoiceNote = function () {
    if (this._mediaRecorder && this._mediaRecorder.state !== "inactive") {
      this._mediaRecorder.stop();
    }
  };

  Widget.prototype._addVoiceNoteBubble = function (url, durationSecs) {
    var self = this;
    var bubble = this._row("user");
    var m = Math.floor(durationSecs / 60);
    var s = durationSecs % 60;
    var label = "Voice note · " + m + ":" + (s < 10 ? "0" : "") + s;
    var wrapper = document.createElement("div");
    wrapper.className = "snkr-audio-msg";
    var audio = document.createElement("audio");
    audio.controls = true;
    audio.src = url;
    var lbl = document.createElement("span");
    lbl.className = "snkr-audio-label";
    lbl.textContent = label;
    wrapper.appendChild(audio);
    wrapper.appendChild(lbl);
    bubble.appendChild(wrapper);
    this._scroll();
    // Also send transcription prompt to agent
    self._sendVoiceNoteToAgent(label);
  };

  Widget.prototype._sendVoiceNoteToAgent = function (label) {
    // Send a text proxy to the agent so the conversation continues
    var self = this;
    this._typingEl = this._typing();
    this._busy(true);
    this._agentText = "";
    this._agentBubble = null;
    this._toolsUsed = 0;
    fetch(this.apiUrl + "/widgets/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Widget-API-Key": this.apiKey },
      body: JSON.stringify({
        message: "[" + label + "]",
        session_id: this.sessionId,
        conversation_id: this.conversationId || undefined,
        user: this._user || undefined,
        user_hash: this._userHash || undefined,
      }),
    }).then(function (res) {
      if (!res.ok || !res.body) { self._finish(); return; }
      var reader = res.body.getReader();
      var dec = new TextDecoder();
      var buf = "";
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) { self._finish(); return; }
          buf += dec.decode(r.value, { stream: true });
          var parts = buf.split("\n\n"); buf = parts.pop();
          parts.forEach(function (p) {
            var line = p.replace(/^data:\s*/, "");
            if (!line) return;
            try { self._processEvent(JSON.parse(line)); } catch (_) {}
          });
          return pump();
        });
      }
      return pump();
    }).catch(function () { self._finish(); });
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
        var theme = data.theme || {};
        self._applyConfig({
          agentName:         data.agent_name || "",
          agentAvatar:       data.agent_avatar || "",
          agentDescription:  data.agent_description || "",
          welcomeMessage:    theme.welcome_message || "",
          placeholder:       theme.placeholder || "",
          primaryColor:      theme.primary_color || "",
          suggestions:       data.suggestion_prompts || [],
          privacyPolicyUrl:  theme.privacy_policy_url || "",
          privacyPolicyText: theme.privacy_policy_text || "",
          // branding_text can be a string OR false (to hide the bar entirely)
          brandingText:      theme.branding_text !== undefined ? theme.branding_text : undefined,
          brandingUrl:       theme.branding_url  || "",
        });
      })
      .catch(function () { self._applyConfig({}); });
  };

  Widget.prototype._applyConfig = function (c) {
    var self = this;
    var cfg = this._cfg;
    cfg.agentName         = c.agentName         || "AI Assistant";
    cfg.agentAvatar       = c.agentAvatar       || "";
    cfg.agentDescription  = c.agentDescription  || "";
    cfg.welcomeMessage    = c.welcomeMessage    || ("Hi there 👋\nHow can we help?");
    cfg.placeholder       = c.placeholder       || "Message…";
    cfg.primaryColor      = c.primaryColor      || "#79dfbc";
    cfg.suggestions       = Array.isArray(c.suggestions) ? c.suggestions : [];
    if (c.privacyPolicyUrl)  cfg.privacyPolicyUrl  = c.privacyPolicyUrl;
    if (c.privacyPolicyText) cfg.privacyPolicyText = c.privacyPolicyText;
    // Branding: server value overrides JS init value when present
    if (c.brandingText !== undefined) cfg.brandingText = c.brandingText;
    if (c.brandingUrl)               cfg.brandingUrl  = c.brandingUrl;
    // Update both branding elements now that we have config
    var self = this;
    ["snkr-branding", "snkr-home-branding"].forEach(function (id) {
      var el = self._shadow.getElementById(id);
      if (!el) return;
      if (cfg.brandingText === false) {
        el.innerHTML = "";
      } else {
        var bText = cfg.brandingText || "Powered by AI";
        var bUrl  = cfg.brandingUrl;
        el.innerHTML = bUrl
          ? bText.replace(/^(Powered by )(.+)$/, '$1<a href="' + esc(bUrl) + '" target="_blank" rel="noopener">$2</a>')
          : esc(bText);
      }
    });

    var color = cfg.primaryColor;
    this._host.style.setProperty("--snkr-c",   color);
    this._host.style.setProperty("--snkr-cd",  darkenHex(color, 50));
    this._host.style.setProperty("--snkr-rgb", hexToRgb(color));
    this._host.style.setProperty("--snkr-fg",  luminance(color) > 0.4 ? "#0F172A" : "#fff");

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

  // opts.screen === 'chat' lets a host-app trigger (e.g. a "Send us a message"
  // button next to a record the visitor is looking at) open straight into the
  // conversation view instead of the home tab — typically paired with
  // setContext() so the agent already knows what the visitor means by "this".
  Widget.prototype.open = function (opts) {
    var forceChat = !!(opts && opts.screen === "chat");
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

    // For identified users: load server history on first open.
    // This restores conversations across devices/browsers automatically.
    if (this._user && this._user.id && !this._serverHistoryLoaded && this._messages.children.length === 0) {
      this._serverHistoryLoaded = true; // set now to prevent double-fetch
      this._loadServerHistory(forceChat);
      return; // _loadServerHistory decides what screen to show after fetch
    }

    if (forceChat) {
      this._showChat();
      return;
    }

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
    this._saveToHistory();
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

    var inner = document.createElement("div");
    inner.className = "snkr-row-inner";

    var bubble = document.createElement("div");
    bubble.className = "snkr-bubble";

    if (type === "agent") {
      var agentAv = document.createElement("div");
      agentAv.className = "snkr-msg-avatar snkr-agent-avatar";
      agentAv.innerHTML = I.sparkle;
      inner.appendChild(agentAv);
      inner.appendChild(bubble);
    } else if (type === "user") {
      inner.appendChild(bubble);
      var userAv = document.createElement("div");
      userAv.className = "snkr-msg-avatar snkr-user-avatar";
      userAv.innerHTML = I.person;
      inner.appendChild(userAv);
    } else {
      inner.appendChild(bubble);
    }
    row.appendChild(inner);

    // Show "AgentName · time" below agent bubbles, just timestamp below user
    if (type !== "error") {
      var ts = document.createElement("div");
      ts.className = "snkr-ts";
      if (type === "agent") {
        ts.textContent = this._cfg.agentName + " · " + timeNow();
      } else {
        ts.textContent = timeNow();
      }
      row.appendChild(ts);
    }

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
    var inner = document.createElement("div");
    inner.className = "snkr-row-inner";
    var agentAv = document.createElement("div");
    agentAv.className = "snkr-msg-avatar snkr-agent-avatar";
    agentAv.innerHTML = I.sparkle;
    inner.appendChild(agentAv);
    var dots = document.createElement("div");
    dots.id = "snkr-typing";
    dots.innerHTML = "<span></span><span></span><span></span>";
    inner.appendChild(dots);
    wrap.appendChild(inner);
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
    if (!text || this.streaming || this._chatEnded) return;

    // Hide chat chips once user sends first message
    this._chatChips.classList.remove("show");

    // Append attached file reference to message text
    if (this._attachedFile) {
      text = text + "\n\n[Attached: " + this._attachedFile.name + "]";
      this._clearAttachedFile();
    }

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
        page_context: this._pageContext || undefined,
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
    } else if (evt.type === "approval_required") {
      this._showApprovalCard(evt);
    } else if (evt.type === "handoff_initiated") {
      this._showHandoffBanner(evt);
    } else if (evt.type === "handoff_resolved") {
      this._hideHandoffBanner();
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
    // Persist the completed turn (user + agent) to localStorage so history
    // is always up-to-date, even if the user never closes the widget.
    this._saveToHistory();
  };

  // ─── HITL: Approval + Handoff ─────────────────────────────────────────────────

  Widget.prototype._showApprovalCard = function (evt) {
    var self = this;
    var approvalId = evt.approval_id;
    var toolName = evt.tool_name || "action";
    var toolArgs = evt.tool_args || {};

    // Build card HTML
    var argsText = JSON.stringify(toolArgs, null, 2);
    var card = document.createElement("div");
    card.className = "snkr-approval-card";
    card.setAttribute("data-approval-id", approvalId);
    card.innerHTML =
      '<div class="snkr-approval-header">Approval required: <code>' + esc(toolName) + '</code></div>' +
      '<pre class="snkr-approval-args">' + esc(argsText) + '</pre>' +
      '<div class="snkr-approval-actions">' +
      '<button class="snkr-approval-btn snkr-approve">Approve</button>' +
      '<button class="snkr-approval-btn snkr-reject">Reject</button>' +
      '</div>';

    this._messages.appendChild(card);
    this._scroll();

    // Wire buttons
    card.querySelector(".snkr-approve").addEventListener("click", function () {
      self._respondApproval(approvalId, "approved", card);
    });
    card.querySelector(".snkr-reject").addEventListener("click", function () {
      self._respondApproval(approvalId, "rejected", card);
    });
  };

  Widget.prototype._respondApproval = function (approvalId, decision, card) {
    var self = this;
    // Disable buttons immediately to prevent double-clicks
    var btns = card.querySelectorAll(".snkr-approval-btn");
    btns.forEach(function (b) { b.disabled = true; });

    fetch(this.apiUrl + "/widgets/chat/approvals/" + encodeURIComponent(approvalId) + "/respond", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Widget-API-Key": self.apiKey,
      },
      body: JSON.stringify({ decision: decision }),
    }).then(function () {
      card.innerHTML = '<div class="snkr-approval-done">' +
        (decision === "approved" ? "\u2713 Approved \u2014 action will proceed." : "\u2717 Rejected.") +
        "</div>";
    }).catch(function () {
      card.innerHTML = '<div class="snkr-approval-done">Request failed.</div>';
    });
  };

  Widget.prototype._showHandoffBanner = function (evt) {
    if (this._handoffBanner) return; // already shown
    var self = this;
    var banner = document.createElement("div");
    banner.className = "snkr-handoff-banner";
    banner.innerHTML =
      '<span class="snkr-handoff-icon">\uD83D\uDC64</span> ' +
      '<span>Connected to support. A human agent will respond shortly.</span>';
    this._messages.appendChild(banner);
    this._handoffBanner = banner;
    this._scroll();
    // Disable input while in handoff
    if (this._input) this._input.disabled = true;
    if (this._sendBtn) this._sendBtn.disabled = true;
    // Poll for operator replies every 4 seconds
    this._startHandoffPolling();
  };

  Widget.prototype._hideHandoffBanner = function () {
    this._stopHandoffPolling();
    if (this._handoffBanner) {
      var el = this._handoffBanner;
      el.style.opacity = "0";
      el.style.transition = "opacity 0.4s";
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 400);
      this._handoffBanner = null;
    }
    // Re-enable input
    if (this._input) this._input.disabled = false;
    if (this._sendBtn) this._sendBtn.disabled = false;
    // Show "Support session ended" message
    var note = document.createElement("div");
    note.className = "snkr-system-note";
    note.textContent = "Support session ended. You are now chatting with the AI assistant again.";
    if (this._messages) { this._messages.appendChild(note); this._scroll(); }
  };

  // Track the last-seen message ID to avoid re-rendering existing messages
  Widget.prototype._startHandoffPolling = function () {
    var self = this;
    if (this._handoffPollInterval) return;
    this._handoffPollInterval = setInterval(function () {
      var convId = self.conversationId;
      if (!convId) return;
      fetch(self.apiUrl + "/widgets/chat/history?conversation_id=" + encodeURIComponent(convId), {
        headers: { "X-Widget-API-Key": self.apiKey },
      })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          // WidgetResponse wraps payload in .data; fall back to top-level .messages
          var msgs = (data && data.data && Array.isArray(data.data.messages))
            ? data.data.messages
            : (data && Array.isArray(data.messages) ? data.messages : null);
          if (!msgs) return;
          // Find operator messages newer than last known
          msgs.forEach(function (m) {
            var roleRaw = (m.role && m.role.value) ? m.role.value : String(m.role || "");
            if (roleRaw.toUpperCase() !== "OPERATOR") return;
            var msgId = m.id || m.message_id || "";
            if (!msgId || self._seenHandoffMsgIds[msgId]) return;
            self._seenHandoffMsgIds[msgId] = true;
            var opBubble = self._row("agent");
            opBubble.innerHTML = "<strong style=\"font-size:11px;color:#6b7280;display:block;margin-bottom:3px;\">Support</strong>" + (m.content || "");
          });
        })
        .catch(function () {});
    }, 4000);
  };

  Widget.prototype._stopHandoffPolling = function () {
    if (this._handoffPollInterval) {
      clearInterval(this._handoffPollInterval);
      this._handoffPollInterval = null;
    }
    this._seenHandoffMsgIds = {};
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
    // Pass { screen: "chat" } to open straight into the conversation view
    // instead of the home tab — e.g. from a "Send us a message" button next
    // to a record on your own page, typically paired with setContext():
    //
    //   SynkoraWidget.setContext("widget_123", { type: "rider", summary: "..." });
    //   SynkoraWidget.open("widget_123", { screen: "chat" });
    open:  function (id, opts) { var w = this._i[id]; if (w) w.open(opts); },
    close: function (id) { var w = this._i[id]; if (w) w.close(); },
    // Page-context-awareness: push arbitrary, schema-less context describing what the
    // end user is currently looking at, so the agent understands what they mean by
    // "this" / "that" without the user having to spell it out.
    //
    //   SynkoraWidget.setContext("widget_123", {
    //     type: "user_detail",
    //     entity_id: "usr_456",
    //     summary: "Viewing user Jane Doe's profile (Pro plan, joined 2024-01-15)"
    //   });
    //
    // Context persists across messages until replaced or cleared, and is automatically
    // reset to a baseline (current URL/title) on same-page SPA navigation.
    setContext: function (id, context) {
      var w = this._i[id];
      if (w) w._setPageContext(context);
    },
    // Reset page context back to the baseline derived from the current URL/title.
    //   SynkoraWidget.clearContext("widget_123");
    clearContext: function (id) {
      var w = this._i[id];
      if (w) w._clearPageContext();
    },
  };

})(window);
