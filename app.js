const cube = document.getElementById('cube');
const resetBtn = document.getElementById('resetBtn');
const scrambleBtn = document.getElementById('scrambleBtn');
const solveBtn = document.getElementById('solveBtn');
const nextStepBtn = document.getElementById('nextStepBtn');
const playSolutionBtn = document.getElementById('playSolutionBtn');
const solutionCount = document.getElementById('solutionCount');
const solutionSteps = document.getElementById('solutionSteps');
const solverStatus = document.getElementById('solverStatus');

const faceNames = ['front', 'back', 'right', 'left', 'top', 'bottom'];
const faceVectors = {
  front: [0, 0, 1],
  back: [0, 0, -1],
  right: [1, 0, 0],
  left: [-1, 0, 0],
  top: [0, -1, 0],
  bottom: [0, 1, 0],
};
const vectorFaces = Object.fromEntries(
  Object.entries(faceVectors).map(([face, vector]) => [vector.join(','), face])
);
const faceColors = {
  front: '#22c55e',
  back: '#2563eb',
  right: '#ef4444',
  left: '#f97316',
  top: '#f8fafc',
  bottom: '#facc15',
};

const cubieSize = 54;
const spacing = 58;
const turnDuration = 220;
const moves = {
  U: { axis: 1, layer: -1, turns: -1 },
  D: { axis: 1, layer: 1, turns: 1 },
  L: { axis: 0, layer: -1, turns: -1 },
  R: { axis: 0, layer: 1, turns: 1 },
  F: { axis: 2, layer: 1, turns: 1 },
  B: { axis: 2, layer: -1, turns: -1 },
};
let cubies = [];
let moveQueue = [];
let moveHistory = [];
let solutionMoves = [];
let solutionIndex = 0;
let solutionStale = false;
let isTurning = false;
let scrambleActive = false;
let isSolving = false;
let isSolutionPlayback = false;
let solverAvailable = false;

function randomIndex(length) {
  const cryptoApi = window.crypto;
  if (!cryptoApi?.getRandomValues) {
    return Math.floor(Math.random() * length);
  }

  const rangeLimit = Math.floor(0x100000000 / length) * length;
  const randomValue = new Uint32Array(1);
  do {
    cryptoApi.getRandomValues(randomValue);
  } while (randomValue[0] >= rangeLimit);

  return randomValue[0] % length;
}

function createScramble(length = 30) {
  const moveFaces = Object.keys(moves);
  const scramble = [];
  let previousFace = null;

  for (let index = 0; index < length; index++) {
    const availableFaces = moveFaces.filter((face) => face !== previousFace);
    const face = availableFaces[randomIndex(availableFaces.length)];
    const clockwise = randomIndex(2) === 0;
    scramble.push(clockwise ? face : `${face}'`);
    previousFace = face;
  }

  return scramble;
}

function renderSolution() {
  solutionSteps.classList.toggle('is-stale', solutionStale);
  solutionCount.textContent = `${solutionMoves.length} ${solutionMoves.length === 1 ? 'move' : 'moves'}`;
  solutionSteps.replaceChildren();

  solutionMoves.forEach((move, index) => {
    const step = document.createElement('li');
    step.className = 'solution-step';
    step.textContent = `${index + 1}. ${move}`;
    if (index === solutionIndex) step.setAttribute('aria-current', 'step');
    if (index < solutionIndex) step.classList.add('is-complete');
    solutionSteps.appendChild(step);
  });
}

function updateSolutionControls() {
  const queueBusy = isTurning || moveQueue.length > 0;
  const inputLocked = isSolving || isSolutionPlayback || scrambleActive;

  solveBtn.disabled = !solverAvailable || isSolving || queueBusy;
  nextStepBtn.disabled = isSolving || queueBusy || solutionStale || solutionIndex >= solutionMoves.length;
  playSolutionBtn.disabled = isSolving || queueBusy || solutionStale || solutionIndex >= solutionMoves.length;
  scrambleBtn.disabled = inputLocked;
  resetBtn.disabled = isSolving;

  for (const button of document.querySelectorAll('[data-move]')) {
    button.disabled = inputLocked;
  }
}

function clearSolution(status) {
  solutionMoves = [];
  solutionIndex = 0;
  solutionStale = false;
  renderSolution();
  solverStatus.textContent = status;
}

async function checkSolverAPI() {
  try {
    const response = await fetch('/api/health');
    if (!response.ok) throw new Error('Native solver server is unavailable.');
    const result = await response.json();
    solverAvailable = result.ready === true;
    if (!solverAvailable) throw new Error('Native solver server is unavailable.');
  } catch {
    solverAvailable = false;
    solverStatus.textContent = 'Start web_server.py to use the native solver.';
  }
  updateSolutionControls();
}

