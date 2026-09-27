# Rubrik Solver GSM Method

A Python project for modeling and experimenting with a 3x3 Rubik's Cube using a Group-State Matrix (GSM) representation.

## Overview

This project defines a legal cube state using:

- corner permutation and orientation
- edge permutation and orientation
- face-turn transformations based on cube-group algebra
- validation for physical cube legality

The Python code provides the GSM cube model and an in-repository two-phase solver. The browser viewer uses that solver through a local API.

## Project structure

```text
RubrikSolver-GSM/
├── main.py
├── README.md
├── pyproject.toml
├── .gitignore
├── app.js
├── index.html
├── solver.py
├── style.css
├── web_server.py
├── docs/
│   ├── algorithm.md
│   ├── solver.md
│   └── usage.md
├── tests/
│   ├── test_gsm.py
│   └── test_solver.py
└── __pycache__/
```

## Run the project

From the project root:

```bash
python main.py
```

Expected output:

```text
All GSM Rubik tests passed.
```

## Run tests

```bash
python -m pytest
```

## Interactive 3D viewer

Start the local viewer and solver server from the project root:

```bash
python web_server.py
```

Then open <http://localhost:8000>. The viewer controls and solver details are documented in [docs/usage.md](docs/usage.md).

## Example usage

```python
from main import CubeState, apply_sequence, is_solved

state = CubeState.solved()
print(is_solved(state))

scrambled = apply_sequence(state, "R U R' U'")
print(is_solved(scrambled))
```

## Documentation

- [docs/algorithm.md](docs/algorithm.md)
- [docs/solver.md](docs/solver.md)
- [docs/usage.md](docs/usage.md)

## Current status

This repository currently provides:

- a valid Rubik's Cube state representation
- face move logic
- state validation
- built-in self-tests
- an interactive browser-based 3D viewer with random scrambles and a step-by-step native two-phase solution panel

The native two-phase solver searches for up to three seconds for a short improvement. If it cannot improve the sequence within that budget, it returns a verified simplified inverse of the move history. Its improved solutions are near-optimal, not guaranteed globally shortest.

## Notes

The implementation follows a standard cubie-level GSM style, where each move is represented as a permutation on positions and modular offsets for orientation.
