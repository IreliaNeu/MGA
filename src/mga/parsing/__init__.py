"""Caption-to-claim parser backends."""

from mga.parsing.base import ClaimParser
from mga.parsing.heuristic import HeuristicClaimParser
from mga.parsing.openai_compatible import OpenAICompatibleClaimParser

__all__ = ["ClaimParser", "HeuristicClaimParser", "OpenAICompatibleClaimParser"]
