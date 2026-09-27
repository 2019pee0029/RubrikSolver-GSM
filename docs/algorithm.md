# GSM Cube Model

This project represents the cube in the same way many advanced Rubik's Cube solvers model piece states: by tracking piece positions and orientations separately.

## Data model

The `CubeState` dataclass stores four arrays:

- `cp`: corner permutation
- `co`: corner orientation
- `ep`: edge permutation
- `eo`: edge orientation

This makes the cube state explicit enough to model moves as affine permutations.

## Move encoding

`MOVE_DATA` defines each face move using the mapping:

- new position <- old piece
- orientation updates are applied as modular arithmetic in $\mathbb{Z}_3$ for corners and $\mathbb{Z}_2$ for edges

Because of this, a move is not just a pure permutation. It is a combined permutation plus orientation update.

## Why this matters

This representation is useful because it preserves the underlying algebra of the cube group. It also allows:

- legal-state checks
- inverse move validation
- move composition
- future solver search logic

## Current scope

The Python cube engine and validation layer are used by the in-repository two-phase solver. The solver's coordinates, pruning tables, cache, search deadline, API fallback, and limitations are documented in [solver.md](solver.md).
