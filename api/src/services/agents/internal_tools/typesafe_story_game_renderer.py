"""
Renders a self-contained HTML page for a TypeSafe AI Story Game.

Pure static HTML/CSS/JS, no build step, no external deps beyond Google
Fonts. The player types free text each turn; the client sends it plus the
running transcript and current meter value to the public story-evaluate
endpoint, which judges it live against the agent-defined questions and
returns the authoritative new meter value + game status. The client only
ever renders what the server computes — no game-math duplicated client-side.
"""

from __future__ import annotations

import html as html_module
import json
from typing import Any

MAX_STORY_MESSAGE_LEN = 500


def _esc(text: str) -> str:
    return html_module.escape(str(text), quote=True)


def _safe_json(obj: Any) -> str:
    return json.dumps(obj).replace("</", "<\\/")


def render_story_game_html(page_id: str, spec: dict[str, Any], api_base_url: str) -> str:
    title = spec["title"]
    description = spec["description"]
    theme_emoji = spec.get("theme_emoji", "🎭")
    scenario_intro = spec["scenario_intro"]
    input_label = spec["input_label"]
    meter_label = spec["meter_label"]
    meter_start = spec.get("meter_start", 50)
    success_threshold = spec.get("success_threshold", 85)
    failure_threshold = spec.get("failure_threshold", 15)
    max_turns = spec.get("max_turns", 8)

    evaluate_url = f"{api_base_url}/api/v1/public/typesafe-playground/{page_id}/story-evaluate"

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
    --good-wash: #DDEBD7;
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
    min-height: 100vh; display: flex; justify-content: center; padding: 48px 18px 40px;
    background: radial-gradient(680px 320px at 50% -80px, var(--clay-wash) 0%, transparent 68%), var(--paper);
    background-attachment: fixed;
  }}
  .wrap {{ width: 100%; max-width: 540px; }}
  .emoji {{ font-size: 42px; text-align: center; margin-bottom: 8px; animation: rise 0.5s cubic-bezier(.2,.9,.25,1) both; }}
  h1 {{
    font-family: var(--serif); font-weight: 700; font-size: 30px; letter-spacing: -0.01em;
    text-align: center; margin: 0 0 8px; animation: rise 0.5s 0.05s cubic-bezier(.2,.9,.25,1) both;
  }}
  p.desc {{
    color: var(--ink-dim); text-align: center; margin: 0 0 26px; line-height: 1.55; font-size: 15px;
    animation: rise 0.5s 0.1s cubic-bezier(.2,.9,.25,1) both;
  }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

  .scenario {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 18px;
    padding: 22px 24px; margin-bottom: 22px; box-shadow: var(--shadow);
    font-family: var(--serif); font-size: 16.5px; line-height: 1.55; color: var(--ink);
  }}
  .scenario-label {{ font-family: var(--sans); font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--clay); margin-bottom: 8px; }}

  .meter-wrap {{ margin-bottom: 22px; }}
  .meter-head {{ display: flex; justify-content: space-between; align-items: baseline; font-size: 12.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--ink-dim); margin-bottom: 8px; }}
  .meter-head b {{ font-family: var(--serif); font-size: 16px; font-weight: 700; letter-spacing: 0; text-transform: none; color: var(--clay); margin-left: 4px; }}
  .meter-track {{
    position: relative; height: 14px; border-radius: 8px; overflow: hidden;
    background: linear-gradient(90deg, var(--bad), var(--clay), var(--good));
  }}
  .meter-cover {{
    position: absolute; top: 0; right: 0; height: 100%; background: var(--card-border);
    transition: width 0.5s cubic-bezier(.2,.9,.25,1);
  }}
  .meter-tick {{ position: absolute; top: -3px; width: 2px; height: 20px; background: var(--ink); opacity: 0.55; border-radius: 1px; z-index: 1; }}
  .meter-caption {{ text-align: center; font-size: 11px; color: var(--ink-dim); margin-top: 8px; }}

  .turn-counter {{ text-align: center; font-size: 12px; color: var(--ink-dim); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }}

  #transcript {{ margin-bottom: 18px; }}
  .msg {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 14px 14px 4px 14px;
    padding: 12px 16px; margin-bottom: 10px; max-width: 88%; margin-left: auto; box-shadow: var(--shadow);
    font-size: 14.5px; line-height: 1.5; animation: rise 0.3s cubic-bezier(.2,.9,.25,1) both;
  }}
  .turn-feedback {{ margin-bottom: 18px; animation: pop 0.3s cubic-bezier(.34,1.56,.64,1) both; }}
  @keyframes pop {{ from {{ opacity: 0; transform: scale(0.94); }} to {{ opacity: 1; transform: scale(1); }} }}
  .feedback-row {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  .feedback-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 12px;
    padding: 10px 14px; box-shadow: var(--shadow); flex: 1; min-width: 130px;
  }}
  .feedback-key {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-dim); margin-bottom: 4px; }}
  .feedback-val {{ font-family: var(--serif); font-size: 15px; font-weight: 700; color: var(--ink); }}
  .feedback-val.good {{ color: var(--good); }}
  .feedback-val.bad {{ color: var(--bad); }}

  label {{ display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-dim); margin-bottom: 9px; }}
  textarea {{
    width: 100%; min-height: 90px; background: var(--card); border: 1.5px solid var(--card-border);
    border-radius: 16px; padding: 14px 16px; color: var(--ink); font-family: var(--sans);
    font-size: 15px; resize: vertical; outline: none; box-shadow: var(--shadow); transition: border-color 0.15s;
  }}
  textarea:focus {{ border-color: var(--clay); }}
  .charcount {{ text-align: right; font-size: 11.5px; color: var(--ink-dim); margin-top: 6px; }}
  button.send {{
    width: 100%; margin-top: 14px; padding: 15px; border: none; border-radius: 999px;
    background: var(--clay); color: #FFF9F1; font-weight: 700; font-family: var(--sans); font-size: 15px;
    cursor: pointer; transition: all 0.15s; box-shadow: 0 6px 18px -6px rgba(194,87,31,0.55);
  }}
  button.send:disabled {{ opacity: 0.55; cursor: default; }}
  button.send:not(:disabled):hover {{ background: var(--clay-deep); transform: translateY(-1px); }}

  #error {{
    display: none; margin-top: 14px; padding: 13px 16px; border-radius: 12px;
    background: var(--bad-wash); border: 1px solid rgba(181,67,46,0.25);
    color: var(--bad); font-size: 14px; font-weight: 500; text-align: center;
  }}

  #ending {{ display: none; text-align: center; }}
  #ending .badge {{
    display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;
    padding: 6px 14px; border-radius: 999px; margin-bottom: 16px;
  }}
  #ending .badge.success {{ background: var(--good-wash); color: var(--good); }}
  #ending .badge.failure {{ background: var(--bad-wash); color: var(--bad); }}
  #ending .badge.stalemate {{ background: var(--clay-wash); color: var(--clay-deep); }}
  #ending .ending-text {{
    font-family: var(--serif); font-size: 20px; line-height: 1.5; color: var(--ink);
    margin-bottom: 28px; animation: rise 0.4s cubic-bezier(.2,.9,.25,1) both;
  }}
  #ending button {{
    width: 100%; padding: 16px; border-radius: 999px; font-weight: 700; font-family: var(--sans);
    font-size: 15px; cursor: pointer; margin-bottom: 12px; border: 1.5px solid var(--card-border);
    transition: all 0.15s;
  }}
  #ending .play-again {{ background: var(--clay); color: #FFF9F1; border: none; box-shadow: 0 6px 18px -6px rgba(194,87,31,0.55); }}
  #ending .play-again:hover {{ background: var(--clay-deep); }}
  #ending .copy-link {{ background: var(--card); color: var(--ink); box-shadow: var(--shadow); }}
  #ending .copy-link:hover {{ border-color: var(--clay); }}

  footer {{ text-align: center; margin-top: 34px; font-size: 12.5px; color: var(--ink-dim); }}
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

  <div id="game">
    <div class="scenario">
      <div class="scenario-label">The situation</div>
      {_esc(scenario_intro)}
    </div>

    <div class="meter-wrap">
      <div class="meter-head"><span>{_esc(meter_label)}</span><b id="meterNum">{meter_start}</b></div>
      <div class="meter-track">
        <div class="meter-tick" style="left:{failure_threshold}%"></div>
        <div class="meter-tick" style="left:{success_threshold}%"></div>
        <div class="meter-cover" id="meterCover" style="width:{100 - meter_start}%"></div>
      </div>
      <div class="meter-caption">Lose at {failure_threshold} · Win at {success_threshold}</div>
    </div>

    <div class="turn-counter">Turn <span id="turnNum">1</span> / {max_turns}</div>

    <div id="transcript"></div>
    <div id="turnFeedback"></div>

    <label for="input">{_esc(input_label)}</label>
    <textarea id="input" maxlength="{MAX_STORY_MESSAGE_LEN}" placeholder="Type what you'd say..."></textarea>
    <div class="charcount"><span id="charcount">0</span> / {MAX_STORY_MESSAGE_LEN}</div>
    <button class="send" id="sendBtn">Send</button>

    <div id="error"></div>
  </div>

  <div id="ending">
    <div class="badge" id="endingBadge">—</div>
    <div class="ending-text" id="endingText"></div>
    <button class="play-again" id="playAgainBtn">Play Again</button>
    <button class="copy-link" id="copyLinkBtn">Copy Link to Challenge a Friend</button>
  </div>

  <footer>Powered by <a href="https://synkora.ai" target="_blank" rel="noopener">Synkora</a> agents × TypeSafe AI</footer>
