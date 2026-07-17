from mga.models import ChangeType, ClaimRole
from mga.parsing.heuristic import HeuristicClaimParser


def test_no_change_caption() -> None:
    claims = HeuristicClaimParser().parse("the two scenes seem identical .")
    assert len(claims) == 1
    assert claims[0].role == ClaimRole.NO_CHANGE


def test_addition_caption() -> None:
    claims = HeuristicClaimParser().parse("a house appears in the lower-right corner .")
    assert len(claims) == 1
    assert claims[0].entity == "house"
    assert claims[0].change_type == ChangeType.ADD
    assert claims[0].location == "lower-right"
