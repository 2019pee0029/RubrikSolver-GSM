"""Native two-phase Rubik's Cube solver built on the GSM move model."""

from array import array
from dataclasses import dataclass
from itertools import combinations
from math import factorial
from os import replace
from pathlib import Path
from pickle import HIGHEST_PROTOCOL, UnpicklingError, dump, load
from tempfile import NamedTemporaryFile
from threading import Lock
from time import monotonic

from main import MOVE_DATA, CubeState, apply_sequence, apply_token, verify_state

PHASE1_TOKENS = tuple(
    face + suffix
    for face in ("U", "R", "F", "D", "L", "B")
    for suffix in ("", "2", "'")
)
PHASE2_TOKENS = (
    "U", "U2", "U'", "D", "D2", "D'", "R2", "F2", "L2", "B2"
)
PHASE1_MOVE_COUNT = len(PHASE1_TOKENS)
PHASE2_MOVE_COUNT = len(PHASE2_TOKENS)
PHASE1_TOKEN_INDEX = {token: index for index, token in enumerate(PHASE1_TOKENS)}
PHASE2_FACE_ORDER = {face: index for index, face in enumerate("URFDLB")}
OPPOSITE_FACE = {"U": "D", "D": "U", "R": "L", "L": "R", "F": "B", "B": "F"}
FACE_AXIS = {"U": 1, "D": 1, "R": 0, "L": 0, "F": 2, "B": 2}
SLICE_COMBINATIONS = tuple(combinations(range(12), 4))
SLICE_RANK = {positions: index for index, positions in enumerate(SLICE_COMBINATIONS)}
SLICE_GOAL = SLICE_RANK[(8, 9, 10, 11)]
CORNER_ORIENTATION_COUNT = 3**7
EDGE_ORIENTATION_COUNT = 2**11
SLICE_COMBINATION_COUNT = len(SLICE_COMBINATIONS)
PERMUTATION_COUNT_8 = factorial(8)
PERMUTATION_COUNT_4 = factorial(4)
MAX_PHASE1_DEPTH = 12
MAX_TOTAL_DEPTH = 30


@dataclass
class _Tables:
    corner_orientation_moves: array
    edge_orientation_moves: array
    slice_combination_moves: array
    phase1_corner_pruning: bytearray
    phase1_edge_pruning: bytearray
    corner_permutation_moves: array
    ud_edge_permutation_moves: array
    slice_permutation_moves: array
    phase2_corner_pruning: bytearray
    phase2_edge_pruning: bytearray
    phase2_source_indices: tuple[int, ...]


@dataclass
class _SearchBudget:
    deadline: float
    visited_nodes: int = 0

    def visit(self) -> None:
        self.visited_nodes += 1
        if self.visited_nodes % 1024 == 0 and monotonic() >= self.deadline:
            raise _SearchTimeout


class _SearchTimeout(Exception):
    pass


_tables: _Tables | None = None
_tables_lock = Lock()
_TABLE_CACHE_PATH = Path(__file__).resolve().parent / ".solver-cache" / "phase-tables-v1.bin"
_TABLE_CACHE_MAGIC = b"RUBRIK_GSM_PHASE_TABLES_V1\n"


def _decode_orientation(coordinate: int, count: int, modulus: int) -> tuple[int, ...]:
    values = [0] * count
    for index in range(count - 2, -1, -1):
        values[index] = coordinate % modulus
        coordinate //= modulus
    values[-1] = (-sum(values[:-1])) % modulus
    return tuple(values)


def _encode_orientation(values: tuple[int, ...], modulus: int) -> int:
    coordinate = 0
    for value in values[:-1]:
        coordinate = coordinate * modulus + value
    return coordinate


def _move_sources(token: str, component: str) -> tuple[int, ...]:
    face = token[0]
    suffix = token[1:]
    turns = 1 if suffix == "" else 2 if suffix == "2" else 3
    source = tuple(range(len(MOVE_DATA[face][component])))
    quarter_turn = MOVE_DATA[face][component]
    for _ in range(turns):
        source = tuple(source[quarter_turn[index]] for index in range(len(source)))
    return source


