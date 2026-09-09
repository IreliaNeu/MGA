from __future__ import annotations

import pytest

from mga.grounding.query_expansion import expand_grounding_queries, format_grounding_query


@pytest.mark.parametrize("entity", ("house", "houses", "building", "buildings"))
def test_building_aliases_expand_to_building_group(entity: str) -> None:
    queries = expand_grounding_queries(entity, "remote-sensing")

    assert queries[0] in {"house", "houses", "building", "buildings"}
    assert "building" in queries
    assert "residential building" in queries
    assert "villa" in queries
    assert "structure" not in queries
    assert len(queries) == len(set(queries))


def test_none_profile_preserves_normalized_entity() -> None:
    assert expand_grounding_queries("  Houses. ", "none") == ("houses",)


def test_unknown_remote_sensing_entity_is_preserved() -> None:
    assert expand_grounding_queries("airport", "remote-sensing") == ("airport",)


def test_villa_alias_expands_to_building_group() -> None:
    assert expand_grounding_queries("villas", "remote-sensing") == (
        "villas",
        "building",
        "house",
        "residential building",
        "villa",
    )


def test_road_expansion_uses_narrow_remote_sensing_prompts() -> None:
    assert expand_grounding_queries("road", "remote-sensing") == ("road", "paved road")


def test_grounding_query_uses_period_separated_categories() -> None:
    assert format_grounding_query(("house", "building")) == "house. building."


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown query expansion profile"):
        expand_grounding_queries("house", "unknown")
