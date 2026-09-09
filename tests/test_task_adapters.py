from mga.models import ChangeType
from mga.parsing.hybrid import HybridEntityClaimParser
from mga.parsing.ontology import core_entity_ontology
from mga.task_adapters import (
    canonical_claim_signature,
    is_claim_preserving_rewrite,
    qa_answer_to_claims,
)


def test_transition_qa_adapter_uses_caption_claim_contract() -> None:
    parser = HybridEntityClaimParser(ontology=core_entity_ontology())
    claims = qa_answer_to_claims(
        question="What changed?",
        answer="A road was converted to buildings in the lower-right.",
        parser=parser,
    )
    assert [(claim.entity, claim.change_type) for claim in claims] == [
        ("road", ChangeType.REMOVE),
        ("building", ChangeType.ADD),
    ]
    assert all(claim.metadata["input_adapter"] == "qa_v1" for claim in claims)


def test_rewrite_gate_accepts_style_and_rejects_fact_drift() -> None:
    parser = HybridEntityClaimParser(ontology=core_entity_ontology())
    original = parser.parse("A house appeared in the lower-right.")
    accepted, rewritten = is_claim_preserving_rewrite(
        original_claims=original,
        rewritten_text="A residential building emerged in the lower-right.",
        parser=parser,
    )
    rejected, _ = is_claim_preserving_rewrite(
        original_claims=original,
        rewritten_text="A road appeared in the lower-right.",
        parser=parser,
    )
    assert accepted
    assert not rejected
    assert canonical_claim_signature(original) == canonical_claim_signature(rewritten)
