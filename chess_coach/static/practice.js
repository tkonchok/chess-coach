'use strict';

// UI state belongs to this tab. The server reconstructs/validates every move path;
// Beta reflections are sent only to our Save endpoint, never to the coach.
const byId = (id) => document.getElementById(id);
const main = document.querySelector('main');
const cardId = main.dataset.cardId;
const squares = Array.from(document.querySelectorAll('.square'));
const assets = new Map(Array.from(document.querySelectorAll('template[data-piece]'))
  .map((template) => [template.dataset.piece, template.content]));
const pieceNames = {p: 'pawn', n: 'knight', b: 'bishop', r: 'rook', q: 'queen', k: 'king'};
let position = null;
let initialPosition = null;
let path = [];
let selected = null;
let proposal = null;
let stage = 'play'; // play -> ready -> explore; notes are never required to advance.
let busy = false;
let example = null;
let exampleStep = 0;
let boardLabel = 'Starting position';
let promotionChoices = [];
let focusSquare = squares[0];
let savePayload = null;
let saved = false;
let studyTab = 'coaching';
let interactiveCoach = !!main.dataset.version;
let selfAnalysis = false;
let coachNotice = '';
let coachFinished = false;
let coachDeviated = false;
let coachAwaitingReply = false;
let coachTimeline = [];
let coachBrowsing = false;
let engineResult = null;
let engineTimer = null;
let engineController = null;
let engineSequence = 0;
let walkthrough = null;
let walkthroughSequence = 0;
let walkthroughPreparing = false;
let commentaryStatus = 'Commentary has not been requested.';
const engineCache = new Map();
const submissionId = main.dataset.version ? crypto.randomUUID() : null;

function message(text) { byId('status').textContent = text; }
function canPlay() { return position && !position.outcome && !busy && (stage !== 'ready' || interactiveCoach || selfAnalysis)
  && (!walkthrough || interactiveCoach) && !coachBrowsing && !coachAwaitingReply && !walkthroughPreparing && !byId('promotion').open; }
function owned(square) {
  const symbol = position?.pieces[square];
  return symbol && (symbol === symbol.toUpperCase()) === (position.turn === 'white');
}

function render() {
  main.dataset.stage = stage;
  main.dataset.interactive = String(interactiveCoach);
  main.dataset.coachFinished = String(coachFinished);
  const turnBadge = document.querySelector('.turn-badge');
  if (turnBadge && position) turnBadge.textContent = `${position.turn === 'white' ? 'White' : 'Black'} to move`;
  if (byId('coach-reply-retry')) {
    byId('coach-reply-retry').hidden = !coachAwaitingReply;
    byId('coach-reply-retry').disabled = busy;
    byId('coach-prev').disabled = busy || !path.length;
    byId('coach-next').disabled = busy || path.length >= coachTimeline.length;
    byId('coach-back').disabled = busy || !path.length;
    byId('coach-reset').disabled = busy;
    byId('coach-save').disabled = busy || stage !== 'explore' || !proposal;
    byId('coach-another').hidden = !coachFinished || coachBrowsing;
  }
  if (byId('tab-coaching')) {
    ['coaching','reflection'].forEach(tab => {
      const active = studyTab === tab;
      byId(`tab-${tab}`).setAttribute('aria-selected',String(active));
      byId(`tab-${tab}`).tabIndex = active ? 0 : -1;
      byId(`${tab}-content`).hidden = !active;
    });
  }
  const targets = new Set(selected ? position.legal_moves.filter((m) => m.slice(0, 2) === selected)
    .map((m) => m.slice(2, 4)) : []);
  const last = path.at(-1);
  squares.forEach((button) => {
    const square = button.dataset.square;
    const symbol = position?.pieces[square];
    const piece = button.querySelector('.piece');
    piece.replaceChildren();
    if (symbol) piece.append(assets.get(symbol).cloneNode(true));
    const description = symbol ? `${symbol === symbol.toUpperCase() ? 'White' : 'Black'} ${pieceNames[symbol.toLowerCase()]}` : 'empty';
    button.setAttribute('aria-label', `${square}, ${description}${targets.has(square) ? ', legal destination' : ''}`);
    button.setAttribute('aria-pressed', String(square === selected));
    button.setAttribute('aria-disabled', String(!canPlay()));
    button.classList.toggle('selected', square === selected);
    button.classList.toggle('target', targets.has(square));
    button.classList.toggle('last-move', !!last && [last.slice(0, 2), last.slice(2, 4)].includes(square));
    button.classList.toggle('in-check', square === position?.check);
  });
  byId('board').setAttribute('aria-busy', String(busy));
  byId('board-label').textContent = boardLabel;
  byId('position-context').textContent = position
    ? `${position.turn === 'white' ? 'White' : 'Black'} to move · Move ${position.fullmove_number}${position.outcome ? ' · Game over ' + position.outcome : ''}` : '';
  byId('reset').disabled = busy || !position;
  byId('your-move').disabled = busy || !proposal;
  byId('undo').hidden = stage !== 'explore';
  byId('undo').disabled = busy || path.length === 0;
  byId('reflection').hidden = !proposal;
  byId('proposal').hidden = !proposal;
  byId('proposal').textContent = proposal ? `Your proposed move: ${proposal.san}` : '';
  byId('reveal-actions').hidden = stage === 'explore';
  byId('reveal').disabled = busy || !proposal || stage === 'explore';
  byId('reasoning').readOnly = stage === 'explore';
  byId('original-reasoning').readOnly = stage === 'explore' || byId('dont-remember').checked;
  byId('dont-remember').disabled = stage === 'explore';
  byId('finish').disabled = busy || saved;
  document.querySelectorAll('input[name="reflection-choice"]').forEach(input => {
    input.checked = input.value === byId('original-choice').value;
    input.disabled = busy || !!savePayload;
  });
  if (savePayload) {
    ['original-reasoning', 'reasoning', 'takeaway'].forEach(id => { byId(id).readOnly = true; });
    if (byId('original-choice')) byId('original-choice').disabled = true;
    if (byId('skip-reflection')) byId('skip-reflection').disabled = true;
  }
  byId('original-summary').textContent = stage === 'explore'
    ? 'Original-game note (before reveal)' : 'Add a thought about your original move (optional)';
  byId('attempt-summary').textContent = stage === 'explore'
    ? 'Attempt note (before reveal)' : 'Add a thought about this attempt (optional)';
  byId('original-reasoning-note').textContent = byId('dont-remember').checked
    ? "You marked that you don't remember. Any draft is preserved, not treated as recalled reasoning."
    : stage === 'explore'
      ? 'Your original-game note is kept as entered before reveal. New thoughts belong in the takeaway.'
      : 'You can leave this unanswered and simply play.';
  byId('playback').hidden = stage !== 'explore' || !!walkthrough;
  byId('previous').disabled = busy || !example || exampleStep <= 0;
  byId('next').disabled = busy || !example || exampleStep >= example.moves.length;
  byId('step-count').textContent = `Example ${exampleStep} / ${example?.moves.length ?? 0}`;
  byId('stage-label').textContent = {play: '1 · Play', ready: '2 · Compare', explore: '3 · Explore'}[stage];
  byId('stage-title').textContent = {play: 'What would you play?', ready: 'Ready to compare?', explore: studyTab === 'reflection' ? 'Keep one useful idea.' : 'Let’s see how it plays out.'}[stage];
  byId('stage-help').textContent = {
    play: 'Choose your move on the board. Legal destinations will be highlighted.',
    ready: interactiveCoach ? 'Play either side to explore your idea. Reveal starts coached comparison; your first proposal is kept.' : 'Reveal the example when ready. No explanation is needed. Use Starting position to change your move.',
    explore: 'Your game move, new attempt, and example are separate. Keep a takeaway only if useful.'
  }[stage];
  renderEngine();
}

