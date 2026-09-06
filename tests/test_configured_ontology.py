from mga.parsing.configured import configured_entity_ontology


def test_configured_ontology_merges_surface_forms() -> None:
    ontology = configured_entity_ontology(
        class_names={1: "tree", 2: "building"},
        surface_forms={
            "tree": ("wooded parcels",),
            "building": ("urban fabric",),
        },
    )

    assert ontology.canonicalize("wooded parcels") == "tree"
    assert ontology.canonicalize("urban fabric") == "building"
    assert ontology.labels_for("tree") == (1,)
    assert ontology.labels_for("building") == (2,)
