from main import CubeState, apply_sequence, verify_state


def test_solved_state_is_valid_and_solved():
    solved = CubeState.solved()
    assert solved == CubeState.solved()
    assert verify_state(solved)


def test_face_turns_are_invertible():
    solved = CubeState.solved()
    for face in ("U", "D", "L", "R", "F", "B"):
        state = apply_sequence(solved, f"{face} {face} {face} {face}")
        assert state == solved


def test_scramble_stays_valid():
    scrambled = apply_sequence(CubeState.solved(), "R U R' U' F2 D L B2")
    assert verify_state(scrambled)