async function api(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), url.endsWith('/commentary') || url.endsWith('/coaching') ? 25000 : url.endsWith('/walkthrough') ? 15000 : 8000);
  try {
    const response = await fetch((main.dataset.apiBase || '') + url, {
      ...options, headers: {...options.headers, ...(main.dataset.csrf ? {'X-CSRF-Token': main.dataset.csrf} : {})},
      signal: controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The request failed.');
    if (result.card_id !== cardId) throw new Error('This card changed. Copy your notes, then reload.');
    return result;
  } finally { clearTimeout(timer); }
}

async function action(work) {
  if (busy) return;
  const startingFen = position?.fen;
  busy = true;
  selected = null;
  render();
  try { await work(); }
  catch (error) {
    message(error.name === 'AbortError'
      ? 'The server did not respond in time. Your board and notes are unchanged; try again.'
      : `Could not complete that action: ${error.message} Your notes are still here.`);
  } finally {
    busy = false; render();
    if (interactiveCoach && stage === 'explore' && !coachAwaitingReply && (position?.fen !== startingFen || selfAnalysis)) scheduleEngine();
  }
}

async function setPath(nextPath, label, remember = true) {
  const result = await api('/api/position', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({card_id: cardId, moves: nextPath}),
  });
  // Commit UI changes only after the complete path has been validated.
  position = result;
  path = nextPath.slice();
  if (remember) { coachTimeline = path.slice(); coachBrowsing = false; }
  else coachBrowsing = path.length < coachTimeline.length;
  boardLabel = label;
  scheduleEngine();
}

async function load() {
  await action(async () => {
    position = await api('/api/position');
    initialPosition = position;
    byId('retry').hidden = true;
    message('Choose a move. There is no timer.');
  });
  byId('retry').hidden = !!position;
}

