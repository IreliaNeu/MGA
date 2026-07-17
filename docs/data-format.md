# Data format

## Canonical sample record

Required fields:

- `sample_id`: stable source ID shared by all compared models;
- `model`: caption-producing system;
- `caption`: raw model output;
- `pre_image`, `post_image`, `change_mask`: absolute paths or paths relative to the
  manifest;
- `claims`: optional during preparation, required during scoring.

Recommended metadata:

- ground-truth caption;
- teacher feedback and feedback type;
- LLM-as-Judge winner, reason, and exact judge model/version;
- separately imported per-rater human labels and their aggregation rule;
- source filename/stem;
- mask class labels when the mask is multi-class.

For multi-class masks, add for example:

```json
{"metadata": {"mask_labels": [1]}}
```

Without `mask_labels`, every nonzero mask value is treated as change.

## Atomic claim

```json
{
  "claim_id": "c001",
  "text": "a house appears in the lower-right corner",
  "entity": "house",
  "role": "changed",
  "change_type": "add",
  "location": "lower-right",
  "count": null,
  "attributes": [],
  "target_labels": [],
  "metadata": {}
}
```

Allowed roles: `changed`, `context`, `no_change`.

Allowed change types: `add`, `remove`, `modify`, `unknown`, `none`.

## Metadata-mask grounder

For CPU tests or oracle experiments, a claim may reference precomputed entity masks:

```json
{
  "metadata": {
    "pre_support_mask": "support/pre/c001.png",
    "post_support_mask": "support/post/c001.png",
    "pre_confidence": 0.1,
    "post_confidence": 0.93
  }
}
```

This provides a deterministic way to isolate scoring behavior from model grounding.

