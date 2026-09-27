
"""
gsm_rubiks.py
Group-State Matrix (GSM) engine for a standard 3x3x3 Rubik's Cube.

Convention:
- Corner positions: URF UFL ULB UBR DFR DLF DBL DRB
- Edge positions:   UR  UF  UL  UB  DR  DF  DL  DB  FR  FL  BL  BR
- cp[i] / ep[i] gives the cubie occupying position i.
- co[i] in Z3; eo[i] in Z2.
- A move operator is an affine permutation:
      p' = P p
      o' = P o + delta  (mod 3 for corners, mod 2 for edges)
  where P is a permutation matrix.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

CORNERS = ("URF","UFL","ULB","UBR","DFR","DLF","DBL","DRB")
EDGES   = ("UR","UF","UL","UB","DR","DF","DL","DB","FR","FL","BL","BR")

# Kociemba cubie-level basic moves, encoded as "new position <- old piece".
MOVE_DATA = {
    "U": {
        "cp": (3,0,1,2,4,5,6,7),
        "co": (0,0,0,0,0,0,0,0),
        "ep": (3,0,1,2,4,5,6,7,8,9,10,11),
        "eo": (0,0,0,0,0,0,0,0,0,0,0,0),
    },
    "R": {
        "cp": (4,1,2,0,7,5,6,3),
        "co": (2,0,0,1,1,0,0,2),
        "ep": (8,1,2,3,11,5,6,7,4,9,10,0),
        "eo": (0,0,0,0,0,0,0,0,0,0,0,0),
    },
    "F": {
        "cp": (1,5,2,3,0,4,6,7),
        "co": (1,2,0,0,2,1,0,0),
        "ep": (0,9,2,3,4,8,6,7,1,5,10,11),
        "eo": (0,1,0,0,0,1,0,0,1,1,0,0),
    },
    "D": {
        "cp": (0,1,2,3,5,6,7,4),
        "co": (0,0,0,0,0,0,0,0),
        "ep": (0,1,2,3,5,6,7,4,8,9,10,11),
        "eo": (0,0,0,0,0,0,0,0,0,0,0,0),
    },
    "L": {
        "cp": (0,2,6,3,4,1,5,7),
        "co": (0,1,2,0,0,2,1,0),
        "ep": (0,1,10,3,4,5,9,7,8,2,6,11),
        "eo": (0,0,0,0,0,0,0,0,0,0,0,0),
    },
    "B": {
        "cp": (0,1,3,7,4,5,2,6),
        "co": (0,0,1,2,0,0,2,1),
        "ep": (0,1,2,11,4,5,6,10,8,9,3,7),
        "eo": (0,0,0,1,0,0,0,1,0,0,1,1),
    },
}

@dataclass(frozen=True)
class CubeState:
    cp: Tuple[int, ...]
    co: Tuple[int, ...]
    ep: Tuple[int, ...]
    eo: Tuple[int, ...]

    @staticmethod
    def solved() -> "CubeState":
        return CubeState(
            tuple(range(8)), (0,)*8,
            tuple(range(12)), (0,)*12
        )

def apply_quarter_turn(state: CubeState, face: str) -> CubeState:
    """Apply one clockwise quarter turn using the convention above."""
    if face not in MOVE_DATA:
        raise ValueError(f"Unknown face: {face}")
    m = MOVE_DATA[face]

    cp = tuple(state.cp[m["cp"][i]] for i in range(8))
    co = tuple((state.co[m["cp"][i]] + m["co"][i]) % 3 for i in range(8))
    ep = tuple(state.ep[m["ep"][i]] for i in range(12))
    eo = tuple((state.eo[m["ep"][i]] + m["eo"][i]) % 2 for i in range(12))

    return CubeState(cp, co, ep, eo)

def apply_token(state: CubeState, token: str) -> CubeState:
    """Apply U, U2, U' etc."""
    token = token.strip()
    if not token:
        return state
    face = token[0]
    if face not in MOVE_DATA:
        raise ValueError(f"Invalid move token: {token}")
    suffix = token[1:]
    turns = 1 if suffix == "" else 2 if suffix == "2" else 3 if suffix == "'" else None
    if turns is None:
        raise ValueError(f"Invalid move suffix: {token}")
    for _ in range(turns):
        state = apply_quarter_turn(state, face)
    return state

