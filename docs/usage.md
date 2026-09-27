# Usage Guide

This project models a 3x3 Rubik's Cube using a group-state matrix (GSM) approach.

## Running the project

From the project root:

```bash
python main.py
```

This runs the built-in self-tests and prints:

```text
All GSM Rubik tests passed.
```

## Interactive 3D viewer

From the project root, start Python's local static web server:

```bash
python -m http.server 8000
```

Open <http://localhost:8000> in a browser. Leave the server running while using the viewer; stop it with `Ctrl+C` in the terminal.

The viewer provides clockwise quarter-turn buttons `U`, `D`, `L`, `R`, `F`, and `B`, plus counterclockwise buttons marked with a prime, such as `U'` and `R'`. A prime move is the inverse quarter turn. Move clicks animate and queue in order. Drag the cube to orbit the view, and use **Reset** to return to the solved cube and default view.

The browser viewer currently maintains its cube state in JavaScript and runs separately from the Python GSM engine. The Python engine's move notation additionally supports half turns such as `U2`.

## Example script usage

```python
from main import CubeState, apply_sequence, is_solved

state = CubeState.solved()
print(is_solved(state))

scrambled = apply_sequence(state, "R U R' U'")
print(is_solved(scrambled))
```

## Move syntax

The engine supports standard cube notation:

- `U`, `D`, `L`, `R`, `F`, `B`
- `U2`, `R2`, `F'`, `L'`
- sequences separated by spaces, such as `R U R' U'`

Example:

```python
from main import CubeState, apply_sequence

state = apply_sequence(CubeState.solved(), "R U R' U'")
print(state)
```

## State validation

The model includes built-in validity checks via `verify_state()`. This ensures:

- all corners are present exactly once
- all edges are present exactly once
- orientation values stay in valid ranges
- permutation parity is consistent

## Next steps

The current code is a correct mathematical cube engine and validation layer. The next logical expansion is a solver that searches for move sequences to reach the solved state.
