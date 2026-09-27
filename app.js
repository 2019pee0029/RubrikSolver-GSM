const cube = document.getElementById('cube');
const resetBtn = document.getElementById('resetBtn');

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
let isTurning = false;

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

function animateMove(token) {
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
    layer.remove();
    renderCubies();
    isTurning = false;
    playNextMove();
  }, turnDuration);
}

function playNextMove() {
  if (isTurning || moveQueue.length === 0) return;
  const nextMove = moveQueue.shift();
  if (nextMove === 'RESET') {
    buildCube();
    currentX = -32;
    currentY = -35;
    updateCubeTransform();
    playNextMove();
    return;
  }

  isTurning = true;
  animateMove(nextMove);
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
    moveQueue.push('RESET');
    playNextMove();
  });
}

for (const button of document.querySelectorAll('[data-move]')) {
  button.addEventListener('click', () => {
    moveQueue.push(button.dataset.move);
    playNextMove();
  });
}

buildCube();
updateCubeTransform();