</div>
<script>
(function() {{
  var EVALUATE_URL = {_safe_json(evaluate_url)};
  var METER_START = {_safe_json(meter_start)};
  var SUCCESS_THRESHOLD = {_safe_json(success_threshold)};
  var FAILURE_THRESHOLD = {_safe_json(failure_threshold)};
  var MAX_TURNS = {_safe_json(max_turns)};

  var meterValue = METER_START;
  var turnIndex = 0;
  var history = [];
  var busy = false;

  var el = {{
    meterNum: document.getElementById('meterNum'),
    meterCover: document.getElementById('meterCover'),
    turnNum: document.getElementById('turnNum'),
    transcript: document.getElementById('transcript'),
    turnFeedback: document.getElementById('turnFeedback'),
    input: document.getElementById('input'),
    charcount: document.getElementById('charcount'),
    sendBtn: document.getElementById('sendBtn'),
    error: document.getElementById('error'),
    game: document.getElementById('game'),
    ending: document.getElementById('ending'),
    endingBadge: document.getElementById('endingBadge'),
    endingText: document.getElementById('endingText')
  }};

  function escapeHtml(str) {{
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }}

  function updateMeter(value) {{
    meterValue = value;
    el.meterNum.textContent = Math.round(value);
    el.meterCover.style.width = (100 - Math.max(0, Math.min(100, value))) + '%';
  }}

  el.input.addEventListener('input', function() {{
    el.charcount.textContent = el.input.value.length;
  }});

  function renderFeedback(answers) {{
    var html = '<div class="feedback-row">';
    Object.keys(answers).forEach(function(key) {{
      var a = answers[key];
      var valStr = '', cls = '';
      if (a.type === 'noul') {{
        var yes = typeof a.noul === 'number' && a.noul >= 0.5;
        valStr = yes ? 'Yes' : 'No';
        cls = yes ? 'good' : 'bad';
      }} else if (a.type === 'choice') {{
        valStr = a.choice || '—';
      }} else if (a.type === 'score') {{
        valStr = typeof a.score === 'number' ? a.score.toFixed(2) : '—';
      }}
      html += '<div class="feedback-card"><div class="feedback-key">' + escapeHtml(key) +
        '</div><div class="feedback-val ' + cls + '">' + escapeHtml(valStr) + '</div></div>';
    }});
    html += '</div>';
    el.turnFeedback.innerHTML = html;
  }}

  function showEnding(status, text) {{
    el.game.style.display = 'none';
    el.ending.style.display = 'block';
    el.endingBadge.className = 'badge ' + status;
    el.endingBadge.textContent = status === 'success' ? 'Success' : status === 'failure' ? 'Failure' : 'Stalemate';
    el.endingText.textContent = text;
  }}

  async function send() {{
    if (busy) return;
    var message = el.input.value.trim();
    el.error.style.display = 'none';
    if (!message) {{
      el.error.textContent = 'Type something first.';
      el.error.style.display = 'block';
      return;
    }}

    busy = true;
    el.sendBtn.disabled = true;
    el.sendBtn.innerHTML = '<span class="spinner"></span>Judging...';
    el.input.disabled = true;

    var msgDiv = document.createElement('div');
    msgDiv.className = 'msg';
    msgDiv.textContent = message;
    el.transcript.appendChild(msgDiv);
    el.turnFeedback.innerHTML = '';

    try {{
      var resp = await fetch(EVALUATE_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          turn_index: turnIndex,
          message: message,
          history: history,
          current_meter: meterValue
        }})
      }});
      var data = await resp.json();

      if (!resp.ok || !data.success) {{
        el.error.textContent = data.error || 'Something went wrong. Please try again.';
        el.error.style.display = 'block';
        return;
      }}

      history.push(message);
      turnIndex++;
      renderFeedback(data.answers || {{}});
      updateMeter(data.new_meter);
      el.input.value = '';
      el.charcount.textContent = '0';

      if (data.status === 'success') {{
        showEnding('success', {_safe_json(spec.get("success_ending", ""))});
      }} else if (data.status === 'failure') {{
        showEnding('failure', {_safe_json(spec.get("failure_ending", ""))});
      }} else if (data.status === 'stalemate') {{
        showEnding('stalemate', {_safe_json(spec.get("stalemate_ending", ""))});
      }} else {{
        el.turnNum.textContent = turnIndex + 1;
      }}
    }} catch (err) {{
      el.error.textContent = 'Network error — please try again.';
      el.error.style.display = 'block';
    }} finally {{
      busy = false;
      el.sendBtn.disabled = false;
      el.sendBtn.textContent = 'Send';
      el.input.disabled = false;
    }}
  }}

  el.sendBtn.addEventListener('click', send);
  el.input.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send();
  }});

  document.getElementById('playAgainBtn').addEventListener('click', function() {{
    el.ending.style.display = 'none';
    el.game.style.display = 'block';
    el.transcript.innerHTML = '';
    el.turnFeedback.innerHTML = '';
    history = [];
    turnIndex = 0;
    el.turnNum.textContent = '1';
    updateMeter(METER_START);
  }});

  document.getElementById('copyLinkBtn').addEventListener('click', function() {{
    navigator.clipboard.writeText(window.location.href).then(function() {{
      var btn = document.getElementById('copyLinkBtn');
      var original = btn.textContent;
      btn.textContent = 'Link copied!';
      setTimeout(function() {{ btn.textContent = original; }}, 1500);
    }});
  }});

  updateMeter(METER_START);
}})();
</script>
</body>
</html>
"""
