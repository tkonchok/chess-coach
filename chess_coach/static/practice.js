'use strict';

// UI state belongs to this tab. The server reconstructs/validates every move path;
// reflections deliberately never leave the browser in milestone 6A.
const byId = (id) => document.getElementById(id);
const main = document.querySelector('main');
const cardId = main.dataset.cardId;
const squares = Array.from(document.querySelectorAll('.square'));
const assets = new Map(Array.from(document.querySelectorAll('template[data-piece]'))
  .map((template) => [template.dataset.piece, template.content]));
const pieceNames = {p: 'pawn', n: 'knight', b: 'bishop', r: 'rook', q: 'queen', k: 'king'};
let position = null;
let path = [];
let selected = null;
let proposal = null;
let stage = 'play'; // play -> reflect -> explore; returning to root is not a fresh attempt.
let busy = false;
let example = null;
let exampleStep = 0;
let boardLabel = 'Starting position';
let promotionChoices = [];
let focusSquare = squares[0];

function message(text) { byId('status').textContent = text; }
function canPlay() { return position && !busy && stage !== 'reflect' && !byId('promotion').open; }
function owned(square) {
  const symbol = position?.pieces[square];
  return symbol && (symbol === symbol.toUpperCase()) === (position.turn === 'white');
}

function render() {
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
  byId('reveal').disabled = busy || stage !== 'reflect';
  byId('skip').disabled = busy || stage !== 'reflect';
  byId('reasoning').readOnly = stage === 'explore';
  byId('playback').hidden = stage !== 'explore';
  byId('previous').disabled = busy || !example || exampleStep <= 0;
  byId('next').disabled = busy || !example || exampleStep >= example.moves.length;
  byId('step-count').textContent = `Example ${exampleStep} / ${example?.moves.length ?? 0}`;
  byId('stage-label').textContent = {play: '1 · Play', reflect: '2 · Explain', explore: '3 · Explore and reflect'}[stage];
  byId('stage-title').textContent = {play: 'What would you play?', reflect: 'What was your idea?', explore: 'What can you take from this?'}[stage];
  byId('stage-help').textContent = {
    play: 'Choose your move on the board. Legal destinations will be highlighted.',
    reflect: 'Think about the reply you expected. You can explain or skip before revealing.',
    explore: 'Your original idea is kept below. Use the separate takeaway field for what you learned.'
  }[stage];
}

async function api(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The request failed.');
    if (result.card_id !== cardId) throw new Error('This card changed. Copy your notes, then reload.');
    return result;
  } finally { clearTimeout(timer); }
}

async function action(work) {
  if (busy) return;
  busy = true;
  selected = null;
  render();
  try { await work(); }
  catch (error) {
    message(error.name === 'AbortError'
      ? 'The server did not respond in time. Your board and notes are unchanged; try again.'
      : `Could not complete that action: ${error.message} Your notes are still here.`);
  } finally { busy = false; render(); }
}

async function setPath(nextPath, label) {
  const result = await api('/api/position', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({card_id: cardId, moves: nextPath}),
  });
  // Commit UI changes only after the complete path has been validated.
  position = result;
  path = nextPath.slice();
  boardLabel = label;
}

async function load() {
  await action(async () => {
    position = await api('/api/position');
    byId('retry').hidden = true;
    message('Choose a move. There is no timer.');
  });
  byId('retry').hidden = !!position;
}

async function play(uci) {
  await action(async () => {
    const proposing = stage === 'play';
    await setPath([...path, uci], proposing ? 'Your proposed move' : 'Your exploration');
    if (proposing) {
      proposal = {uci, san: position.sans[0]};
      stage = 'reflect';
      render();
      byId('reasoning').focus();
      message(`You proposed ${proposal.san}. What reply did you expect?`);
    } else {
      message(position.outcome ? `This exploration ends ${position.outcome}. You can undo or return to the start.`
        : `Played ${position.sans.at(-1)}. You can explore the reply or return to the reviewed line.`);
    }
  });
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
  promotionChoices = [];
  render();
  focusSquare.focus({preventScroll: true});
});

async function reveal(skipped) {
  if (stage !== 'reflect') return;
  if (!skipped && !byId('reasoning').value.trim()) {
    message('Write a thought, or use “Skip reflection and reveal”.');
    byId('reasoning').focus();
    return;
  }
  await action(async () => {
    const result = await api('/api/reveal');
    await setPath([], 'Reviewed example · starting position');
    example = result;
    exampleStep = 0;
    stage = 'explore';
    byId('example-line').textContent = example.line;
    byId('explanation').textContent = example.explanation;
    byId('actual-move').textContent = `In the original game: ${example.played_move_san}. This is not a right/wrong grade.`;
    byId('reasoning-note').textContent = skipped
      ? 'Reflection skipped. Any draft is retained unchanged; record new thoughts in the takeaway below.'
      : 'Your pre-reveal reasoning is now kept unchanged. Record new thoughts in the takeaway below.';
    byId('example').hidden = false;
    render();
    byId('example').focus();
    message('The example is revealed. Your proposed move and initial reasoning are preserved.');
  });
}

byId('reveal').addEventListener('click', () => reveal(false));
byId('skip').addEventListener('click', () => reveal(true));
byId('retry').addEventListener('click', load);
byId('reset').addEventListener('click', () => action(async () => {
  await setPath([], 'Starting position');
  if (stage === 'reflect') stage = 'play';
  if (stage === 'explore') exampleStep = 0;
  message('Back at the start. Your proposed move and notes are preserved.');
}));
byId('your-move').addEventListener('click', () => action(async () => {
  await setPath([proposal.uci], 'Your proposed move');
  if (stage === 'play') stage = 'reflect';
  message(`Your proposed move was ${proposal.san}.`);
}));
byId('undo').addEventListener('click', () => action(async () => {
  await setPath(path.slice(0, -1), 'Your exploration');
  message('Undid one exploration move. Your original proposal and notes are unchanged.');
}));
function showExample(step) {
  return action(async () => {
    await setPath(example.moves.slice(0, step), `Reviewed example · step ${step}`);
    exampleStep = step;
    message(step ? `Example: ${position.sans.join(' ')}` : 'Reviewed example: starting position.');
  });
}
byId('previous').addEventListener('click', () => showExample(Math.max(0, exampleStep - 1)));
byId('next').addEventListener('click', () => showExample(Math.min(example.moves.length, exampleStep + 1)));
byId('finish').addEventListener('click', () => {
  byId('finish-note').hidden = false;
  byId('finish-note').focus();
});
load();
