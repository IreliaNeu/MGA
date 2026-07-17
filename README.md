# MGA v2

Mask-Guided Alignment (MGA) is a research toolkit for evaluating whether open-ended
remote-sensing change captions are supported by bi-temporal imagery and change masks.

This repository contains:

- a documented reconstruction of the original MGA v1 score;
- MGA v2 with separate faithfulness, coverage, temporal, context, and unverifiable outputs;
- adapters for Draft/Guided feedback JSONL and per-sample Change-Agent text files;
- pluggable and cached grounding backends;
- controlled perturbations for metric monotonicity experiments;
- local CPU tests and an optional AutoDL GPU workflow.

> Status: research scaffold. The Hugging Face Grounding DINO backend currently
> rasterizes detection boxes. A SAM refinement backend and human meta-evaluation
> analysis will be added after the first server-side validation.

## Why MGA v2?

The original formulation used the ground-truth change mask both to filter grounded
components and to score them. That can remove false-positive regions before scoring.
It also mixed spatial faithfulness and semantic coverage into a single value, treated
mask/grounder failures as caption errors, and used a single temporal image for
add/remove verification.

MGA v2 changes the evaluation contract:

| Output | Interpretation |
| --- | --- |
| `faithfulness` | Are changed-entity claims spatially and temporally supported? |
| `coverage` | How many annotated change components are covered by grounded claims? |
| `temporal` | Does pre/post evidence support add, remove, or modify direction? |
| `context_support` | Can static reference entities be grounded? |
| `unverifiable_rate` | How many claims lack sufficient evidence? |
| `overall` | Optional weighted summary; never a replacement for the score vector. |

Every claim is classified as `supported`, `contradicted`, or `unverifiable`.

## Installation

Local CPU development:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

AutoDL/GPU:

```bash
git clone https://github.com/IreliaNeu/MGA.git
cd MGA
bash scripts/setup_autodl.sh
source .venv/bin/activate
```

See [docs/autodl.md](docs/autodl.md) for the VS Code Remote workflow and persistent
artifact recommendations.

## 1. Convert existing Draft/Guided results

The source format may contain the fields shown in `examples/feedback_sample.jsonl`:

```bash
mga prepare-feedback \
  --input /path/to/feedback_results.jsonl \
  --output data/feedback_manifest.jsonl \
  --mask-root /path/to/LEVIR-MCI/masks/test \
  --mask-template "{image_stem}.png"
```

Each source row becomes two canonical records, one for `Draft` and one for `Guided`.
Ground-truth captions, teacher feedback, and LLM-as-Judge winner labels/reasons are
preserved in `metadata`. Human ratings are imported separately and never conflated.

If masks use another name, the template can use `{id}`, `{sample_id}`, or
`{image_stem}`.

## 2. Attach Change-Agent text files

When each sample has one text file such as `test_000001.txt`:

```bash
mga attach-change-agent \
  --manifest data/feedback_manifest.jsonl \
  --results-dir /path/to/change_agent_results \
  --output data/all_models_manifest.jsonl
```

Matching tries the canonical sample ID and the source image stem. The default is
strict: missing captions stop the conversion instead of silently changing the test set.
Use `--allow-missing` only for an explicitly documented subset.

## 3. Validate paths and parse atomic claims

```bash
mga validate --manifest data/all_models_manifest.jsonl

# Deterministic smoke-test parser
mga parse \
  --manifest data/all_models_manifest.jsonl \
  --output data/claims_heuristic.jsonl \
  --parser heuristic

# Recommended experiment parser: any OpenAI-compatible endpoint
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=...
mga parse \
  --manifest data/all_models_manifest.jsonl \
  --output data/claims_llm.jsonl \
  --parser openai \
  --model YOUR_MODEL_ID
```

The heuristic parser is for tests and ablations, not the final paper results.
LLM-derived claims are persisted so scoring never needs to repeat API calls.

## 4. Score with cached Grounding DINO evidence

```bash
mga score \
  --manifest data/claims_llm.jsonl \
  --output outputs/mga_v2.jsonl \
  --method v2 \
  --grounder hf-dino \
  --device cuda \
  --cache-dir cache/grounding_dino
```

Run the legacy reconstruction on the exact same claims and evidence:

```bash
mga score \
  --manifest data/claims_llm.jsonl \
  --output outputs/mga_v1.jsonl \
  --method v1 \
  --grounder hf-dino \
  --device cuda \
  --cache-dir cache/grounding_dino
```

Grounding cache keys include backend settings, image paths, sample ID, and the full
claim. Restarting an expired instance only recomputes missing keys if the cache has
been synchronized to persistent storage.

## 5. Create controlled corruptions

```bash
mga perturb \
  --manifest data/all_models_manifest.jsonl \
  --output data/controlled_perturbations.jsonl
```

The initial suite includes entity injection, temporal-direction swaps, and location
swaps. These samples support tests such as "hallucination injection should reduce
faithfulness" without rerunning captioning models.

## Canonical manifest

One row represents one model caption for one image pair:

```json
{
  "sample_id": "levir-cc_test_000001",
  "model": "Guided",
  "caption": "a house appears in the lower-right corner .",
  "pre_image": ".../A/test_000001.png",
  "post_image": ".../B/test_000001.png",
  "change_mask": ".../masks/test_000001.png",
  "dataset": "LEVIR-MCI",
  "split": "test",
  "feedback": "Correction: ...",
  "claims": [],
  "metadata": {
    "ground_truth_caption": "there is no difference .",
    "llm_judge_winner": "Draft"
  }
}
```

Detailed contracts are documented in [docs/data-format.md](docs/data-format.md).

## Reproducibility rules

- Never commit private datasets, API keys, or model checkpoints.
- Commit manifests with portable relative paths only when licensing permits.
- Persist parsed claims, grounding cache, raw per-claim scores, and environment logs.
- Pin the final parser model, grounding model revision, thresholds, and prompt.
- Keep Draft, Guided, and Change-Agent on the identical test sample set.
- Report MGA dimensions separately before reporting `overall`.

## Roadmap

- [ ] Grounded-SAM mask refinement backend.
- [ ] Spatial relation verifier for left/right/near/along.
- [ ] Count and attribute verification with explicit abstention.
- [ ] Five-rater human-label importer and correlation statistics.
- [ ] SECOND-CC semantic-map adapter.
- [ ] Model- and dataset-level bootstrap confidence intervals.

