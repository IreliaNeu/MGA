from __future__ import annotations

from dataclasses import dataclass

from mga.models import ChangeType
from mga.parsing.hybrid import EntityMention, HybridEntityClaimParser
from mga.parsing.ontology import second_entity_ontology

SECOND_LABELS = {
    "non-vegetated ground": (1,),
    "tree": (2,),
    "low vegetation": (3,),
    "water": (4,),
    "building": (5,),
    "playground": (6,),
}


@dataclass
class FakeExtractor:
    def extract(
        self, text: str, candidate_entities: tuple[str, ...]
    ) -> tuple[EntityMention, ...]:
        start = text.index("aquatic corridor")
        return (
            EntityMention(
                text="aquatic corridor",
                entity="water",
                start=start,
                end=start + len("aquatic corridor"),
                score=0.82,
                source="gliner",
            ),
        )


def test_second_ontology_extracts_multiple_semantic_classes() -> None:
    parser = HybridEntityClaimParser(
        ontology=second_entity_ontology(SECOND_LABELS)
    )

    claims = parser.parse("Trees were replaced by buildings in the upper-left.")

    assert [(item.entity, item.change_type) for item in claims] == [
        ("tree", ChangeType.REMOVE),
        ("building", ChangeType.ADD),
    ]
    assert claims[0].target_labels == (2,)
    assert claims[1].target_labels == (5,)


def test_lightweight_extractor_recovers_unlisted_surface_form() -> None:
    parser = HybridEntityClaimParser(
        ontology=second_entity_ontology(SECOND_LABELS),
        extractor=FakeExtractor(),
    )

    claims = parser.parse("A new aquatic corridor appeared in the center.")

    assert len(claims) == 1
    assert claims[0].entity == "water"
    assert claims[0].change_type == ChangeType.ADD
    assert claims[0].metadata["parser_source"] == "gliner"
