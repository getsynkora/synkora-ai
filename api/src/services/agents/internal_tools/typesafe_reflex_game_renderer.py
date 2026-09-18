"""
Renders a self-contained HTML page for a TypeSafe AI Reflex Game.

Pure static HTML/CSS/JS, no build step, no external deps. The scenario bank
and guess question are embedded at build time (fixed by the agent); each
round the client sends only a scenario INDEX to the public evaluate
endpoint, which looks the text up server-side from the stored spec — the
client can never submit arbitrary text through this page.
"""

from __future__ import annotations

import html as html_module
import json
from typing import Any


def _esc(text: str) -> str:
    return html_module.escape(str(text), quote=True)


def _safe_json(obj: Any) -> str:
    return json.dumps(obj).replace("</", "<\\/")


def render_reflex_game_html(page_id: str, spec: dict[str, Any], api_base_url: str) -> str:
    title = spec["title"]
    description = spec["description"]
    theme_emoji = spec.get("theme_emoji", "⚡")
    scenarios = spec["scenarios"]
    guess_question = spec["guess_question"]
    yes_label = spec.get("yes_label", "Yes")
    no_label = spec.get("no_label", "No")
    round_seconds = spec.get("round_seconds", 6)

    evaluate_url = f"{api_base_url}/api/v1/public/typesafe-playground/{page_id}/reflex-evaluate"

    guess_type = guess_question.get("type", "noul")
    guess_options = guess_question.get("options") or []

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
    --good: #4ade80;
    --bad: #f87171;
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text); font-family: var(--font);
    min-height: 100vh; display: flex; justify-content: center; padding: 40px 16px;
  }}
  .wrap {{ width: 100%; max-width: 480px; }}
  .emoji {{ font-size: 40px; text-align: center; margin-bottom: 6px; }}
  h1 {{ font-size: 24px; text-align: center; margin: 0 0 6px; }}
  p.desc {{ color: var(--text-dim); text-align: center; margin: 0 0 24px; line-height: 1.5; font-size: 14px; }}

  .hud {{ display: flex; justify-content: space-between; font-size: 13px; color: var(--text-dim); margin-bottom: 10px; }}
  .hud b {{ color: var(--text); }}

  .timer-track {{ height: 5px; border-radius: 3px; background: var(--card-border); overflow: hidden; margin-bottom: 20px; }}
  .timer-fill {{ height: 100%; background: var(--accent); width: 100%; transition: width linear; }}

  .scenario-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 16px;
    padding: 32px 24px; text-align: center; font-size: 19px; font-weight: 600; line-height: 1.4;
    min-height: 120px; display: flex; align-items: center; justify-content: center;
    margin-bottom: 20px; animation: pop 0.25s ease both;
  }}
  @keyframes pop {{ from {{ opacity: 0; transform: scale(0.97); }} to {{ opacity: 1; transform: scale(1); }} }}

  .guess-row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  button.guess {{
    flex: 1; min-width: 110px; padding: 16px 10px; border: 1px solid var(--card-border);
    border-radius: 12px; background: var(--card); color: var(--text); font-weight: 700;
    font-size: 15px; cursor: pointer; transition: all 0.12s;
  }}
  button.guess:not(:disabled):hover {{ border-color: var(--accent); transform: translateY(-1px); }}
  button.guess:disabled {{ opacity: 0.5; cursor: default; }}
  button.guess.picked {{ border-color: var(--accent); background: rgba(167,139,250,0.15); }}
  button.guess.correct {{ border-color: var(--good); background: rgba(74,222,128,0.15); }}
  button.guess.wrong {{ border-color: var(--bad); background: rgba(248,113,113,0.12); }}

  #reveal {{ display: none; margin-top: 18px; }}
  .banner {{
    text-align: center; font-weight: 800; font-size: 17px; padding: 12px; border-radius: 12px;
    margin-bottom: 14px; animation: pop 0.25s ease both;
  }}
  .banner.match {{ background: rgba(74,222,128,0.15); color: var(--good); }}
  .banner.miss {{ background: rgba(248,113,113,0.12); color: var(--bad); }}
  .reveal-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 12px;
    padding: 12px 16px; margin-bottom: 10px; font-size: 13px;
  }}
  .reveal-key {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim); margin-bottom: 4px; }}
  .reveal-val {{ font-size: 15px; font-weight: 700; }}

  button.next {{
    width: 100%; margin-top: 6px; padding: 14px; border: none; border-radius: 12px;
    background: var(--accent); color: #17131f; font-weight: 700; font-size: 15px; cursor: pointer;
  }}

  #final {{ display: none; text-align: center; }}
  #final .score-big {{ font-size: 52px; font-weight: 800; margin: 12px 0 4px; }}
  #final .score-sub {{ color: var(--text-dim); margin-bottom: 24px; }}
  #final button {{
    width: 100%; padding: 14px; border-radius: 12px; font-weight: 700; font-size: 15px;
    cursor: pointer; margin-bottom: 10px; border: 1px solid var(--card-border);
  }}
  #final .play-again {{ background: var(--accent); color: #17131f; border: none; }}
  #final .copy-link {{ background: var(--card); color: var(--text); }}

  footer {{ text-align: center; margin-top: 32px; font-size: 12px; color: var(--text-dim); }}
  footer a {{ color: var(--accent); text-decoration: none; }}
  #error {{
    display: none; margin-top: 14px; padding: 12px 16px; border-radius: 10px;
    background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.3);
    color: var(--bad); font-size: 14px; text-align: center;
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="emoji">{_esc(theme_emoji)}</div>
  <h1>{_esc(title)}</h1>
  <p class="desc">{_esc(description)}</p>

  <div id="game">
    <div class="hud">
      <span>Round <b id="roundNum">1</b>/<b id="roundTotal">-</b></span>
      <span>Score <b id="scoreNum">0</b></span>
    </div>
    <div class="timer-track"><div class="timer-fill" id="timerFill"></div></div>
    <div class="scenario-card" id="scenarioText">Loading…</div>
    <div class="guess-row" id="guessRow"></div>
    <div id="reveal"></div>
    <div id="error"></div>
  </div>

  <div id="final">
    <div class="score-big" id="finalScore">—</div>
    <div class="score-sub" id="finalSub"></div>
    <button class="play-again" id="playAgainBtn">Play Again</button>
    <button class="copy-link" id="copyLinkBtn">Copy Link to Challenge a Friend</button>
  </div>

  <footer>Powered by <a href="https://synkora.ai" target="_blank" rel="noopener">Synkora</a> agents × TypeSafe AI</footer>
