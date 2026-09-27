# Native Solver Notes

This note describes the in-repository solver implementation in `solver.py`, its integration with the browser viewer, and its performance and correctness boundaries. The implementation uses the project's own GSM move tables from `main.py`; it does not import a third-party Rubik's Cube solver.

## Goals and guarantees

The solver aims to produce short solutions quickly for legal 3x3 cube states. It implements a two-phase search over the existing corner and edge representation. It does not prove a globally shortest solution.

The search improvement budget is three seconds. When a state came from the browser viewer, the API also has its exact move history. If search reaches its budget without finding a shorter result, it returns a verified, simplified inverse of that history instead. That fallback is guaranteed to undo the submitted history, but is not guaranteed to be short. The API reports whether a result came from the two-phase search or from the fallback so the UI can describe it accurately.

Move count uses the face-turn metric: `U`, `U'`, and `U2` each count as one move. The solver searches phase-one depths up to 12, phase-two depths up to 18, and total solutions up to 30 face turns.

## State and move conventions

`CubeState` in `main.py` stores:

- `cp`: the corner piece at each corner position
- `co`: corner orientation values in $\mathbb{Z}_3$
- `ep`: the edge piece at each edge position
- `eo`: edge orientation values in $\mathbb{Z}_2$

`MOVE_DATA` defines each clockwise quarter turn as a permutation from new position to old piece, plus orientation offsets. `apply_token()` composes quarter turns to implement standard notation, including prime and half turns. The solver builds all transition tables from these same operations so browser solutions and the GSM engine share one move convention.

The solver validates incoming states with `verify_state()` before searching. It also applies its returned algorithm through `apply_sequence()` and checks that the result equals `CubeState.solved()` before returning it.

## Two-phase search

The phase boundary is the usual subgroup where all corner and edge orientations are solved and the four slice edges occupy slice positions 8 through 11 (`FR`, `FL`, `BL`, `BR` in `EDGES`). Phase one can use all 18 face turns: six faces with clockwise, half-turn, and counterclockwise variants.

Phase-one coordinates:

- Corner orientation: $3^7 = 2{,}187$ coordinates. The eighth corner orientation is determined by the sum constraint.
- Edge orientation: $2^{11} = 2{,}048$ coordinates. The twelfth edge orientation is determined by parity.
- Slice-edge placement: $\binom{12}{4} = 495$ possible position sets.

Phase two stays inside the subgroup. Its ten legal moves are `U`, `U2`, `U'`, `D`, `D2`, `D'`, and the half turns `R2`, `F2`, `L2`, `B2`.

Phase-two coordinates:

- Corner permutation: $8! = 40{,}320$ coordinates.
- Non-slice edge permutation: $8! = 40{,}320$ coordinates.
- Slice-edge permutation: $4! = 24$ coordinates.

The coordinate transitions are generated from `MOVE_DATA` and stored as compact `array` objects. Breadth-first searches from each phase goal build paired pruning tables. Phase one combines corner orientation with slice placement and edge orientation with slice placement. Phase two combines corner permutation with slice permutation and non-slice edge permutation with slice permutation. At a search node, the maximum of the two corresponding table distances is an admissible lower bound on remaining depth.

The search iteratively deepens within the total and phase-specific caps. It prunes repeated turns of the same face and imposes a fixed order on opposite faces, since opposite-face turns commute. These rules remove equivalent move orderings without removing a distinct cube state.

## Persistent table cache

The pruning tables are built lazily on the first non-solved request. On this development machine, cold table generation took about 45 seconds. The table set is then saved to:

```text
.solver-cache/phase-tables-v1.bin
```

The directory is ignored by Git. A later server process loads the cached tables in about 0.01 seconds instead of rebuilding them. The cache file has a version magic header and is checked against expected table dimensions before use. Writes go to a temporary file followed by an atomic replacement; an absent, malformed, or incompatible cache causes a rebuild.

The cache is a locally generated Python pickle and should be treated as trusted local data. Do not substitute a cache file from an untrusted source. Delete `.solver-cache/` to force regeneration or recover from a damaged cache.

## Search deadline and fallback

The recursive search counts visited nodes and checks a monotonic-clock deadline every 1,024 nodes. The deadline covers search after table loading; it does not interrupt first-time pruning-table generation. If search finds a result shorter than the supplied fallback, it returns the searched result. If the budget expires first, the API returns the fallback immediately.

The fallback is computed by reversing the submitted history and inverting each token:

- `U` becomes `U'`
- `U'` becomes `U`
- `U2` remains `U2`

It then simplifies each consecutive block of moves around one axis. The two opposite faces on that axis commute, so their quarter-turn amounts can be combined modulo four. Blocks on different axes retain their order. This gives a quick, verifiable upper bound even when search does not improve it in time.

## Browser and API flow

The viewer tracks completed move tokens in `moveHistory`. Animated manual turns, scrambles, and solution turns are recorded only after their animation completes. Reset rebuilds the solved cube and clears that history.

When **Find solution** is selected:

1. `app.js` posts the move history as JSON to `POST /api/solve`.
2. `web_server.py` replays it from `CubeState.solved()`, validates the resulting GSM state, and computes the inverse-history fallback.
3. `solver.solve()` attempts a two-phase improvement within its time budget.
4. The API returns JSON containing `moves` and `strategy` (`two-phase` or `fallback`).
5. The viewer renders numbered steps. **Next move** applies one token; **Play all** queues the remaining tokens.

`GET /api/health` reports whether the local server is reachable. The web page and API must be served from the same local server, started with `python web_server.py`. The API accepts a JSON object with a list of at most 10,000 standard move tokens and responds with HTTP 400 for malformed or invalid history.

If the user makes a manual move after a solution is displayed, the numbered list remains visible but is marked stale. Playback is disabled because those steps target the earlier state; requesting a new solution replaces the stale list.

## Performance observations

Measured on the current development machine:

- Cold pruning-table build: about 45 seconds once.
- Loading a valid local table cache in a fresh Python process: about 0.01 seconds.
- A seeded 30-move scramble: a 24-move two-phase improvement in about 1.02 seconds with cached tables.
- If no shorter result is found before the three-second search budget, the verified inverse-history fallback is returned.

These are observations, not timing guarantees; machine speed, cache state, and scramble structure affect results.

## Tests

`tests/test_solver.py` covers short and mixed scrambles, solved and invalid states, the time-budget fallback, opposite-face simplification, table-cache serialization, and the invariant that applying every returned solution reaches the solved GSM state.