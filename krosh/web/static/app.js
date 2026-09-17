/* KROSH browser client.
   All rules and search happen server-side; this file draws state and posts
   clicks. It never decides what is legal. */

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status");
const messageEl = document.getElementById("message");
const setupEl = document.getElementById("setup");
const liveEl = document.getElementById("live");
const historyEl = document.getElementById("history");

const CROWN = `<svg class="crown" viewBox="0 0 24 15" aria-hidden="true">
  <path d="M1 14V2l5 5 6-6 6 6 5-5v12z"/></svg>`;

let gameId = null;
let busy = false;
let setup = { mode: "ai", engine: "greedy", colour: "red", p1Name: "", p2Name: "" };

/* ------------------------------------------------------------ network -- */
async function api(path, body) {
  const options = body
    ? { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) }
    : { method: "POST" };
  const response = await fetch(path, options);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.error || `request failed (${response.status})`);
  }
  return response.json();
}

/* ------------------------------------------------------------- render -- */
function buildBoard() {
  boardEl.replaceChildren();
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const cell = document.createElement("div");
      cell.className = "cell" + ((row + col) % 2 ? " dark" : "");
      cell.dataset.row = row;
      cell.dataset.col = col;
      cell.setAttribute("role", "gridcell");
      boardEl.appendChild(cell);
    }
  }
}

function cellAt(row, col) {
  return boardEl.children[row * 8 + col];
}

function draw(state) {
  const trail = new Set();
  const taken = new Set();
  if (state.last_move) {
    state.last_move.squares.forEach(([r, c]) => trail.add(`${r},${c}`));
    state.last_move.captures.forEach(([r, c]) => taken.add(`${r},${c}`));
  }
  const hints = new Set(state.highlights.map(([r, c]) => `${r},${c}`));
  const chosen = state.selected ? `${state.selected[0]},${state.selected[1]}` : null;
  const ghostAt = state.partial_path.length
    ? state.partial_path[state.partial_path.length - 1]
    : null;

  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const key = `${row},${col}`;
      const cell = cellAt(row, col);
      const value = state.board[row][col];

      cell.className = "cell" + ((row + col) % 2 ? " dark" : "");
      if (trail.has(key)) cell.classList.add("trail");
      if (taken.has(key)) cell.classList.add("taken");
      if (chosen === key) cell.classList.add("chosen");
      const ownPiece = state.turn === "red" ? value > 0 : value < 0;
      if (hints.has(key) || (state.is_human_turn && ownPiece)) {
        cell.classList.add("playable");
      }
      cell.replaceChildren();

      const hiddenOrigin = ghostAt && chosen === key;
      if (value !== 0 && !hiddenOrigin) {
        cell.appendChild(makePiece(value, false));
      }
      if (ghostAt && ghostAt[0] === row && ghostAt[1] === col && state.selected) {
        const origin = state.board[state.selected[0]][state.selected[1]];
        cell.appendChild(makePiece(origin, true));
      }
      if (hints.has(key)) {
        const dot = document.createElement("span");
        dot.className = "hint" + (value !== 0 ? " over-piece" : "");
        cell.appendChild(dot);
      }
    }
  }

  statusEl.textContent = state.status;
  statusEl.classList.toggle("over", state.is_over);
  messageEl.textContent = state.message || "";

  document.getElementById("label-red").textContent = state.labels.red;
  document.getElementById("label-white").textContent = state.labels.white;
  const c = state.counts;
  document.getElementById("count-red").textContent =
    `${c.red_men} men, ${c.red_kings} kings`;
  document.getElementById("count-white").textContent =
    `${c.white_men} men, ${c.white_kings} kings`;

  drawTelemetry(state.last_search);
  drawHistory(state.history);
  document.getElementById("undo").disabled = !state.can_undo;
}

function makePiece(value, ghost) {
  const piece = document.createElement("div");
  piece.className = `piece ${value > 0 ? "red" : "white"}${ghost ? " ghost" : ""}`;
  if (Math.abs(value) === 2) piece.innerHTML = CROWN;
  return piece;
}