def _all_move_sources(tokens: tuple[str, ...], component: str) -> tuple[tuple[int, ...], ...]:
    return tuple(_move_sources(token, component) for token in tokens)


def _apply_sources(values: tuple[int, ...], source: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(values[source[index]] for index in range(len(source)))


def _build_orientation_moves(corners: bool) -> array:
    count = 8 if corners else 12
    modulus = 3 if corners else 2
    coordinate_count = CORNER_ORIENTATION_COUNT if corners else EDGE_ORIENTATION_COUNT
    result = array("H", [0]) * (coordinate_count * PHASE1_MOVE_COUNT)
    identity_corners = tuple(range(8))
    identity_edges = tuple(range(12))
    zero_corners = (0,) * 8
    zero_edges = (0,) * 12

    for coordinate in range(coordinate_count):
        orientation = _decode_orientation(coordinate, count, modulus)
        state = CubeState(
            identity_corners,
            orientation if corners else zero_corners,
            identity_edges,
            orientation if not corners else zero_edges,
        )
        offset = coordinate * PHASE1_MOVE_COUNT
        for move_index, token in enumerate(PHASE1_TOKENS):
            moved = apply_token(state, token)
            values = moved.co if corners else moved.eo
            result[offset + move_index] = _encode_orientation(values, modulus)

    return result


def _slice_representative(coordinate: int) -> tuple[int, ...]:
    selected = set(SLICE_COMBINATIONS[coordinate])
    edge_permutation = [0] * 12
    slice_piece = 8
    other_piece = 0
    for position in range(12):
        if position in selected:
            edge_permutation[position] = slice_piece
            slice_piece += 1
        else:
            edge_permutation[position] = other_piece
            other_piece += 1
    return tuple(edge_permutation)


def _slice_coordinate(edge_permutation: tuple[int, ...]) -> int:
    positions = tuple(index for index, piece in enumerate(edge_permutation) if piece >= 8)
    return SLICE_RANK[positions]


def _build_slice_combination_moves(edge_sources: tuple[tuple[int, ...], ...]) -> array:
    result = array("H", [0]) * (SLICE_COMBINATION_COUNT * PHASE1_MOVE_COUNT)
    for coordinate in range(SLICE_COMBINATION_COUNT):
        edge_permutation = _slice_representative(coordinate)
        offset = coordinate * PHASE1_MOVE_COUNT
        for move_index, source in enumerate(edge_sources):
            moved = _apply_sources(edge_permutation, source)
            result[offset + move_index] = _slice_coordinate(moved)
    return result


def _build_permutation_moves(
    size: int,
    source_maps: tuple[tuple[int, ...], ...],
    move_count: int,
    typecode: str,
) -> array:
    coordinate_count = factorial(size)
    result = array(typecode, [0]) * (coordinate_count * move_count)
    for coordinate in range(coordinate_count):
        permutation = _permutation_unrank(coordinate, size)
        offset = coordinate * move_count
        for move_index, source in enumerate(source_maps):
            result[offset + move_index] = _permutation_rank(_apply_sources(permutation, source))
    return result


def _permutation_rank(permutation: tuple[int, ...]) -> int:
    rank = 0
    size = len(permutation)
    for index, value in enumerate(permutation):
        smaller = sum(other < value for other in permutation[index + 1 :])
        rank += smaller * factorial(size - index - 1)
    return rank


def _permutation_unrank(rank: int, size: int) -> tuple[int, ...]:
    remaining = list(range(size))
    permutation = []
    for index in range(size):
        factor = factorial(size - index - 1)
        digit, rank = divmod(rank, factor)
        permutation.append(remaining.pop(digit))
    return tuple(permutation)


def _build_pruning_table(
    moves_a: array,
    size_a: int,
    moves_b: array,
    size_b: int,
    move_count: int,
    goal_a: int,
    goal_b: int,
) -> bytearray:
    distances = bytearray([255]) * (size_a * size_b)
    start = goal_a * size_b + goal_b
    distances[start] = 0
    queue = array("I", [start])
    head = 0

    while head < len(queue):
        coordinate = queue[head]
        head += 1
        coordinate_a, coordinate_b = divmod(coordinate, size_b)
        next_depth = distances[coordinate] + 1
        offset_a = coordinate_a * move_count
        offset_b = coordinate_b * move_count

        for move_index in range(move_count):
            next_a = moves_a[offset_a + move_index]
            next_b = moves_b[offset_b + move_index]
            next_coordinate = next_a * size_b + next_b
            if distances[next_coordinate] == 255:
                distances[next_coordinate] = next_depth
                queue.append(next_coordinate)

    return distances


def _build_tables() -> _Tables:
    print("Building native solver pruning tables (first solve only)...", flush=True)
    phase1_corner_sources = _all_move_sources(PHASE1_TOKENS, "cp")
    phase1_edge_sources = _all_move_sources(PHASE1_TOKENS, "ep")
    corner_orientation_moves = _build_orientation_moves(corners=True)
    edge_orientation_moves = _build_orientation_moves(corners=False)
    slice_combination_moves = _build_slice_combination_moves(phase1_edge_sources)

    phase1_corner_pruning = _build_pruning_table(
        corner_orientation_moves,
        CORNER_ORIENTATION_COUNT,
        slice_combination_moves,
        SLICE_COMBINATION_COUNT,
        PHASE1_MOVE_COUNT,
        0,
        SLICE_GOAL,
    )
    phase1_edge_pruning = _build_pruning_table(
        edge_orientation_moves,
        EDGE_ORIENTATION_COUNT,
        slice_combination_moves,
        SLICE_COMBINATION_COUNT,
        PHASE1_MOVE_COUNT,
        0,
        SLICE_GOAL,
    )
    print("Phase 1 pruning tables ready.", flush=True)

    phase2_source_indices = tuple(PHASE1_TOKEN_INDEX[token] for token in PHASE2_TOKENS)
    phase2_corner_sources = tuple(phase1_corner_sources[index] for index in phase2_source_indices)
    phase2_ud_edge_sources = tuple(
        phase1_edge_sources[index][:8] for index in phase2_source_indices
    )
    phase2_slice_sources = tuple(
        tuple(phase1_edge_sources[index][position] - 8 for position in range(8, 12))
        for index in phase2_source_indices
    )

    corner_permutation_moves = _build_permutation_moves(
        8, phase2_corner_sources, PHASE2_MOVE_COUNT, "I"
    )
    ud_edge_permutation_moves = _build_permutation_moves(
        8, phase2_ud_edge_sources, PHASE2_MOVE_COUNT, "I"
    )
    slice_permutation_moves = _build_permutation_moves(
        4, phase2_slice_sources, PHASE2_MOVE_COUNT, "B"
    )
    phase2_corner_pruning = _build_pruning_table(
        corner_permutation_moves,
        PERMUTATION_COUNT_8,
        slice_permutation_moves,
        PERMUTATION_COUNT_4,
        PHASE2_MOVE_COUNT,
        0,
        0,
    )
    phase2_edge_pruning = _build_pruning_table(
        ud_edge_permutation_moves,
        PERMUTATION_COUNT_8,
        slice_permutation_moves,
        PERMUTATION_COUNT_4,
        PHASE2_MOVE_COUNT,
        0,
        0,
    )
    print("Phase 2 pruning tables ready.", flush=True)

    return _Tables(
        corner_orientation_moves,
        edge_orientation_moves,
        slice_combination_moves,
        phase1_corner_pruning,
        phase1_edge_pruning,
        corner_permutation_moves,
        ud_edge_permutation_moves,
        slice_permutation_moves,
        phase2_corner_pruning,
        phase2_edge_pruning,
        phase2_source_indices,
    )


def _get_tables() -> _Tables:
    global _tables
    if _tables is None:
        with _tables_lock:
            if _tables is None:
                _tables = _load_cached_tables()
                if _tables is None:
                    _tables = _build_tables()
                    _save_cached_tables(_tables)
    return _tables


def _load_cached_tables() -> _Tables | None:
    try:
        with _TABLE_CACHE_PATH.open("rb") as cache_file:
            if cache_file.read(len(_TABLE_CACHE_MAGIC)) != _TABLE_CACHE_MAGIC:
                return None
            tables = load(cache_file)
        if not isinstance(tables, _Tables):
            return None
        expected_lengths = (
            CORNER_ORIENTATION_COUNT * PHASE1_MOVE_COUNT,
            EDGE_ORIENTATION_COUNT * PHASE1_MOVE_COUNT,
            SLICE_COMBINATION_COUNT * PHASE1_MOVE_COUNT,
            CORNER_ORIENTATION_COUNT * SLICE_COMBINATION_COUNT,
            EDGE_ORIENTATION_COUNT * SLICE_COMBINATION_COUNT,
            PERMUTATION_COUNT_8 * PHASE2_MOVE_COUNT,
            PERMUTATION_COUNT_8 * PHASE2_MOVE_COUNT,
            PERMUTATION_COUNT_4 * PHASE2_MOVE_COUNT,
            PERMUTATION_COUNT_8 * PERMUTATION_COUNT_4,
            PERMUTATION_COUNT_8 * PERMUTATION_COUNT_4,
            PHASE2_MOVE_COUNT,
        )
        actual_lengths = tuple(len(value) for value in (
            tables.corner_orientation_moves,
            tables.edge_orientation_moves,
            tables.slice_combination_moves,
            tables.phase1_corner_pruning,
            tables.phase1_edge_pruning,
            tables.corner_permutation_moves,
            tables.ud_edge_permutation_moves,
            tables.slice_permutation_moves,
            tables.phase2_corner_pruning,
            tables.phase2_edge_pruning,
            tables.phase2_source_indices,
        ))
        if actual_lengths != expected_lengths:
            return None
        print("Loaded native solver pruning tables from local cache.", flush=True)
        return tables
    except (OSError, EOFError, UnpicklingError, AttributeError, ValueError):
        return None


def _save_cached_tables(tables: _Tables) -> None:
    temporary_path = None
    try:
        _TABLE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="wb",
            dir=_TABLE_CACHE_PATH.parent,
            prefix="phase-tables-",
            delete=False,
        ) as cache_file:
            temporary_path = Path(cache_file.name)
            cache_file.write(_TABLE_CACHE_MAGIC)
            dump(tables, cache_file, protocol=HIGHEST_PROTOCOL)
        replace(temporary_path, _TABLE_CACHE_PATH)
        print("Saved native solver pruning tables to local cache.", flush=True)
    except OSError as error:
        print(f"Could not save solver table cache: {error}", flush=True)
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _skip_face(previous_face: str | None, face: str) -> bool:
    if previous_face is None:
        return False
    if previous_face == face:
        return True
    return (
        OPPOSITE_FACE[previous_face] == face
        and PHASE2_FACE_ORDER[face] < PHASE2_FACE_ORDER[previous_face]
    )