async function play(uci) {
  const firstProposal = stage === 'play';
  // Ended prepared lines hand off to live coach replies before dispatching
  // this move. Only the explicit Self analysis mode permits manual replies.
  if (interactiveCoach && !selfAnalysis && walkthrough && coachFinished) {
    leaveWalkthrough();
  }
  if (interactiveCoach && !selfAnalysis && !walkthrough && stage === 'explore') {
    await action(async () => {
      await setPath([...path,uci], 'Your variation');
      coachFinished = false; coachDeviated = true;
      await liveCoachReply();
    });
    return;
  }
  if (interactiveCoach && !selfAnalysis && walkthrough) {
    await action(async () => {
      const branch = walkBranch();
      const expected = branch.steps[walkthrough.ply];
      if (coachDeviated || !expected || uci !== expected.uci) {
        await setPath([...path,uci], 'Your alternative');
        coachFinished = false;
        coachDeviated = true;
        coachNotice = 'Another legal variation. Let’s see the engine reply.';
        await liveCoachReply();
        return;
      }
      await setPath([...path,uci], 'Your continuation');
      walkthrough.ply++;
      coachNotice = 'Nice! Matches the engine line.';
      await coachReply();
    });
    return;
  }
  await action(async () => {
    const proposing = stage === 'play' || (selfAnalysis && !proposal && !path.length);
    await setPath([...path, uci], proposing ? 'Your proposed move' : 'Your exploration');
    if (proposing) {
      proposal = {uci, san: position.sans[0]};
      stage = selfAnalysis ? 'explore' : 'ready';
      render();
      message(`You proposed ${proposal.san}. You can reveal the example without writing anything.`);
    } else {
      message(position.outcome ? `This exploration ends ${position.outcome}. You can undo or return to the start.`
        : `Played ${position.sans.at(-1)}. You can explore the reply or return to the example line.`);
    }
  });
  // action() has re-enabled controls now; focus the next step, not a writing field.
  if (stage === 'ready' && interactiveCoach && !selfAnalysis) {
    await reveal();
    if (stage === 'explore') await startWalkthrough();
  } else if (stage === 'ready' && firstProposal && !interactiveCoach) byId('reveal').focus();
}

function chooseDestination(from, to) {
  const choices = position.legal_moves.filter((move) => move.slice(0, 4) === from + to);
  selected = null;
  if (!choices.length) {
    message('That move is not legal in this position. Choose another destination.');
    render();
    return;
  }
  if (choices.some((move) => move.length === 5)) {
    promotionChoices = choices;
    byId('promotion').showModal();
    render();
  } else { play(choices[0]); }
}

function selectSquare(square) {
  if (!canPlay()) return;
  if (selected === square) selected = null;
  else if (owned(square)) {
    selected = square;
    message(`Selected ${square}. Choose a highlighted destination.`);
  } else if (selected) { chooseDestination(selected, square); return; }
  else message('Select a piece belonging to the side to move.');
  render();
}

function focus(button) {
  focusSquare.tabIndex = -1;
  focusSquare = button;
  focusSquare.tabIndex = 0;
  focusSquare.focus({preventScroll: true});
}

// Native button activation provides Enter/Space; arrows follow the displayed
// orientation, so the same controls work for White and Black cards.
byId('board').addEventListener('keydown', (event) => {
  const button = event.target.closest('.square');
  if (!button) return;
  const index = squares.indexOf(button), row = Math.floor(index / 8), column = index % 8;
  const offsets = {ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]};
  if (event.key === 'Escape') { selected = null; render(); event.preventDefault(); }
  if (event.key in offsets) {
    const [dr, dc] = offsets[event.key];
    const nextRow = Math.max(0, Math.min(7, row + dr));
    const nextColumn = Math.max(0, Math.min(7, column + dc));
    focus(squares[nextRow * 8 + nextColumn]);
    event.preventDefault();
  }
});

let drag = null;
let swallowClick = false;
byId('board').addEventListener('click', (event) => {
  if (swallowClick) return;
  const button = event.target.closest('.square');
  if (button) { focus(button); selectSquare(button.dataset.square); }
});
byId('board').addEventListener('pointerdown', (event) => {
  const button = event.target.closest('.square');
  if (!button || !canPlay() || event.button !== 0 || !owned(button.dataset.square)) return;
  drag = {button, id: event.pointerId, x: event.clientX, y: event.clientY, ghost: null};
  button.setPointerCapture(event.pointerId);
});
byId('board').addEventListener('pointermove', (event) => {
  if (!drag || event.pointerId !== drag.id) return;
  if (!drag.ghost && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > 8) {
    drag.ghost = document.createElement('div');
    drag.ghost.className = 'drag-piece';
    drag.ghost.setAttribute('aria-hidden', 'true');
    drag.ghost.append(assets.get(position.pieces[drag.button.dataset.square]).cloneNode(true));
    const size = drag.button.getBoundingClientRect().width;
    drag.ghost.style.width = `${size}px`;
    drag.ghost.style.height = `${size}px`;
    document.body.append(drag.ghost);
    selected = drag.button.dataset.square;
    render();
  }
  if (drag.ghost) {
    drag.ghost.style.left = `${event.clientX}px`;
    drag.ghost.style.top = `${event.clientY}px`;
  }
});
function clearDrag() {
  if (drag?.button.hasPointerCapture(drag.id)) drag.button.releasePointerCapture(drag.id);
  drag?.ghost?.remove();
  drag = null;
}
byId('board').addEventListener('pointerup', (event) => {
  if (!drag || event.pointerId !== drag.id) return;
  const from = drag.button.dataset.square;
  const moved = !!drag.ghost;
  const destination = document.elementFromPoint(event.clientX, event.clientY)?.closest('.square');
  clearDrag();
  if (moved) {
    swallowClick = true;
    setTimeout(() => { swallowClick = false; }, 0);
    if (destination && canPlay()) chooseDestination(from, destination.dataset.square);
    else { selected = null; render(); message('Move cancelled. Choose a square on the board.'); }
  }
});
byId('board').addEventListener('pointercancel', () => { clearDrag(); selected = null; render(); });

