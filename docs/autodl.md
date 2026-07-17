# AutoDL and VS Code Remote workflow

## Recommended directory layout

Keep code and large artifacts separate:

```text
MGA/                         # Git repository
datasets/                    # images and masks, not committed
mga-artifacts/
  claims/                    # persisted parser outputs
  grounding-cache/           # expensive per-claim evidence
  scores/                    # raw v1/v2 JSONL
  logs/                      # environment and run logs
```

Store `mga-artifacts` on persistent storage or synchronize it after every run. An
expired compute instance should never be the only copy of claims, evidence, or scores.

## First connection

1. Create the AutoDL instance and confirm CUDA/PyTorch compatibility.
2. Configure VS Code Remote SSH.
3. In the remote terminal:

```bash
git clone https://github.com/IreliaNeu/MGA.git
cd MGA
bash scripts/setup_autodl.sh
source .venv/bin/activate
pytest
nvidia-smi
```

4. Place or mount LEVIR-MCI outside the repository.
5. Convert paths with `mga prepare-feedback`, validate them, and parse claims.
6. Run a 10-sample smoke test before the full test set.

## Server-side development

Create a feature branch rather than editing the default branch:

```bash
git switch -c experiment/grounded-sam
# edit and test
git add <explicit files>
git commit -m "add grounded sam backend"
git push -u origin experiment/grounded-sam
```

Pull local changes before starting a server run and push code changes before stopping
the instance. Do not commit datasets, model weights, caches, or API keys.

## Smoke-test sequence

```bash
mga validate --manifest data/all_models_manifest.jsonl
mga parse --manifest data/all_models_manifest.jsonl \
  --output data/claims_smoke.jsonl --parser heuristic
mga score --manifest data/claims_smoke.jsonl \
  --output outputs/smoke_v2.jsonl --grounder hf-dino \
  --cache-dir /path/to/persistent/mga-artifacts/grounding-cache
```

The heuristic parser only verifies the pipeline. Use the persisted LLM/parser claims
for the final experiment.

## Run provenance

Record the following beside every full run:

```bash
git rev-parse HEAD
python --version
python -m pip freeze
nvidia-smi
```

Also record the parser model, prompt revision, Grounding DINO model revision,
thresholds, dataset checksum, and sample count.

