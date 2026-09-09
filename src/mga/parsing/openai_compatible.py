"""Optional OpenAI-compatible structured claim parser with deterministic settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from mga.models import AtomicClaim

SYSTEM_PROMPT = """You extract verifiable atomic claims from remote-sensing change captions.
Return JSON only with a top-level `claims` array. Each claim must contain:
claim_id, text, entity, role, change_type, location, count, attributes, target_labels.
role is one of changed, context, no_change. change_type is one of add, remove,
modify, unknown, none. Split multiple changed entities into separate claims. Do not
invent entities. Context entities are static references, not changed objects.
"""


@dataclass
class OpenAICompatibleClaimParser:
    model: str
    api_key: str | None = None
    base_url: str | None = None

    def __post_init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Install the optional parser dependency: pip install -e '.[llm]'"
            ) from exc
        self._client = OpenAI(
            api_key=self.api_key or os.getenv("OPENAI_API_KEY"),
            base_url=self.base_url or os.getenv("OPENAI_BASE_URL") or None,
        )

    def parse(self, caption: str) -> tuple[AtomicClaim, ...]:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": caption},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Claim parser returned an empty response")
        payload = json.loads(content)
        claims = tuple(AtomicClaim.from_dict(item) for item in payload.get("claims", ()))
        if not claims:
            raise ValueError(f"Claim parser returned no claims for caption: {caption!r}")
        return claims