document.querySelectorAll('[data-promotion]').forEach((button) => {
  button.addEventListener('click', () => {
    const move = promotionChoices.find((uci) => uci.endsWith(button.dataset.promotion));
    byId('promotion').close();
    promotionChoices = [];
    if (move) play(move);
  });
});
byId('cancel-promotion').addEventListener('click', () => byId('promotion').close());
byId('promotion').addEventListener('close', () => {
  // A queued close event from Cancel must not clear a newly reopened dialog.
  if (byId('promotion').open) return;
  promotionChoices = [];
  render();
  focusSquare.focus({preventScroll: true});
});

async function reveal() {
  if (!proposal || stage === 'explore') return;
  await action(async () => {
    const result = await api('/api/reveal');
    await setPath([], 'Example · starting position');
    example = result;
    exampleStep = 0;
    stage = 'explore';
    scheduleEngine();
    byId('example-line').textContent = example.line;
    if (byId('recommended-line')) byId('recommended-line').textContent = example.line;
    if (byId('explanation')) byId('explanation').textContent = example.explanation;
    if (byId('actual-move')) byId('actual-move').textContent = `In the original game: ${example.played_move_san}. This is not a right/wrong grade.`;
    byId('reasoning-note').textContent = 'Your optional attempt note is kept as entered before reveal. New thoughts belong in the takeaway.';
    byId('example').hidden = false;
    render();
    byId('example').focus();
    message('The example is revealed, not a right/wrong grade. Your proposed move and any notes are preserved.');
  });
}

byId('reveal').addEventListener('click', async () => {
  await reveal();
  if (interactiveCoach && stage === 'explore') await startWalkthrough();
});
byId('dont-remember').addEventListener('change', render);
byId('retry').addEventListener('click', load);
byId('reset').addEventListener('click', () => action(async () => {
  leaveWalkthrough();
  await setPath([], 'Starting position');
  if (stage === 'ready') stage = 'play';
  if (stage === 'explore') exampleStep = 0;
  message('Back at the start. Your proposed move and notes are preserved.');
}));
byId('your-move').addEventListener('click', () => action(async () => {
  leaveWalkthrough();
  await setPath([proposal.uci], 'Your proposed move');
  if (stage === 'play') stage = 'ready';
  message(`Your proposed move was ${proposal.san}.`);
}));
byId('undo').addEventListener('click', () => action(async () => {
  leaveWalkthrough();
  await setPath(path.slice(0, -1), 'Your exploration');
  message('Undid one exploration move. Your original proposal and notes are unchanged.');
}));
function showExample(step) {
  return action(async () => {
    leaveWalkthrough();
    await setPath(example.moves.slice(0, step), `Example · step ${step}`);
    exampleStep = step;
    message(step ? `Example: ${position.sans.join(' ')}` : 'Example: starting position.');
  });
}
byId('previous').addEventListener('click', () => showExample(Math.max(0, exampleStep - 1)));
byId('next').addEventListener('click', () => showExample(Math.min(example.moves.length, exampleStep + 1)));
byId('finish').addEventListener('click', () => {
  if (!main.dataset.version) {
    byId('finish-note').hidden = false;
    byId('finish-note').focus();
    return;
  }
  action(async () => {
    if (!savePayload) savePayload = {
      submission_id: submissionId, version_id: main.dataset.version,
      proposed_move_uci: proposal.uci, original_choice: byId('original-choice').value,
      original_reasoning: byId('original-reasoning').value,
      dont_remember: byId('dont-remember').checked || byId('original-choice').value === 'dont_remember',
      practice_reasoning: byId('reasoning').value, takeaway: byId('takeaway').value,
    };
    render();
    const result = await api('/api/attempts', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(savePayload),
    });
    saved = true;
    byId('finish-note').hidden = false;
    byId('finish-note').replaceChildren();
    const link = document.createElement('a');
    link.href = result.url;
    link.textContent = 'Saved. Open this session in your practice history.';
    byId('finish-note').append(link);
    byId('finish-note').focus();
    message('Session saved. Your reflection stays private from the AI.');
  });
});
if (byId('skip-reflection')) {
  document.querySelectorAll('input[name="reflection-choice"]').forEach(input => {
    input.addEventListener('change', () => { byId('original-choice').value = input.value; render(); });
  });
  byId('skip-reflection').addEventListener('click', () => { byId('original-choice').value = ''; render(); });
}
function renderEngine() {
  if (!byId('live-engine')) return;
  byId('live-engine').hidden = stage !== 'explore';
  byId('engine-arrow').setAttribute('hidden', '');
  renderWalkthrough();
  if (stage !== 'explore') {
    byId('engine-score').textContent = '—';
    byId('engine-line').textContent = '';
    byId('eval-black').setAttribute('height','50');
    byId('eval-bar').setAttribute('aria-valuenow','50');
    byId('eval-bar').setAttribute('aria-valuetext','Evaluation unavailable during prediction or before reveal');
    return;
  }
  if (!engineResult || engineResult.fen !== position?.fen) return;
  const result = engineResult;
  let share = 50;
  let text = '0.00';
  if (result.terminal) {
    share = result.terminal === '1-0' ? 100 : result.terminal === '0-1' ? 0 : 50;
    text = result.terminal;
  } else if (result.mate !== null) {
    share = result.mate > 0 ? 100 : 0;
    text = `${result.mate > 0 ? '+' : '−'}M${Math.abs(result.mate)}`;
  } else {
    share = 50 + 50 * Math.tanh(result.centipawns / 400);
    text = `${result.centipawns >= 0 ? '+' : ''}${(result.centipawns / 100).toFixed(2)}`;
  }
  byId('engine-score').textContent = text;
  byId('eval-black').setAttribute('height',String(100 - share));
  byId('eval-bar').setAttribute('aria-valuenow',String(Math.round(share)));
  byId('eval-bar').setAttribute('aria-valuetext',`White perspective: ${text}`);
  byId('engine-line').textContent = result.line.join(' · ');
  if (!result.best_move_uci || (walkthrough && !interactiveCoach) || !byId('arrow-enabled').checked || !byId('live-enabled').checked) return;
  const point = square => {
    const file = square.charCodeAt(0) - 97, rank = Number(square[1]) - 1;
    return main.dataset.orientation === 'white' ? [(file + .5) * 100,(7.5 - rank) * 100]
      : [(7.5 - file) * 100,(rank + .5) * 100];
  };
  const [x1,y1] = point(result.best_move_uci.slice(0,2));
  const [x2,y2] = point(result.best_move_uci.slice(2,4));
  const length = Math.hypot(x2-x1,y2-y1);
  byId('engine-arrow-path').setAttribute('d',`M ${x1} ${y1} L ${x2-(x2-x1)*18/length} ${y2-(y2-y1)*18/length}`);
  byId('engine-arrow').removeAttribute('hidden');
}

