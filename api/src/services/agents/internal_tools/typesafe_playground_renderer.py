"""
Renders a self-contained HTML page for a TypeSafe AI Playground.

The page is pure static HTML/CSS/JS (no build step, no external JS deps) —
it posts the visitor's text to the public evaluate endpoint and renders
whatever noul/choice/score answers come back. Generic over any question set;
nothing here is specific to one use case.
"""

from __future__ import annotations

import html as html_module
import json
from typing import Any

MAX_PLAYGROUND_TEXT_LEN = 4000


def _esc(text: str) -> str:
    return html_module.escape(str(text), quote=True)


def _safe_json(obj: Any) -> str:
    """JSON for embedding inside a <script> block — neutralize '</script>' injection."""
    return json.dumps(obj).replace("</", "<\\/")


def render_playground_html(page_id: str, spec: dict[str, Any], api_base_url: str) -> str:
    title = spec["title"]
    description = spec["description"]
    input_label = spec["input_label"]
    theme_emoji = spec.get("theme_emoji", "🔮")

    evaluate_url = f"{api_base_url}/api/v1/public/typesafe-playground/{page_id}/evaluate"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
  :root {{
    --bg: #0f0f13;
    --card: #1a1a21;
    --card-border: #2a2a34;
    --text: #f2f1ee;
    --text-dim: #9a97a3;
    --accent: #a78bfa;
    --accent-soft: rgba(167,139,250,0.15);
    --good: #4ade80;
    --bad: #f87171;
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text); font-family: var(--font);
    min-height: 100vh; display: flex; justify-content: center; padding: 48px 16px;
  }}
  .wrap {{ width: 100%; max-width: 560px; }}
  .emoji {{ font-size: 42px; text-align: center; margin-bottom: 8px; }}
  h1 {{ font-size: 26px; text-align: center; margin: 0 0 8px; }}
  p.desc {{ color: var(--text-dim); text-align: center; margin: 0 0 32px; line-height: 1.5; }}
  label {{ display: block; font-size: 13px; font-weight: 600; color: var(--text-dim); margin-bottom: 8px; }}
  textarea {{
    width: 100%; min-height: 120px; background: var(--card); border: 1px solid var(--card-border);
    border-radius: 12px; padding: 14px 16px; color: var(--text); font-family: var(--font);
    font-size: 15px; resize: vertical; outline: none;
  }}
  textarea:focus {{ border-color: var(--accent); }}
  .charcount {{ text-align: right; font-size: 12px; color: var(--text-dim); margin-top: 6px; }}
  button.judge {{
    width: 100%; margin-top: 18px; padding: 14px; border: none; border-radius: 12px;
    background: var(--accent); color: #17131f; font-weight: 700; font-size: 15px;
    cursor: pointer; transition: opacity 0.15s;
  }}
  button.judge:disabled {{ opacity: 0.5; cursor: default; }}
  button.judge:not(:disabled):hover {{ opacity: 0.9; }}
  #error {{
    display: none; margin-top: 16px; padding: 12px 16px; border-radius: 10px;
    background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.3);
    color: var(--bad); font-size: 14px;
  }}
  #results {{ margin-top: 28px; display: none; }}
  .answer-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 12px;
    padding: 16px 18px; margin-bottom: 12px; animation: rise 0.35s ease both;
  }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .answer-key {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim); margin-bottom: 8px; }}
  .answer-value {{ font-size: 18px; font-weight: 700; }}
  .answer-conf {{ font-size: 12px; color: var(--text-dim); margin-top: 2px; }}
  .bar-row {{ display: flex; align-items: center; gap: 8px; margin-top: 6px; font-size: 12px; color: var(--text-dim); }}
  .bar-track {{ flex: 1; height: 6px; border-radius: 3px; background: var(--card-border); overflow: hidden; }}
  .bar-fill {{ height: 100%; background: var(--accent); }}
  footer {{ text-align: center; margin-top: 36px; font-size: 12px; color: var(--text-dim); }}
  footer a {{ color: var(--accent); text-decoration: none; }}
  .spinner {{
    display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(23,19,31,0.3);
    border-top-color: #17131f; border-radius: 50%; animation: spin 0.7s linear infinite; margin-right: 8px;
    vertical-align: -2px;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="emoji">{_esc(theme_emoji)}</div>
  <h1>{_esc(title)}</h1>
  <p class="desc">{_esc(description)}</p>

  <label for="input">{_esc(input_label)}</label>
  <textarea id="input" maxlength="{MAX_PLAYGROUND_TEXT_LEN}" placeholder="Paste text here..."></textarea>
  <div class="charcount"><span id="charcount">0</span> / {MAX_PLAYGROUND_TEXT_LEN}</div>

  <button class="judge" id="judgeBtn">Judge it</button>

  <div id="error"></div>
  <div id="results"></div>

  <footer>Powered by <a href="https://synkora.ai" target="_blank" rel="noopener">Synkora</a> agents × TypeSafe AI</footer>
</div>
<script>
(function() {{
  var EVALUATE_URL = {_safe_json(evaluate_url)};
  var input = document.getElementById('input');
  var charcount = document.getElementById('charcount');
  var btn = document.getElementById('judgeBtn');
  var errorBox = document.getElementById('error');
  var results = document.getElementById('results');

  input.addEventListener('input', function() {{
    charcount.textContent = input.value.length;
  }});

  function bar(pct) {{
    return '<div class="bar-track"><div class="bar-fill" style="width:' + Math.round(pct * 100) + '%"></div></div>';
  }}

  function renderAnswer(key, answer) {{
    var type = answer.type || '';
    var html = '<div class="answer-card"><div class="answer-key">' + escapeHtml(key) + '</div>';

    if (type === 'noul') {{
      var prob = typeof answer.noul === 'number' ? answer.noul : 0.5;
      var label = prob >= 0.5 ? 'Yes' : 'No';
      var icon = prob >= 0.5 ? '✓' : '✗';
      html += '<div class="answer-value">' + icon + ' ' + label + '</div>';
      html += '<div class="bar-row">' + bar(prob) + '<span>' + Math.round(prob * 100) + '%</span></div>';
    }} else if (type === 'choice') {{
      var choice = answer.choice || '—';
      var conf = typeof answer.confidence === 'number' ? answer.confidence : 0;
      html += '<div class="answer-value">' + escapeHtml(String(choice)) + '</div>';
      html += '<div class="answer-conf">' + Math.round(conf * 100) + '% confident</div>';
      var probs = answer.probabilities || {{}};
      var entries = Object.keys(probs).map(function(k) {{ return [k, probs[k]]; }});
      entries.sort(function(a, b) {{ return b[1] - a[1]; }});
      entries.slice(0, 5).forEach(function(pair) {{
        html += '<div class="bar-row">' + bar(pair[1]) + '<span>' + escapeHtml(pair[0]) + ' ' + Math.round(pair[1] * 100) + '%</span></div>';
      }});
    }} else if (type === 'score') {{
      var score = typeof answer.score === 'number' ? answer.score : 0;
      var sconf = typeof answer.confidence === 'number' ? answer.confidence : 0;
      html += '<div class="answer-value">' + score.toFixed(2) + '</div>';
      html += '<div class="answer-conf">' + Math.round(sconf * 100) + '% confident</div>';
      html += '<div class="bar-row">' + bar(score) + '</div>';
    }} else {{
      html += '<div class="answer-value">' + escapeHtml(JSON.stringify(answer)) + '</div>';
    }}

    html += '</div>';
    return html;
  }}

  function escapeHtml(str) {{
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }}

  async function judge() {{
    var text = input.value.trim();
    errorBox.style.display = 'none';
    results.style.display = 'none';
    results.innerHTML = '';

    if (!text) {{
      errorBox.textContent = 'Please enter some text first.';
      errorBox.style.display = 'block';
      return;
    }}

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Judging...';

    try {{
      var resp = await fetch(EVALUATE_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ text: text }})
      }});
      var data = await resp.json();

      if (!resp.ok || !data.success) {{
        errorBox.textContent = data.error || 'Something went wrong. Please try again.';
        errorBox.style.display = 'block';
        return;
      }}

      var answers = data.answers || {{}};
      var html = '';
      Object.keys(answers).forEach(function(key) {{
        html += renderAnswer(key, answers[key]);
      }});
      results.innerHTML = html || '<p style="color:var(--text-dim)">No results returned.</p>';
      results.style.display = 'block';
    }} catch (err) {{
      errorBox.textContent = 'Network error — please try again.';
      errorBox.style.display = 'block';
    }} finally {{
      btn.disabled = false;
      btn.textContent = 'Judge it';
    }}
  }}

  btn.addEventListener('click', judge);
}})();
</script>
</body>
</html>
"""
