from mga.models import ChangeType, ClaimRole
from mga.parsing.heuristic import HeuristicClaimParser


def test_no_change_caption() -> None:
    claims = HeuristicClaimParser().parse("the two scenes seem identical .")
    assert len(claims) == 1
    assert claims[0].role == ClaimRole.NO_CHANGE


def test_same_as_before_is_no_change() -> None:
    claims = HeuristicClaimParser().parse("the scene is the same as before .")

    assert len(claims) == 1
    assert claims[0].role == ClaimRole.NO_CHANGE


def test_addition_caption() -> None:
    claims = HeuristicClaimParser().parse("a house appears in the lower-right corner .")
    assert len(claims) == 1
    assert claims[0].entity == "building"
    assert claims[0].change_type == ChangeType.ADD
    assert claims[0].location == "lower-right"
    assert claims[0].target_labels == (2,)


def test_villa_is_building_and_nearby_road_is_context() -> None:
    claims = HeuristicClaimParser().parse("a villa is built near the road .")

    assert [(claim.entity, claim.role, claim.change_type) for claim in claims] == [
        ("building", ClaimRole.CHANGED, ChangeType.ADD),
        ("road", ClaimRole.CONTEXT, ChangeType.NONE),
    ]


def test_location_reference_road_is_not_marked_as_added() -> None:
    claims = HeuristicClaimParser().parse(
        "a house appears on the right side of the road ."
    )

    assert claims[0].entity == "building"
    assert claims[0].role == ClaimRole.CHANGED
    assert claims[1].entity == "road"
    assert claims[1].role == ClaimRole.CONTEXT
    assert claims[1].change_type == ChangeType.NONE


def test_road_on_both_sides_expression_is_context() -> None:
    claims = HeuristicClaimParser().parse(
        "some houses are built on both sides of the road ."
    )

    assert [(claim.entity, claim.role, claim.change_type) for claim in claims] == [
        ("building", ClaimRole.CHANGED, ChangeType.ADD),
        ("road", ClaimRole.CONTEXT, ChangeType.NONE),
    ]


def test_explicitly_built_road_is_kept_separate_from_context_mention() -> None:
    claims = HeuristicClaimParser().parse(
        "a road is built and houses appear on both sides of the road ."
    )

    assert [(claim.entity, claim.role, claim.change_type) for claim in claims] == [
        ("road", ClaimRole.CHANGED, ChangeType.ADD),
        ("building", ClaimRole.CHANGED, ChangeType.ADD),
        ("road", ClaimRole.CONTEXT, ChangeType.NONE),
    ]


def test_clause_level_change_type_does_not_propagate_removal() -> None:
    claims = HeuristicClaimParser().parse(
        "the vegetation is removed and many houses are built along the road"
    )

    assert [(claim.entity, claim.role, claim.change_type) for claim in claims] == [
        ("building", ClaimRole.CHANGED, ChangeType.ADD),
        ("road", ClaimRole.CONTEXT, ChangeType.NONE),
    ]


def test_unlabelled_entities_are_not_extracted() -> None:
    assert HeuristicClaimParser().parse("trees are removed and a lake appears") == ()


def test_textual_structure_alias_does_not_change_grounding_query() -> None:
    claims = HeuristicClaimParser().parse("a new structure appears .")

    assert len(claims) == 1
    assert claims[0].entity == "building"
    assert claims[0].target_labels == (2,)