</div>
<script>
(function() {{
  var EVALUATE_URL = {_safe_json(evaluate_url)};
  var SCENARIOS = {_safe_json(scenarios)};
  var GUESS_TYPE = {_safe_json(guess_type)};
  var GUESS_OPTIONS = {_safe_json(guess_options)};
  var YES_LABEL = {_safe_json(yes_label)};
  var NO_LABEL = {_safe_json(no_label)};
  var ROUND_SECONDS = {_safe_json(round_seconds)};

  var order = [];
  var roundIdx = 0;
  var score = 0;
  var timer = null;
  var locked = false;

  var el = {{
    roundNum: document.getElementById('roundNum'),
    roundTotal: document.getElementById('roundTotal'),
    scoreNum: document.getElementById('scoreNum'),
    timerFill: document.getElementById('timerFill'),
    scenarioText: document.getElementById('scenarioText'),
    guessRow: document.getElementById('guessRow'),
    reveal: document.getElementById('reveal'),
    error: document.getElementById('error'),
    game: document.getElementById('game'),
    final: document.getElementById('final'),
    finalScore: document.getElementById('finalScore'),
    finalSub: document.getElementById('finalSub')
  }};

  function shuffle(arr) {{
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {{
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }}
    return a;
  }}

  function escapeHtml(str) {{
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }}

  function buildGuessButtons() {{
    el.guessRow.innerHTML = '';
    var choices = GUESS_TYPE === 'choice' ? GUESS_OPTIONS : [YES_LABEL, NO_LABEL];
    choices.forEach(function(label, i) {{
      var btn = document.createElement('button');
      btn.className = 'guess';
      btn.textContent = label;
      btn.dataset.value = GUESS_TYPE === 'choice' ? label : (i === 0 ? 'yes' : 'no');
      btn.addEventListener('click', function() {{ onGuess(btn.dataset.value, btn); }});
      el.guessRow.appendChild(btn);
    }});
  }}

  function startRound() {{
    if (roundIdx >= order.length) {{ showFinal(); return; }}
    locked = false;
    el.reveal.style.display = 'none';
    el.reveal.innerHTML = '';
    el.error.style.display = 'none';
    el.roundNum.textContent = roundIdx + 1;
    el.scenarioText.textContent = SCENARIOS[order[roundIdx]];
    buildGuessButtons();
    Array.prototype.forEach.call(el.guessRow.children, function(b) {{ b.disabled = false; b.className = 'guess'; }});

    var remaining = ROUND_SECONDS * 1000;
    el.timerFill.style.transition = 'none';
    el.timerFill.style.width = '100%';
    void el.timerFill.offsetWidth;
    el.timerFill.style.transition = 'width ' + ROUND_SECONDS + 's linear';
    el.timerFill.style.width = '0%';

    clearTimeout(timer);
    timer = setTimeout(function() {{ onGuess(null, null); }}, remaining);
  }}

  async function onGuess(value, btnEl) {{
    if (locked) return;
    locked = true;
    clearTimeout(timer);
    el.timerFill.style.transition = 'none';

    Array.prototype.forEach.call(el.guessRow.children, function(b) {{
      b.disabled = true;
      if (b === btnEl) b.classList.add('picked');
    }});

    try {{
      var resp = await fetch(EVALUATE_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ scenario_index: order[roundIdx] }})
      }});
      var data = await resp.json();

      if (!resp.ok || !data.success) {{
        el.error.textContent = data.error || 'Something went wrong. Please try again.';
        el.error.style.display = 'block';
        locked = false;
        return;
      }}

      var guessAnswer = data.guess_answer || {{}};
      var aiValue, aiLabel;
      if (GUESS_TYPE === 'noul') {{
        var prob = typeof guessAnswer.noul === 'number' ? guessAnswer.noul : 0.5;
        aiValue = prob >= 0.5 ? 'yes' : 'no';
        aiLabel = prob >= 0.5 ? YES_LABEL : NO_LABEL;
      }} else {{
        aiValue = guessAnswer.choice || '';
        aiLabel = aiValue;
      }}

      var isMatch = value !== null && value === aiValue;
      if (isMatch) {{ score++; el.scoreNum.textContent = score; }}

      Array.prototype.forEach.call(el.guessRow.children, function(b) {{
        if (b.dataset.value === aiValue) b.classList.add('correct');
        else if (b === btnEl) b.classList.add('wrong');
      }});

      var html = '<div class="banner ' + (isMatch ? 'match' : 'miss') + '">' +
        (value === null ? "Time's up — " : '') +
        (isMatch ? 'You matched the AI! ✓' : 'AI disagreed: ' + escapeHtml(aiLabel)) +
        '</div>';

      var reveal = data.reveal_answers || {{}};
      Object.keys(reveal).forEach(function(key) {{
        var a = reveal[key];
        var valStr = '';
        if (a.type === 'score') {{
          valStr = (typeof a.score === 'number' ? a.score.toFixed(2) : '—');
        }} else if (a.type === 'choice') {{
          valStr = a.choice || '—';
        }} else if (a.type === 'noul') {{
          valStr = (typeof a.noul === 'number' && a.noul >= 0.5) ? 'Yes' : 'No';
        }}
        html += '<div class="reveal-card"><div class="reveal-key">' + escapeHtml(key) + '</div>' +
          '<div class="reveal-val">' + escapeHtml(valStr) + '</div></div>';
      }});

      html += '<button class="next" id="nextBtn">' + (roundIdx + 1 >= order.length ? 'See Results' : 'Next') + '</button>';
      el.reveal.innerHTML = html;
      el.reveal.style.display = 'block';
      document.getElementById('nextBtn').addEventListener('click', function() {{
        roundIdx++;
        startRound();
      }});
    }} catch (err) {{
      el.error.textContent = 'Network error — please try again.';
      el.error.style.display = 'block';
      locked = false;
    }}
  }}

  function showFinal() {{
    el.game.style.display = 'none';
    el.final.style.display = 'block';
    var pct = Math.round((score / order.length) * 100);
    el.finalScore.textContent = score + '/' + order.length;
    var verdict;
    if (pct >= 80) verdict = "You think exactly like the AI. 🎯";
    else if (pct >= 50) verdict = 'Decent instincts — better than a coin flip.';
    else verdict = "You and the AI see the world very differently. 🤷";
    el.finalSub.textContent = pct + '% match — ' + verdict;
  }}

  document.getElementById('playAgainBtn').addEventListener('click', function() {{
    el.final.style.display = 'none';
    el.game.style.display = 'block';
    order = shuffle(SCENARIOS.map(function(_, i) {{ return i; }}));
    roundIdx = 0;
    score = 0;
    el.scoreNum.textContent = '0';
    startRound();
  }});

  document.getElementById('copyLinkBtn').addEventListener('click', function() {{
    navigator.clipboard.writeText(window.location.href).then(function() {{
      var btn = document.getElementById('copyLinkBtn');
      var original = btn.textContent;
      btn.textContent = 'Link copied!';
      setTimeout(function() {{ btn.textContent = original; }}, 1500);
    }});
  }});

  order = shuffle(SCENARIOS.map(function(_, i) {{ return i; }}));
  el.roundTotal.textContent = order.length;
  startRound();
}})();
</script>
</body>
</html>
"""
