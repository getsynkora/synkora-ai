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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;0,9..144,700;0,9..144,900;1,9..144,600&family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper: #F6F1E7;
    --paper-warm: #F0E8D8;
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
    min-height: 100vh; display: flex; justify-content: center; padding: 56px 18px 40px;
    background:
      radial-gradient(680px 320px at 50% -80px, var(--clay-wash) 0%, transparent 68%),
      var(--paper);
    background-attachment: fixed;
  }}
  .wrap {{ width: 100%; max-width: 500px; position: relative; }}
  .emoji {{
    font-size: 44px; text-align: center; margin-bottom: 10px;
    animation: rise 0.5s cubic-bezier(.2,.9,.25,1) both;
  }}
  h1 {{
    font-family: var(--serif); font-weight: 700; font-size: 32px; letter-spacing: -0.01em;
    text-align: center; margin: 0 0 10px; color: var(--ink);
    animation: rise 0.5s 0.05s cubic-bezier(.2,.9,.25,1) both;
  }}
  p.desc {{
    color: var(--ink-dim); text-align: center; margin: 0 0 30px; line-height: 1.55; font-size: 15.5px;
    max-width: 400px; margin-left: auto; margin-right: auto;
    animation: rise 0.5s 0.1s cubic-bezier(.2,.9,.25,1) both;
  }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

  .hud {{
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: 12.5px; color: var(--ink-dim); margin-bottom: 10px;
    text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600;
  }}
  .hud b {{ color: var(--clay); font-family: var(--serif); font-size: 16px; font-weight: 700; letter-spacing: 0; text-transform: none; margin-left: 4px; }}

  .timer-track {{ height: 6px; border-radius: 4px; background: var(--card-border); overflow: hidden; margin-bottom: 22px; }}
  .timer-fill {{ height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--clay-deep), var(--clay)); width: 100%; transition: width linear; }}

  .scenario-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 20px;
    padding: 40px 30px; text-align: center; font-family: var(--serif); font-size: 23px;
    font-weight: 600; line-height: 1.42; color: var(--ink);
    min-height: 130px; display: flex; align-items: center; justify-content: center;
    margin-bottom: 22px; box-shadow: var(--shadow);
    animation: deal 0.32s cubic-bezier(.2,.9,.25,1) both;
  }}
  @keyframes deal {{
    from {{ opacity: 0; transform: scale(0.95) rotate(-0.8deg) translateY(6px); }}
    to {{ opacity: 1; transform: scale(1) rotate(0) translateY(0); }}
  }}

  .guess-row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  button.guess {{
    flex: 1; min-width: 120px; padding: 17px 12px; border: 1.5px solid var(--card-border);
    border-radius: 999px; background: var(--card); color: var(--ink); font-weight: 700;
    font-family: var(--sans); font-size: 15px; cursor: pointer; transition: all 0.15s;
    box-shadow: var(--shadow);
  }}
  button.guess:not(:disabled):hover {{ border-color: var(--clay); transform: translateY(-2px); }}
  button.guess:not(:disabled):active {{ transform: translateY(0) scale(0.98); }}
  button.guess:disabled {{ cursor: default; }}
  button.guess.picked {{ border-color: var(--clay); background: var(--clay-wash); }}
  button.guess.correct {{ border-color: var(--good); background: var(--good-wash); color: var(--good); }}
  button.guess.wrong {{ border-color: var(--bad); background: var(--bad-wash); color: var(--bad); opacity: 0.8; }}

  #reveal {{ display: none; margin-top: 20px; }}
  .banner {{
    text-align: center; font-family: var(--serif); font-weight: 700; font-size: 18px;
    padding: 14px; border-radius: 14px; margin-bottom: 14px;
    animation: pop 0.3s cubic-bezier(.34,1.56,.64,1) both;
  }}
  @keyframes pop {{ from {{ opacity: 0; transform: scale(0.92); }} to {{ opacity: 1; transform: scale(1); }} }}
  .banner.match {{ background: var(--good-wash); color: var(--good); }}
  .banner.miss {{ background: var(--bad-wash); color: var(--bad); }}
  .reveal-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 14px;
    padding: 14px 18px; margin-bottom: 10px; box-shadow: var(--shadow);
  }}
  .reveal-key {{ font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink-dim); margin-bottom: 4px; }}
  .reveal-val {{ font-family: var(--serif); font-size: 17px; font-weight: 700; color: var(--ink); }}

  button.next {{
    width: 100%; margin-top: 8px; padding: 16px; border: none; border-radius: 999px;
    background: var(--clay); color: #FFF9F1; font-weight: 700; font-family: var(--sans);
    font-size: 15.5px; cursor: pointer; transition: all 0.15s; box-shadow: 0 6px 18px -6px rgba(194,87,31,0.55);
  }}
  button.next:hover {{ background: var(--clay-deep); transform: translateY(-1px); }}

  #final {{ display: none; text-align: center; }}
  #final .score-big {{
    font-family: var(--serif); font-size: 64px; font-weight: 700; margin: 14px 0 6px; color: var(--clay);
    animation: pop 0.4s cubic-bezier(.34,1.56,.64,1) both;
  }}
  #final .score-sub {{ color: var(--ink-dim); margin-bottom: 28px; font-size: 15px; line-height: 1.5; }}
  #final button {{
    width: 100%; padding: 16px; border-radius: 999px; font-weight: 700; font-family: var(--sans);
    font-size: 15px; cursor: pointer; margin-bottom: 12px; border: 1.5px solid var(--card-border);
    transition: all 0.15s;
  }}
  #final .play-again {{ background: var(--clay); color: #FFF9F1; border: none; box-shadow: 0 6px 18px -6px rgba(194,87,31,0.55); }}
  #final .play-again:hover {{ background: var(--clay-deep); }}
  #final .copy-link {{ background: var(--card); color: var(--ink); box-shadow: var(--shadow); }}
  #final .copy-link:hover {{ border-color: var(--clay); }}

  footer {{ text-align: center; margin-top: 38px; font-size: 12.5px; color: var(--ink-dim); letter-spacing: 0.01em; }}
  footer a {{ color: var(--clay); text-decoration: none; font-weight: 600; }}
  #error {{
    display: none; margin-top: 16px; padding: 13px 16px; border-radius: 12px;
    background: var(--bad-wash); border: 1px solid rgba(181,67,46,0.25);
    color: var(--bad); font-size: 14px; text-align: center; font-weight: 500;
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
