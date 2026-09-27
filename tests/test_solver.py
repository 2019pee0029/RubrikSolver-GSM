from array import array

import pytest

from main import CubeState, apply_sequence
import solver
from solver import inverse_sequence, solve


@pytest.mark.parametrize(
    "scramble",
    [
        "R",
        "R U F'",
        "R U R' U' F2 D L B2",
    ],
)
def test_native_solver_returns_a_valid_solution(scramble):
    state = apply_sequence(CubeState.solved(), scramble)

    solution = solve(state)

    assert apply_sequence(state, " ".join(solution)) == CubeState.solved()
    assert len(solution) <= 22


def test_native_solver_returns_no_moves_for_solved_cube():
    assert solve(CubeState.solved()) == []


def test_native_solver_rejects_invalid_state():
    invalid = CubeState((0,) * 8, (0,) * 8, tuple(range(12)), (0,) * 12)

    with pytest.raises(ValueError, match="invalid cube state"):
        solve(invalid)


def test_native_solver_uses_inverse_fallback_when_budget_expires(monkeypatch):
    import solver

    scramble = "R' B' R' U D' B' U R' D L D' L' D' B' D' F B R U B' F' B' F' D L D L' B' F' L'"
    tokens = scramble.split()
    state = apply_sequence(CubeState.solved(), scramble)
    fallback = inverse_sequence(tokens)

    def expire_budget(_budget):
        raise solver._SearchTimeout

    monkeypatch.setattr(solver._SearchBudget, "visit", expire_budget)

    solution = solve(state, fallback_solution=fallback)

    assert solution == fallback
    assert apply_sequence(state, " ".join(solution)) == CubeState.solved()


def test_inverse_sequence_simplifies_opposite_face_moves():
    assert inverse_sequence(["U", "D", "U'"]) == ["D'"]


def test_solver_table_cache_round_trip(tmp_path, monkeypatch):
    tables = solver._Tables(
        array("H", [0]) * (solver.CORNER_ORIENTATION_COUNT * solver.PHASE1_MOVE_COUNT),
        array("H", [0]) * (solver.EDGE_ORIENTATION_COUNT * solver.PHASE1_MOVE_COUNT),
        array("H", [0]) * (solver.SLICE_COMBINATION_COUNT * solver.PHASE1_MOVE_COUNT),
        bytearray(solver.CORNER_ORIENTATION_COUNT * solver.SLICE_COMBINATION_COUNT),
        bytearray(solver.EDGE_ORIENTATION_COUNT * solver.SLICE_COMBINATION_COUNT),
        array("I", [0]) * (solver.PERMUTATION_COUNT_8 * solver.PHASE2_MOVE_COUNT),
        array("I", [0]) * (solver.PERMUTATION_COUNT_8 * solver.PHASE2_MOVE_COUNT),
        array("B", [0]) * (solver.PERMUTATION_COUNT_4 * solver.PHASE2_MOVE_COUNT),
        bytearray(solver.PERMUTATION_COUNT_8 * solver.PERMUTATION_COUNT_4),
        bytearray(solver.PERMUTATION_COUNT_8 * solver.PERMUTATION_COUNT_4),
        tuple(range(solver.PHASE2_MOVE_COUNT)),
    )
    monkeypatch.setattr(solver, "_TABLE_CACHE_PATH", tmp_path / "phase-tables.bin")

    solver._save_cached_tables(tables)

    assert solver._load_cached_tables() == tables