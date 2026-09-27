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

From the project root, start the local viewer and native solver API:

```bash
python web_server.py
```

Open <http://localhost:8000> in a browser. Leave the server running while using the viewer; stop it with `Ctrl+C` in the terminal.

The viewer provides clockwise quarter-turn buttons `U`, `D`, `L`, `R`, `F`, and `B`, plus counterclockwise buttons marked with a prime, such as `U'` and `R'`. A prime move is the inverse quarter turn. Move clicks animate and queue in order. **Scramble** queues 30 random legal quarter turns, avoiding the same face twice in a row; **Reset** clears pending moves and returns the cube to solved after any current turn finishes. Drag the cube to orbit the view.

The browser keeps its animation state in JavaScript. The local API reconstructs the current position with the Python GSM model before solving. The Python engine also supports half turns such as `U2`. For the solver's coordinates, table cache, timeout, and fallback details, see [solver.md](solver.md).

The **Solution** panel uses the in-repository two-phase solver in `solver.py`, built from the GSM move tables without a third-party solver dependency. Select **Find solution** to get a numbered move list, then use **Next move** to apply one step or **Play all** to animate the remaining steps. The first solve builds pruning tables and can take around a minute; it saves them in `.solver-cache/` so later server starts load them instead of rebuilding. The two-phase search has a three-second budget. If it cannot improve the result in that time, the API returns a verified, simplified inverse of the move history instead. Two-phase improvements are short, but not guaranteed globally shortest.

Manual turns leave the current solution list visible but mark it as belonging to the previous cube state. **Next move** and **Play all** stay disabled until **Find solution** generates a solution for the updated state.

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

The Python code provides the cube engine, validation layer, and native two-phase solver.