async function requestSolution() {
  if (isSolving || isTurning || moveQueue.length > 0) return;

  isSolving = true;
  clearSolution('Searching for a shorter solution (up to 3 seconds). First use may prepare pruning tables.');
  updateSolutionControls();

  try {
    const response = await fetch('/api/solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ moves: moveHistory.slice() }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The native solver failed.');

    solutionMoves = result.moves;
    solutionIndex = 0;
    solutionStale = false;
    renderSolution();
    if (solutionMoves.length === 0) {
      solverStatus.textContent = 'The cube is already solved.';
    } else if (result.strategy === 'fallback') {
      solverStatus.textContent = `Verified inverse-history solution ready: ${solutionMoves.length} moves.`;
    } else {
      solverStatus.textContent = `Two-phase improvement ready: ${solutionMoves.length} moves.`;
    }
  } catch (error) {
    clearSolution(error.message || 'The native solver failed.');
  } finally {
    isSolving = false;
    updateSolutionControls();
  }
}

function enqueueMove(token, source = 'manual') {
  if (source === 'manual' && solutionMoves.length > 0 && !solutionStale) {
    solutionStale = true;
    solutionSteps.classList.add('is-stale');
    solverStatus.textContent = 'Cube changed manually. This solution is for the previous state; find a new one to replace it.';
    updateSolutionControls();
  }

  moveQueue.push({ token, source });
  updateSolutionControls();
  playNextMove();
}

function createCubie(x, y, z) {
  const element = document.createElement('div');
  element.className = 'cubelet';
  element.style.left = `${-cubieSize / 2}px`;
  element.style.top = `${-cubieSize / 2}px`;

  const stickers = {};
  for (const face of faceNames) {
    const [faceX, faceY, faceZ] = faceVectors[face];
    const visible =
      (faceX !== 0 && x === faceX) ||
      (faceY !== 0 && y === faceY) ||
      (faceZ !== 0 && z === faceZ);
    const faceElement = document.createElement('div');
    faceElement.className = `face ${face}`;

    if (visible) {
      stickers[face] = faceColors[face];
    }

    element.appendChild(faceElement);
  }

  return { element, position: [x, y, z], stickers };
}

function buildCube() {
  cube.replaceChildren();
  cubies = [];

  for (let x = -1; x <= 1; x++) {
    for (let y = -1; y <= 1; y++) {
      for (let z = -1; z <= 1; z++) {
        const cubie = createCubie(x, y, z);
        cubies.push(cubie);
        cube.appendChild(cubie.element);
      }
    }
  }

  renderCubies();
}

function renderCubies() {
  for (const cubie of cubies) {
    const [x, y, z] = cubie.position;
    cubie.element.dataset.position = `${x},${y},${z}`;
    cubie.element.style.transform = `translate3d(${x * spacing}px, ${y * spacing}px, ${z * spacing}px)`;

    for (const face of faceNames) {
      const faceElement = cubie.element.querySelector(`.face.${face}`);
      faceElement.style.background = cubie.stickers[face] || '#101820';
    }
  }
}

function rotateVector(vector, axis, quarterTurns) {
  let [x, y, z] = vector;
  const count = (quarterTurns + 4) % 4;

  for (let turn = 0; turn < count; turn++) {
    if (axis === 0) [y, z] = [-z, y];
    if (axis === 1) [x, z] = [z, -x];
    if (axis === 2) [x, y] = [-y, x];
  }

  return [x, y, z];
}

function rotateCubieState(cubie, move) {
  cubie.position = rotateVector(cubie.position, move.axis, move.turns);

  const rotatedStickers = {};
  for (const [face, color] of Object.entries(cubie.stickers)) {
    const direction = rotateVector(faceVectors[face], move.axis, move.turns);
    rotatedStickers[vectorFaces[direction.join(',')]] = color;
  }
  cubie.stickers = rotatedStickers;
}