def simplify_sequence(tokens: list[str]) -> list[str]:
    """Combine same-face moves and canonicalize commuting opposite faces."""
    simplified: list[str] = []
    block: list[str] = []
    turn_values = {"": 1, "2": 2, "'": 3}
    turn_tokens = {1: "", 2: "2", 3: "'"}

    def flush_block() -> None:
        amounts: dict[str, int] = {}
        for move in block:
            face = move[0]
            amounts[face] = (amounts.get(face, 0) + turn_values[move[1:]]) % 4
        for face in "URFDLB":
            amount = amounts.get(face, 0)
            if amount:
                simplified.append(face + turn_tokens[amount])
        block.clear()

    for token in tokens:
        face = token[0]
        suffix = token[1:]
        if face not in MOVE_DATA or suffix not in turn_values:
            raise ValueError(f"Invalid move token: {token}")
        if block and FACE_AXIS[block[0][0]] != FACE_AXIS[face]:
            flush_block()
        block.append(token)

    flush_block()

    return simplified


def inverse_sequence(tokens: list[str]) -> list[str]:
    """Return a simplified inverse algorithm for a known legal move history."""
    inverse = []
    for token in reversed(tokens):
        suffix = token[1:]
        inverse.append(token[0] + ("" if suffix == "'" else "'" if suffix == "" else "2"))
    return simplify_sequence(inverse)


