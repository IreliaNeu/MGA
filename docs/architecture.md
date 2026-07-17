# Architecture

```text
existing outputs
  |-- feedback JSONL -> prepare-feedback --|
  |-- Change-Agent .txt -> attach ---------|--> canonical manifest
                                                   |
                                                   v
                                            atomic claim parser
                                                   |
                                                   v
pre/post images -> cached Grounder -> per-claim pre/post support masks
                                                   |
change mask ---------------------------------------|
                                                   v
                                    MGA v1 or MGA v2 scorer
                                                   |
                                                   v
                              raw claim scores + caption score vector
```

## Module boundaries

- `mga.models`: stable dataclasses and enums.
- `mga.prepare`: adapters for existing experiment artifacts.
- `mga.parsing`: deterministic and OpenAI-compatible claim parsers.
- `mga.grounding`: backend protocol, persistent cache, and GPU implementations.
- `mga.mask_ops`: dependency-light mask primitives and connected components.
- `mga.scoring`: documented v1 reconstruction and v2 multidimensional scorer.
- `mga.pipeline`: orchestration without CLI-specific state.
- `mga.perturbations`: controlled metric sensitivity examples.
- `mga.cli`: local and server entry point.

## Design decisions

### Ground truth is not used to filter predictions in v2

All grounded regions remain in the denominator of spatial support precision. This
prevents false-positive components from disappearing before evaluation. The legacy
filter is isolated in `LegacyMGAScorer` for ablation only.

### Missing evidence is not automatically false

Low confidence or missing target-time grounding is `unverifiable`. This separates
caption errors from grounding failure and incomplete annotations.

### Coverage and faithfulness are different axes

A conservative caption can be faithful but incomplete. Faithfulness averages
verifiable changed claims; coverage measures connected change components reached by
the union of changed-claim supports.

### Time direction uses both images

For additions, post-image support is evidence and corresponding pre-image support is
anti-evidence. Removal reverses the direction. Modification uses the symmetric
difference of pre/post supports inside changed regions.

## Extension points

New parsers implement `ClaimParser.parse`. New visual backends implement
`Grounder.ground`. Neither requires changing the score implementation. This is
important for testing Grounding DINO, Grounded-SAM, or an oracle mask backend under
the same metric contract.