function scheduleEngine(force = false, busyRetries = 0) {
  if (!byId('live-engine')) return;
  clearTimeout(engineTimer);
  engineController?.abort();
  const sequence = ++engineSequence;
  engineResult = null;
  byId('engine-score').textContent = '—';
  byId('engine-line').textContent = '';
  byId('eval-black').setAttribute('height','50');
  byId('eval-bar').setAttribute('aria-valuenow','50');
  byId('eval-bar').setAttribute('aria-valuetext','Evaluation unavailable for the current position');
  renderEngine();
  if (stage !== 'explore' || walkthroughPreparing || (interactiveCoach && busy) || !byId('live-enabled').checked) {
    byId('engine-state').textContent = walkthroughPreparing ? 'Preparing the walkthrough…' : 'Live engine paused.';
    return;
  }
  const fen = position.fen, moves = path.slice();
  if (!force && engineCache.has(fen)) {
    engineResult = engineCache.get(fen);
    byId('engine-state').textContent = engineResult.terminal ? 'Game over' : `Best for ${position.turn}: ${engineResult.best_move_san} · depth ${engineResult.depth}`;
    renderEngine();
    return;
  }
  byId('engine-state').textContent = 'Calculating this position…';
  engineTimer = setTimeout(async () => {
    const controller = new AbortController();
    engineController = controller;
    const timer = setTimeout(() => controller.abort(),7000);
    try {
      const response = await fetch(main.dataset.apiBase + '/api/engine', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':main.dataset.csrf},
        body:JSON.stringify({card_id:cardId,moves}),signal:controller.signal});
      const result = await response.json();
      if (sequence !== engineSequence || position.fen !== fen) return;
      if (!response.ok) throw new Error(result.error || 'Engine unavailable');
      if (result.card_id !== cardId || result.fen !== fen) throw new Error('Engine position mismatch');
      engineResult = result;
      if (engineCache.size >= 128) engineCache.delete(engineCache.keys().next().value);
      engineCache.set(fen,result);
      byId('engine-state').textContent = result.terminal ? 'Game over' : `Best for ${position.turn}: ${result.best_move_san} · depth ${result.depth}`;
      renderEngine();
    } catch (error) {
      if (sequence === engineSequence) {
        const text = error.name === 'AbortError' ? 'Engine request timed out; refresh to retry.' : error.message;
        byId('engine-state').textContent = text;
        if (/Engine is busy/i.test(text) && busyRetries < 2) {
          engineTimer = setTimeout(() => {
            if (sequence === engineSequence && position.fen === fen) scheduleEngine(true,busyRetries + 1);
          },750);
        }
      }
    } finally { clearTimeout(timer); }
  },250);
}
if (byId('live-engine')) {
  byId('live-enabled').addEventListener('change',() => scheduleEngine());
  byId('arrow-enabled').addEventListener('change',renderEngine);
  byId('engine-retry').addEventListener('click',() => scheduleEngine(true));
  ['coaching','reflection'].forEach(tab => {
    byId(`tab-${tab}`).addEventListener('click',() => { studyTab = tab; render(); });
    byId(`tab-${tab}`).addEventListener('keydown',event => {
      if (['ArrowLeft','ArrowRight'].includes(event.key)) {
        studyTab = studyTab === 'coaching' ? 'reflection' : 'coaching';
        render(); byId(`tab-${studyTab}`).focus(); event.preventDefault();
      }
    });
  });
}

