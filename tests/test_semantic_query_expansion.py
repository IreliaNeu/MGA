from mga.grounding.semantic_query_expansion import expand_semantic_change_queries


def test_second_queries_are_conservative_and_class_specific() -> None:
    tree = expand_semantic_change_queries("tree")
    low_vegetation = expand_semantic_change_queries("low vegetation")
    assert tree == ("tree", "tree cover")
    assert low_vegetation == ("low vegetation", "grassland")
    assert set(tree).isdisjoint(low_vegetation)


def test_non_vegetated_ground_includes_remote_sensing_surfaces() -> None:
    queries = expand_semantic_change_queries("non-vegetated ground")
    assert "bare ground" in queries
    assert "impervious surface" in queries
