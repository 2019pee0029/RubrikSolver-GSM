# Rubrik Solver GSM Method

A Python project for modeling and experimenting with a 3x3 Rubik's Cube using a Group-State Matrix (GSM) representation.

## Overview

This project defines a legal cube state using:

- corner permutation and orientation
- edge permutation and orientation
- face-turn transformations based on cube-group algebra
- validation for physical cube legality

The code is intentionally focused on the mathematical model of the cube and the correctness of move operations before moving into a full solver.

## Project structure

```text
RubrikSolver-GSM/
├── main.py
├── README.md
├── pyproject.toml
├── .gitignore
├── docs/
│   ├── algorithm.md
│   └── usage.md
├── tests/
│   └── test_gsm.py
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
- [docs/usage.md](docs/usage.md)

## Current status

This repository currently provides:

- a valid Rubik's Cube state representation
- face move logic
- state validation
- built-in self-tests

The next step would be implementing a solver that searches for and returns a move sequence from a scrambled cube to solved state.

## Notes

The implementation follows a standard cubie-level GSM style, where each move is represented as a permutation on positions and modular offsets for orientation.