def _phase2_coordinates(state: CubeState) -> tuple[int, int, int]:
    return (
        _permutation_rank(state.cp),
        _permutation_rank(state.ep[:8]),
        _permutation_rank(tuple(piece - 8 for piece in state.ep[8:])),
    )


def _search_phase2(
    coordinates: tuple[int, int, int],
    max_depth: int,
    previous_face: str | None,
    tables: _Tables,
    budget: _SearchBudget,
) -> list[str] | None:
    corner_permutation, ud_edge_permutation, slice_permutation = coordinates
    path: list[str] = []

    def search(
        corner_coordinate: int,
        edge_coordinate: int,
        slice_coordinate: int,
        depth_left: int,
        previous: str | None,
    ) -> bool:
        budget.visit()
        corner_bound = tables.phase2_corner_pruning[
            corner_coordinate * PERMUTATION_COUNT_4 + slice_coordinate
        ]
        edge_bound = tables.phase2_edge_pruning[
            edge_coordinate * PERMUTATION_COUNT_4 + slice_coordinate
        ]
        if max(corner_bound, edge_bound) > depth_left:
            return False
        if corner_coordinate == edge_coordinate == slice_coordinate == 0:
            return True
        if depth_left == 0:
            return False

        corner_offset = corner_coordinate * PHASE2_MOVE_COUNT
        edge_offset = edge_coordinate * PHASE2_MOVE_COUNT
        slice_offset = slice_coordinate * PHASE2_MOVE_COUNT
        for move_index, token in enumerate(PHASE2_TOKENS):
            face = token[0]
            if _skip_face(previous, face):
                continue
            if search(
                tables.corner_permutation_moves[corner_offset + move_index],
                tables.ud_edge_permutation_moves[edge_offset + move_index],
                tables.slice_permutation_moves[slice_offset + move_index],
                depth_left - 1,
                face,
            ):
                path.append(token)
                return True
        return False

    corner_bound = tables.phase2_corner_pruning[
        corner_permutation * PERMUTATION_COUNT_4 + slice_permutation
    ]
    edge_bound = tables.phase2_edge_pruning[
        ud_edge_permutation * PERMUTATION_COUNT_4 + slice_permutation
    ]
    lower_bound = max(corner_bound, edge_bound)
    for depth in range(lower_bound, max_depth + 1):
        path.clear()
        if search(
            corner_permutation,
            ud_edge_permutation,
            slice_permutation,
            depth,
            previous_face,
        ):
            return list(reversed(path))
    return None