function leaveWalkthrough() {
  walkthroughSequence++;
  walkthrough = null;
  walkthroughPreparing = false;
  if (byId('walk-text')) {
    byId('walk-text').textContent = 'Follow your idea and the recommended line, one move at a time.';
    commentaryStatus = 'Commentary has not been requested.';
    if (example) byId('example-line').textContent = example.line;
  }
}

function walkBranch() {
  return walkthrough?.evidence.branches.find(branch => branch.id === walkthrough.branch);
}
function walkComment() {
  if (!walkthrough?.ply) return null;
  return walkthrough.comments.find(item => item.branch === walkthrough.branch && item.ply === walkthrough.ply);
}
function renderWalkthrough() {
  if (!byId('walk-start')) return;
  byId('arrow-enabled').disabled = !!walkthrough && !interactiveCoach;
  const branch = walkBranch();
  if (byId('recommended-line')) {
    const identical = !!branch && branch.steps.map(step => step.uci).join(' ') === example?.moves.join(' ');
    // One line when the saved recommendation and active branch agree;
    // otherwise distinguish the fixed starting-position line from exploration.
    byId('recommended-line').hidden = identical;
    byId('recommended-label').textContent = 'Recommended line · starting position';
    byId('example-line').hidden = !branch;
    byId('branch-line-label').hidden = !branch || identical;
  }
  const current = (coachBrowsing || (coachDeviated && interactiveCoach)) ? null : branch?.steps[walkthrough.ply - 1];
  const comment = walkComment();
  const relevant = new Set(comment?.fact_ids || current?.fallback_fact_ids || current?.facts.filter(fact =>
    ['capture','check','promotion','outcome'].includes(fact.id)).map(fact => fact.id) || []);
  if (current && !relevant.size) relevant.add('move');
  const highlights = new Set(current?.facts.filter(fact => relevant.has(fact.id)).flatMap(fact => fact.squares) || []);
  squares.forEach(button => button.classList.toggle('coach-highlight',highlights.has(button.dataset.square)));
  byId('coach-compare').hidden = !interactiveCoach || !example || !!walkthrough?.evidence.same_move;
  byId('walk-start').hidden = !interactiveCoach && !selfAnalysis;
  byId('walk-start').disabled = busy || walkthroughPreparing;
  byId('walk-start').setAttribute('aria-pressed',String(selfAnalysis));
  byId('walk-branches').hidden = !walkthrough;
  byId('walk-navigation').hidden = !walkthrough;
  byId('walk-end').hidden = !walkthrough || (interactiveCoach && !coachFinished);
  byId('walk-comparison').hidden = !walkthrough;
  byId('commentary-status').textContent = commentaryStatus;
  if (byId('branch-line-label')) {
    byId('branch-line-label').hidden = !walkthrough || branch.steps.map(step => step.uci).join(' ') === example?.moves.join(' ');
    byId('branch-line-label').textContent = coachDeviated ? 'Prepared line (you are exploring another variation)'
      : walkthrough?.branch === 'recommended' ? 'Playing the recommended variation' : 'Playing your proposed variation';
  }
  if (!walkthrough) {
    if (!selfAnalysis && coachNotice && stage === 'explore') byId('walk-text').textContent = coachNotice;
    return;
  }
  byId('walk-text').textContent = walkthrough.ply === 0
    ? `Start with ${branch.root_san}. Select Next move to see what follows.`
    : comment?.text || current?.fallback || coachNotice;
  if (interactiveCoach) byId('walk-text').textContent = coachBrowsing
    ? `Reviewing move ${path.length}: ${position.sans.at(-1) || 'starting position'}. Use Next to return to the latest position.`
    : coachNotice + (coachFinished ? '' : ' Your turn—play your continuation on the board.');
  byId('walk-comparison').textContent = walkthrough.evidence.same_move ? 'Your move matches the recommendation.'
    : walkthrough.evidence.comparison_uncertain ? 'The comparison is uncertain at these search budgets. Explore both possibilities.'
    : 'Two illustrative lines, compared at matching search budgets.';
  byId('walk-your').setAttribute('aria-pressed',String(walkthrough.branch === 'your'));
  byId('walk-recommended').setAttribute('aria-pressed',String(walkthrough.branch === 'recommended'));
  byId('walk-recommended').hidden = walkthrough.evidence.same_move;
  byId('walk-count').textContent = `${walkthrough.ply} / ${branch.steps.length}`;
  byId('walk-previous').disabled = busy || walkthrough.ply === 0;
  byId('walk-next').disabled = busy || walkthrough.ply >= branch.steps.length;
  ['walk-your','walk-recommended','walk-free','walk-reflect'].forEach(id => { byId(id).disabled = busy; });
  byId('example-line').replaceChildren();
  branch.steps.forEach(step => {
    const span = document.createElement('span');
    span.textContent = step.san + ' ';
    span.className = step.ply === walkthrough.ply ? 'active-ply' : '';
    if (step.ply === walkthrough.ply) span.setAttribute('aria-current','step');
    byId('example-line').append(span);
  });
}
async function showWalkPly(branchId, ply) {
  if (!walkthrough) return;
  await action(async () => {
    const branch = walkthrough.evidence.branches.find(item => item.id === branchId);
    if (!branch || ply < 0 || ply > branch.steps.length) return;
    await setPath(branch.steps.slice(0,ply).map(step => step.uci),`${branchId === 'your' ? 'Your move' : 'Recommended move'} · ${ply} / ${branch.steps.length}`);
    walkthrough.branch = branchId; walkthrough.ply = ply;
    message(ply === branch.steps.length ? 'End of this illustrative line. Compare the other branch or keep a takeaway.' : 'Step through the line at your own pace.');
  });
}
async function requestWalkCommentary(sequence, evidence) {
  commentaryStatus = 'AI commentary is loading; board facts are available now.';
  renderWalkthrough();
  try {
    const result = await api('/api/walkthrough/commentary',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({card_id:cardId,proposed_move_uci:proposal.uci,walkthrough_id:evidence.walkthrough_id,consent:true})});
    if (sequence !== walkthroughSequence || walkthrough?.evidence.walkthrough_id !== evidence.walkthrough_id) return;
    if (result.walkthrough_id !== evidence.walkthrough_id) throw new Error('Commentary belongs to a different walkthrough.');
    walkthrough.comments = result.available ? result.steps : [];
    commentaryStatus = result.available ? 'AI commentary is available; compare it with the moves on the board.' : result.message;
    renderWalkthrough();
  } catch (error) {
    if (sequence === walkthroughSequence && walkthrough) {
      commentaryStatus = 'AI commentary is unavailable. Board facts remain available.';
      renderWalkthrough();
    }
  }
}
async function startWalkthrough() {
  selfAnalysis = false;
  await action(async () => {
    const sequence = ++walkthroughSequence;
    walkthroughPreparing = true;
    byId('walk-text').textContent = 'Preparing coach replies…';
    try {
      // Pause an in-flight live request before claiming the shared engine slot.
      clearTimeout(engineTimer); engineController?.abort(); engineSequence++;
      const evidence = await api('/api/walkthrough',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({card_id:cardId,proposed_move_uci:proposal.uci})});
      if (sequence !== walkthroughSequence) return;
      walkthrough = {evidence,branch:'your',ply:0,comments:[]};
      coachFinished = false; coachDeviated = false;
      coachNotice = evidence.same_move ? 'Nice—you found the engine-recommended move!' : 'Let’s see the reply to your idea.';
      try { await setPath([],'Your move · start'); }
      catch (error) { leaveWalkthrough(); throw error; }
      // Commentary deliberately runs outside action(): navigating and saving
      // never wait for the provider.
      requestWalkCommentary(sequence,evidence);
      if (interactiveCoach) {
        await setPath([proposal.uci], 'Your proposed move');
        walkthrough.ply = 1;
        await coachReply();
      }
    } catch (error) {
      byId('walk-text').textContent = 'Could not prepare coach lines. Use Self analysis, or reset and try again.';
      throw error;
    } finally { walkthroughPreparing = false; if (walkthrough) scheduleEngine(); }
  });
}
async function liveCoachReply() {
  coachAwaitingReply = true;
  clearTimeout(engineTimer); engineController?.abort(); engineSequence++;
  const fen = position.fen, moves = path.slice(), sequence = walkthroughSequence;
  try {
    const result = await api('/api/engine',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({card_id:cardId,moves})});
    if (sequence !== walkthroughSequence || position.fen !== fen) return;
    if (result.fen !== fen) throw new Error('Engine position mismatch');
    if (result.terminal) {
      coachFinished = true; coachAwaitingReply = false;
      coachNotice = 'This variation has ended. Keep a takeaway or take back a move.';
      return;
    }
    if (!position.legal_moves.includes(result.best_move_uci)) throw new Error('Engine reply is not legal');
    const score = result.mate !== null ? `mate score ${result.mate}` : `${(result.centipawns / 100).toFixed(2)}`;
    await pauseForReply();
    await setPath([...moves,result.best_move_uci], 'Engine reply');
    coachAwaitingReply = false;
    coachNotice = `Engine reply: ${result.best_move_san}. Before this reply: ${score}, White perspective, short search. Your turn.`;
    coachFinished = !!position.outcome || path.length >= 126;
    if (coachFinished) coachNotice += ' Reflect or reset to continue.';
    message(coachFinished ? 'This continuation is finished.' : 'Your turn—play your next move.');
  } catch (error) {
    coachNotice = 'The engine reply is unavailable. Retry, take back, or reset; your notes are preserved.';
    throw error;
  } finally { renderWalkthrough(); }
}
async function pauseForReply() {
  render();
  message('Your move is on the board. The coach is about to reply…');
  await new Promise(resolve => setTimeout(resolve,900));
}
async function coachReply() {
  const branch = walkBranch();
  const reply = branch?.steps[walkthrough.ply];
  if (reply) {
    await pauseForReply();
    await setPath([...path,reply.uci], 'Coach reply');
    walkthrough.ply++;
    coachNotice += ' ' + reply.fallback;
  }
  coachFinished = walkthrough.ply >= branch.steps.length || !!position.outcome;
  if (coachFinished) coachNotice += ' Great work—you played through this engine line. Choose another puzzle or keep a reflection.';
  message(coachFinished ? 'This continuation is finished.' : 'Your turn—play your next move.');
  renderWalkthrough();
}
if (byId('walk-start')) {
  byId('walk-start').addEventListener('click',() => action(async () => {
    if (selfAnalysis) { selfAnalysis = false; coachNotice = 'Coach replies are on. Play your next move.'; if (!proposal) { stage = 'play'; byId('example').hidden = true; } byId('arrow-enabled').checked = false; byId('walk-text').textContent = 'Coach replies are on. Play your next move.'; return; }
    leaveWalkthrough(); selfAnalysis = true; coachNotice = '';
    if (!example) example = await api('/api/reveal');
    stage = 'explore'; byId('example').hidden = false;
    byId('recommended-line').textContent = example.line;
    byId('arrow-enabled').checked = true;
    byId('walk-text').textContent = 'Self analysis: play both sides. Best-move arrows are enabled.';
    scheduleEngine();
  }));
  byId('coach-prev').addEventListener('click',() => action(() => setPath(path.slice(0,-1),'Previous move',false)));
  byId('coach-next').addEventListener('click',() => action(() => setPath(coachTimeline.slice(0,path.length+1),'Next move',false)));
  byId('coach-save').addEventListener('click',() => { studyTab = 'reflection'; render(); byId('takeaway').focus(); });
  byId('coach-reply-retry').addEventListener('click',() => action(liveCoachReply));
  byId('coach-reset').addEventListener('click',() => action(async () => {
    leaveWalkthrough(); coachAwaitingReply = false; coachFinished = false; coachDeviated = false;
    await setPath([], 'Starting position'); stage = 'play'; proposal = null; byId('example').hidden = true;
    message('Play a new idea. Your notes are preserved.');
  }));
  byId('coach-back').addEventListener('click',() => action(async () => {
    const count = selfAnalysis || !interactiveCoach || coachAwaitingReply || stage !== 'explore' ? 1 : 2;
    coachAwaitingReply = false; coachFinished = false;
    await setPath(path.slice(0,Math.max(0,path.length-count)), 'Take back');
    if (!path.length) { leaveWalkthrough(); stage = 'play'; proposal = null; byId('example').hidden = true; }
    else if (walkthrough) {
      const branch = walkBranch();
      coachDeviated = path.some((move,index) => branch.steps[index]?.uci !== move);
      walkthrough.ply = Math.min(path.length,branch.steps.length);
      coachNotice = 'Try another move. Your notes are preserved.';
    }
  }));

  byId('coach-compare').addEventListener('click',() => action(async () => {
    selfAnalysis = false;
    if (!walkthrough) {
      await setPath([example.moves[0]], 'Recommended move');
      await liveCoachReply();
      return;
    }
    const branch = walkthrough.evidence.branches.find(item => item.id === 'recommended');
    if (!branch) return;
    walkthrough.branch = 'recommended'; walkthrough.ply = 1; coachFinished = false; coachDeviated = false;
    coachAwaitingReply = false;
    coachNotice = 'One recommended continuation to consider.';
    await setPath([branch.steps[0].uci], 'Recommended move');
    await coachReply();
  }));
  byId('walk-your').addEventListener('click',() => showWalkPly('your',0));
  byId('walk-recommended').addEventListener('click',() => showWalkPly('recommended',0));
  byId('walk-previous').addEventListener('click',() => showWalkPly(walkthrough.branch,walkthrough.ply-1));
  byId('walk-next').addEventListener('click',() => showWalkPly(walkthrough.branch,walkthrough.ply+1));
  byId('walk-free').addEventListener('click',() => {
    leaveWalkthrough(); byId('walk-text').textContent = 'Explore freely, or start the walkthrough again.';
    byId('example-line').textContent = example.line;
    scheduleEngine(); render();
  });
  byId('walk-reflect').addEventListener('click',() => { studyTab = 'reflection'; render(); byId('tab-reflection').focus(); });
  let infoPinned = false;
  const info = byId('coach-info'), panel = byId('coach-info-panel'), wrapper = info.parentElement;
  const showInfo = show => { panel.hidden = !show; info.setAttribute('aria-expanded',String(show)); };
  wrapper.addEventListener('pointerenter',() => showInfo(true));
  wrapper.addEventListener('pointerleave',() => { if (!infoPinned && !wrapper.contains(document.activeElement)) showInfo(false); });
  wrapper.addEventListener('focusin',() => showInfo(true));
  wrapper.addEventListener('focusout',event => { if (!infoPinned && !wrapper.contains(event.relatedTarget)) showInfo(false); });
  info.addEventListener('click',() => { infoPinned = !infoPinned; showInfo(infoPinned); });
  wrapper.addEventListener('keydown',event => { if (event.key === 'Escape') { infoPinned = false; showInfo(false); info.focus(); event.preventDefault(); } });
}
load();