def apply_sequence(state: CubeState, sequence: str) -> CubeState:
    for token in sequence.split():
        state = apply_token(state, token)
    return state

def is_solved(state: CubeState) -> bool:
    return state == CubeState.solved()

def permutation_parity(p: Tuple[int, ...]) -> int:
    inv = 0
    for i in range(len(p)):
        for j in range(i+1, len(p)):
            inv += int(p[i] > p[j])
    return inv & 1

def verify_state(state: CubeState) -> bool:
    """Physical cubie-level validity checks."""
    if sorted(state.cp) != list(range(8)):
        return False
    if sorted(state.ep) != list(range(12)):
        return False
    if any(x not in (0,1,2) for x in state.co):
        return False
    if any(x not in (0,1) for x in state.eo):
        return False
    if sum(state.co) % 3 != 0:
        return False
    if sum(state.eo) % 2 != 0:
        return False
    if permutation_parity(state.cp) != permutation_parity(state.ep):
        return False
    return True

def permutation_matrix(perm: Tuple[int, ...]):
    """
    Return P with P[i, perm[i]] = 1.
    This acts on a column state vector as:
        new[i] = old[perm[i]]
    """
    n = len(perm)
    P = [[0]*n for _ in range(n)]
    for i, src in enumerate(perm):
        P[i][src] = 1
    return P

def block_diag(A, B):
    n, m = len(A), len(A[0])
    p, q = len(B), len(B[0])
    out = [[0]*(m+q) for _ in range(n+p)]
    for i in range(n):
        for j in range(m):
            out[i][j] = A[i][j]
    for i in range(p):
        for j in range(q):
            out[n+i][m+j] = B[i][j]
    return out

def piece_permutation_matrix(face: str):
    """20x20 P for [8 corners | 12 edges]."""
    m = MOVE_DATA[face]
    return block_diag(
        permutation_matrix(m["cp"]),
        permutation_matrix(m["ep"])
    )

def affine_move_data(face: str):
    """
    Return (P20, dc, de), where:
      P20 acts on [corner_perm(8), edge_perm(12)].
      dc is the corner-orientation offset.
      de is the edge-orientation offset.
    """
    if face not in MOVE_DATA:
        raise ValueError(face)
    m = MOVE_DATA[face]
    return piece_permutation_matrix(face), m["co"], m["eo"]

def named_state(state: CubeState):
    """Human-readable cubie state."""
    return {
        "corners": [(CORNERS[i], CORNERS[state.cp[i]], state.co[i]) for i in range(8)],
        "edges":   [(EDGES[i],   EDGES[state.ep[i]],   state.eo[i]) for i in range(12)],
    }

def run_self_tests() -> None:
    solved = CubeState.solved()

    # Every quarter turn is a legal state and has order 4.
    for face in MOVE_DATA:
        s = solved
        for _ in range(4):
            s = apply_quarter_turn(s, face)
        assert s == solved, f"{face}^4 != identity"

        s1 = apply_quarter_turn(solved, face)
        assert verify_state(s1), f"{face} produced invalid state"

    # Inverse pairs.
    for face in MOVE_DATA:
        assert apply_sequence(
            solved, f"{face} {face} {face} {face}"
        ) == solved

    # Known relation: opposite faces commute.
    for a, b in (("U","D"), ("R","L"), ("F","B")):
        ab = apply_sequence(solved, f"{a} {b}")
        ba = apply_sequence(solved, f"{b} {a}")
        assert ab == ba, f"{a}{b} != {b}{a}"

    # Mixed scramble followed by its exact inverse.
    scramble = "R U R' U' F2 D L B2"
    inverse = "B2 L' D' F2 U R U' R'"
    s = apply_sequence(solved, scramble)
    assert verify_state(s), "scramble state invalid"
    assert apply_sequence(s, inverse) == solved, "scramble inverse failed"

    # Matrix sanity: each permutation matrix has one 1 in every row and column.
    for face in MOVE_DATA:
        P = piece_permutation_matrix(face)
        assert len(P) == 20 and all(len(row) == 20 for row in P)
        assert all(sum(row) == 1 for row in P)
        assert all(sum(P[i][j] for i in range(20)) == 1 for j in range(20))

if __name__ == "__main__":
    run_self_tests()
    print("All GSM Rubik tests passed.")