def _phase1_coordinates(state: CubeState) -> tuple[int, int, int]:
    return (
        _encode_orientation(state.co, 3),
        _encode_orientation(state.eo, 2),
        _slice_coordinate(state.ep),
    )


def _search_phase1(
    initial_state: CubeState,
    initial_coordinates: tuple[int, int, int],
    phase1_limit: int,
    max_total_depth: int,
    tables: _Tables,
    budget: _SearchBudget,
) -> list[str] | None:
    path: list[str] = []

    def search(corner_orientation: int, edge_orientation: int, slice_position: int, previous: str | None):
        budget.visit()
        depth = len(path)
        corner_bound = tables.phase1_corner_pruning[
            corner_orientation * SLICE_COMBINATION_COUNT + slice_position
        ]
        edge_bound = tables.phase1_edge_pruning[
            edge_orientation * SLICE_COMBINATION_COUNT + slice_position
        ]
        if depth + max(corner_bound, edge_bound) > phase1_limit:
            return None

        if corner_orientation == 0 and edge_orientation == 0 and slice_position == SLICE_GOAL:
            state = apply_sequence(initial_state, " ".join(path)) if path else initial_state
            phase2 = _search_phase2(
                _phase2_coordinates(state),
                min(18, max_total_depth - depth),
                previous,
                tables,
                budget,
            )
            if phase2 is not None:
                return path + phase2

        if depth == phase1_limit:
            return None

        corner_offset = corner_orientation * PHASE1_MOVE_COUNT
        edge_offset = edge_orientation * PHASE1_MOVE_COUNT
        slice_offset = slice_position * PHASE1_MOVE_COUNT
        for move_index, token in enumerate(PHASE1_TOKENS):
            face = token[0]
            if _skip_face(previous, face):
                continue
            next_corner = tables.corner_orientation_moves[corner_offset + move_index]
            next_edge = tables.edge_orientation_moves[edge_offset + move_index]
            next_slice = tables.slice_combination_moves[slice_offset + move_index]
            next_corner_bound = tables.phase1_corner_pruning[
                next_corner * SLICE_COMBINATION_COUNT + next_slice
            ]
            next_edge_bound = tables.phase1_edge_pruning[
                next_edge * SLICE_COMBINATION_COUNT + next_slice
            ]
            if depth + 1 + max(next_corner_bound, next_edge_bound) > phase1_limit:
                continue

            path.append(token)
            solution = search(next_corner, next_edge, next_slice, face)
            if solution is not None:
                return solution
            path.pop()

        return None

    return search(*initial_coordinates, None)


