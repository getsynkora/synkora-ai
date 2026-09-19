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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;0,9..144,700;0,9..144,900;1,9..144,600&family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper: #F6F1E7;
    --card: #FFFDF8;
    --card-border: #E4D9C3;
    --ink: #26211A;
    --ink-dim: #7A7060;
    --clay: #C2571F;
    --clay-deep: #A8481A;
    --clay-wash: #F3D9C4;
    --good: #4B7A4E;
    --bad: #B5432E;
    --bad-wash: #F3DCD3;
    --serif: 'Fraunces', Georgia, serif;
    --sans: 'Public Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    --shadow: 0 1px 2px rgba(38,33,26,0.04), 0 8px 24px -12px rgba(38,33,26,0.18);
  }}
  * {{ box-sizing: border-box; }}
  html {{ background: var(--paper); }}
  body {{
    margin: 0; color: var(--ink); font-family: var(--sans);
    min-height: 100vh; display: flex; justify-content: center; padding: 56px 18px 40px;
    background:
      radial-gradient(680px 320px at 50% -80px, var(--clay-wash) 0%, transparent 68%),
      var(--paper);
    background-attachment: fixed;
  }}
  .wrap {{ width: 100%; max-width: 560px; }}
  .emoji {{ font-size: 44px; text-align: center; margin-bottom: 10px; animation: rise 0.5s cubic-bezier(.2,.9,.25,1) both; }}
  h1 {{
    font-family: var(--serif); font-weight: 700; font-size: 32px; letter-spacing: -0.01em;
    text-align: center; margin: 0 0 10px; animation: rise 0.5s 0.05s cubic-bezier(.2,.9,.25,1) both;
  }}
  p.desc {{
    color: var(--ink-dim); text-align: center; margin: 0 0 32px; line-height: 1.55; font-size: 15.5px;
    animation: rise 0.5s 0.1s cubic-bezier(.2,.9,.25,1) both;
  }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  label {{ display: block; font-size: 12.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-dim); margin-bottom: 10px; }}
  textarea {{
    width: 100%; min-height: 130px; background: var(--card); border: 1.5px solid var(--card-border);
    border-radius: 16px; padding: 16px 18px; color: var(--ink); font-family: var(--sans);
    font-size: 15.5px; resize: vertical; outline: none; box-shadow: var(--shadow); transition: border-color 0.15s;
  }}
  textarea:focus {{ border-color: var(--clay); }}
  .charcount {{ text-align: right; font-size: 12px; color: var(--ink-dim); margin-top: 8px; }}
  button.judge {{
    width: 100%; margin-top: 20px; padding: 16px; border: none; border-radius: 999px;
    background: var(--clay); color: #FFF9F1; font-weight: 700; font-family: var(--sans); font-size: 15.5px;
    cursor: pointer; transition: all 0.15s; box-shadow: 0 6px 18px -6px rgba(194,87,31,0.55);
  }}
  button.judge:disabled {{ opacity: 0.6; cursor: default; }}
  button.judge:not(:disabled):hover {{ background: var(--clay-deep); transform: translateY(-1px); }}
  #error {{
    display: none; margin-top: 16px; padding: 13px 16px; border-radius: 12px;
    background: var(--bad-wash); border: 1px solid rgba(181,67,46,0.25);
    color: var(--bad); font-size: 14px; font-weight: 500;
  }}
  #results {{ margin-top: 30px; display: none; }}
  .answer-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 16px;
    padding: 18px 20px; margin-bottom: 12px; box-shadow: var(--shadow);
    animation: rise 0.35s cubic-bezier(.2,.9,.25,1) both;
  }}
  .answer-key {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--ink-dim); margin-bottom: 8px; }}
  .answer-value {{ font-family: var(--serif); font-size: 20px; font-weight: 700; color: var(--ink); }}
  .answer-conf {{ font-size: 12.5px; color: var(--ink-dim); margin-top: 3px; }}
  .bar-row {{ display: flex; align-items: center; gap: 9px; margin-top: 7px; font-size: 12.5px; color: var(--ink-dim); }}
  .bar-track {{ flex: 1; height: 6px; border-radius: 4px; background: var(--card-border); overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--clay-deep), var(--clay)); }}
  footer {{ text-align: center; margin-top: 38px; font-size: 12.5px; color: var(--ink-dim); }}
  footer a {{ color: var(--clay); text-decoration: none; font-weight: 600; }}
  .spinner {{
    display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,249,241,0.35);
    border-top-color: #FFF9F1; border-radius: 50%; animation: spin 0.7s linear infinite; margin-right: 8px;
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
      results.innerHTML = html || '<p style="color:var(--ink-dim)">No results returned.</p>';
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