function animateMove(token, source) {
  const baseMove = moves[token[0]];
  const direction = token.endsWith("'") ? -1 : 1;
  const move = { ...baseMove, turns: baseMove.turns * direction };
  const turns = token.endsWith('2') ? 2 : 1;
  const layer = document.createElement('div');
  layer.className = 'turn-layer';

  const movingCubies = cubies.filter((cubie) => cubie.position[move.axis] === move.layer);
  cube.appendChild(layer);
  for (const cubie of movingCubies) {
    layer.appendChild(cubie.element);
  }

  layer.offsetHeight;
  requestAnimationFrame(() => {
    const degrees = move.turns * 90 * turns;
    layer.style.transform = `rotate${['X', 'Y', 'Z'][move.axis]}(${degrees}deg)`;
  });

  window.setTimeout(() => {
    for (const cubie of movingCubies) {
      for (let turn = 0; turn < turns; turn++) {
        rotateCubieState(cubie, move);
      }
      cube.appendChild(cubie.element);
    }
    moveHistory.push(token);
    layer.remove();
    renderCubies();
    if (source === 'solution' && solutionMoves[solutionIndex] === token) {
      solutionIndex++;
      renderSolution();
      if (solutionIndex === solutionMoves.length) {
        solverStatus.textContent = 'Cube solved.';
      } else {
        solverStatus.textContent = `Step ${solutionIndex} of ${solutionMoves.length} complete.`;
      }
    }
    isTurning = false;
    playNextMove();
    updateSolutionControls();
  }, turnDuration);
}

function playNextMove() {
  if (isTurning) return;
  if (moveQueue.length === 0) {
    if (scrambleActive) {
      scrambleActive = false;
      scrambleBtn.disabled = false;
      scrambleBtn.textContent = 'Scramble';
      solverStatus.textContent = 'Scramble complete. Find a solution when ready.';
    }
    isSolutionPlayback = false;
    updateSolutionControls();
    return;
  }

  const nextMove = moveQueue.shift();
  if (nextMove.token === 'RESET') {
    buildCube();
    moveHistory = [];
    currentX = -32;
    currentY = -35;
    updateCubeTransform();
    solverStatus.textContent = 'Cube reset.';
    playNextMove();
    return;
  }

  isTurning = true;
  updateSolutionControls();
  animateMove(nextMove.token, nextMove.source);
}

let currentX = -32;
let currentY = -35;
let isDragging = false;
let lastX = 0;
let lastY = 0;

function updateCubeTransform() {
  cube.style.transform = `translate(-50%, -50%) rotateX(${currentX}deg) rotateY(${currentY}deg)`;
}

cube.addEventListener('pointerdown', (event) => {
  isDragging = true;
  lastX = event.clientX;
  lastY = event.clientY;
});

window.addEventListener('pointermove', (event) => {
  if (!isDragging) return;

  const dx = event.clientX - lastX;
  const dy = event.clientY - lastY;

  currentY += dx * 0.35;
  currentX -= dy * 0.25;
  lastX = event.clientX;
  lastY = event.clientY;
  updateCubeTransform();
});

window.addEventListener('pointerup', () => {
  isDragging = false;
});

window.addEventListener('pointerleave', () => {
  isDragging = false;
});

if (resetBtn) {
  resetBtn.addEventListener('click', () => {
    moveQueue = [{ token: 'RESET', source: 'reset' }];
    scrambleActive = false;
    isSolutionPlayback = false;
    scrambleBtn.textContent = 'Scramble';
    clearSolution('Resetting cube.');
    playNextMove();
    updateSolutionControls();
  });
}

if (scrambleBtn) {
  scrambleBtn.addEventListener('click', () => {
    if (scrambleActive) return;
    scrambleActive = true;
    scrambleBtn.textContent = 'Scrambling...';
    clearSolution('Scrambling cube with 30 random moves.');
    moveQueue.push(...createScramble().map((token) => ({ token, source: 'scramble' })));
    updateSolutionControls();
    playNextMove();
  });
}

solveBtn.addEventListener('click', requestSolution);

nextStepBtn.addEventListener('click', () => {
  if (solutionIndex >= solutionMoves.length) return;
  solverStatus.textContent = `Applying move ${solutionIndex + 1} of ${solutionMoves.length}.`;
  enqueueMove(solutionMoves[solutionIndex], 'solution');
});

playSolutionBtn.addEventListener('click', () => {
  const remainingMoves = solutionMoves.slice(solutionIndex);
  if (remainingMoves.length === 0) return;

  isSolutionPlayback = true;
  solverStatus.textContent = `Playing ${remainingMoves.length} remaining moves.`;
  moveQueue.push(...remainingMoves.map((token) => ({ token, source: 'solution' })));
  updateSolutionControls();
  playNextMove();
});

for (const button of document.querySelectorAll('[data-move]')) {
  button.addEventListener('click', () => {
    enqueueMove(button.dataset.move);
  });
}

buildCube();
updateCubeTransform();
renderSolution();
updateSolutionControls();
checkSolverAPI();