def solve(
    state: CubeState,
    max_depth: int = MAX_TOTAL_DEPTH,
    fallback_solution: list[str] | None = None,
    time_limit_seconds: float = 3.0,
) -> list[str]:
    """Return a short two-phase solution in standard face-turn notation."""
    if not verify_state(state):
        raise ValueError("Cannot solve an invalid cube state.")
    if state == CubeState.solved():
        return []
    if time_limit_seconds <= 0:
        raise ValueError("Search time limit must be positive.")

    fallback = simplify_sequence(fallback_solution) if fallback_solution is not None else None
    if fallback is not None and apply_sequence(state, " ".join(fallback)) != CubeState.solved():
        raise ValueError("Fallback sequence does not solve the submitted cube state.")

    tables = _get_tables()
    budget = _SearchBudget(monotonic() + time_limit_seconds)
    initial_coordinates = _phase1_coordinates(state)
    corner_coordinate, edge_coordinate, slice_coordinate = initial_coordinates
    lower_bound = max(
        tables.phase1_corner_pruning[
            corner_coordinate * SLICE_COMBINATION_COUNT + slice_coordinate
        ],
        tables.phase1_edge_pruning[
            edge_coordinate * SLICE_COMBINATION_COUNT + slice_coordinate
        ],
    )

    try:
        for total_depth in range(lower_bound, max_depth + 1):
            phase1_limit = min(MAX_PHASE1_DEPTH, total_depth)
            solution = _search_phase1(
                state,
                initial_coordinates,
                phase1_limit,
                max_depth,
                tables,
                budget,
            )
            if solution is not None:
                if apply_sequence(state, " ".join(solution)) != CubeState.solved():
                    raise RuntimeError("Native solver returned an invalid solution.")
                if fallback is None or len(solution) < len(fallback):
                    return solution
    except _SearchTimeout:
        if fallback is not None:
            return fallback
        raise TimeoutError(f"Native search exceeded {time_limit_seconds:g} seconds.")

    if fallback is not None and len(fallback) <= max_depth:
        return fallback
    raise ValueError(f"No solution found within {max_depth} face turns.")