function drawTelemetry(search) {
  const blank = "—";
  const set = (id, text) => (document.getElementById(id).textContent = text);
  if (!search) {
    ["t-move", "t-score", "t-depth", "t-nodes", "t-time", "t-rate"]
      .forEach((id) => set(id, blank));
    return;
  }
  set("t-move", search.move);
  set("t-score", (search.score > 0 ? "+" : "") + Math.round(search.score));
  set("t-depth", search.depth);
  set("t-nodes", search.nodes.toLocaleString());
  set("t-time", `${search.time_ms.toFixed(1)} ms`);
  set("t-rate", `${search.nodes_per_second.toLocaleString()}/s`);
}

function drawHistory(entries) {
  historyEl.replaceChildren();
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No moves yet.";
    historyEl.appendChild(empty);
    return;
  }
  for (const entry of entries) {
    const item = document.createElement("li");
    item.className = entry.player;
    item.textContent = entry.engine ? `${entry.move}  (${entry.engine})` : entry.move;
    historyEl.appendChild(item);
  }
  historyEl.scrollTop = historyEl.scrollHeight;
}

/* -------------------------------------------------------------- flow -- */
async function settle(state) {
  draw(state);
  // Hand over to the engine whenever it is the computer's turn. The counter
  // is a guard: if an engine ever returned no move, this would spin forever.
  let guard = 0;
  while (!state.is_over && !state.is_human_turn && guard < 200) {
    state = await api(`/api/game/${gameId}/ai`);
    draw(state);
    guard += 1;
  }
  return state;
}

async function onCellClick(event) {
  const cell = event.target.closest(".cell");
  if (!cell || !gameId || busy) return;
  busy = true;
  try {
    const state = await api(`/api/game/${gameId}/click`, {
      row: Number(cell.dataset.row),
      col: Number(cell.dataset.col),
    });
    await settle(state);
  } catch (error) {
    messageEl.textContent = error.message;
  } finally {
    busy = false;
  }
}

async function startGame() {
  busy = true;
  try {
    const payload = {
      mode: setup.mode,
      engine: setup.engine,
      human_colour: setup.colour,
      p1_name: document.getElementById("p1-name").value.trim(),
      p2_name: document.getElementById("p2-name").value.trim(),
    };
    const data = await api("/api/game", payload);
    gameId = data.game_id;
    setupEl.hidden = true;
    liveEl.hidden = false;
    await settle(data.state);
  } catch (error) {
    messageEl.textContent = error.message;
  } finally {
    busy = false;
  }
}

async function command(path) {
  if (!gameId || busy) return;
  busy = true;
  try {
    const state = await api(`/api/game/${gameId}/${path}`);
    if (path === "reset") {
      await settle(state);
    } else {
      draw(state);
    }
  } catch (error) {
    messageEl.textContent = error.message;
  } finally {
    busy = false;
  }
}

/* ------------------------------------------------------------- setup -- */
function wireChoice(containerId, key, attribute) {
  const container = document.getElementById(containerId);
  container.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    [...container.querySelectorAll(".chip")].forEach((c) =>
      c.classList.toggle("is-on", c === chip));
    setup[key] = chip.dataset[attribute];
    if (key === "mode") {
      const versusHuman = setup.mode === "human";
      document.getElementById("engine-field").classList.toggle("disabled", versusHuman);
      document.getElementById("colour-field").classList.toggle("disabled", versusHuman);
      const namesField = document.getElementById("names-field");
      namesField.hidden = !versusHuman;
      namesField.classList.toggle("disabled", !versusHuman);
    }
  });
}

wireChoice("mode-choices", "mode", "mode");
wireChoice("engine-choices", "engine", "engine");
wireChoice("colour-choices", "colour", "colour");

document.getElementById("start").addEventListener("click", startGame);
document.getElementById("undo").addEventListener("click", () => command("undo"));
document.getElementById("restart").addEventListener("click", () => command("reset"));
document.getElementById("newgame").addEventListener("click", () => {
  gameId = null;
  liveEl.hidden = true;
  setupEl.hidden = false;
  statusEl.textContent = "Choose an opponent to begin.";
  statusEl.classList.remove("over");
  messageEl.textContent = "";
  buildBoard();
});

boardEl.addEventListener("click", onCellClick);
document.addEventListener("keydown", (event) => {
  if (!gameId) return;
  if (event.key === "u" || event.key === "U") command("undo");
  if (event.key === "r" || event.key === "R") command("reset");
});

buildBoard();
