# Synthetic ddPCR fixtures

All counts, rules, expected artifacts and negative cases in this directory are redistributable synthetic fixtures. They establish software arithmetic only. The positive example is pack.json; its input identities hash rules.json, counts.json and report.json. expected.json contains the recomputed quantities.

```bash
python3 scripts/validate_ddpcr_absolute_quantification_pack.py examples/workflow-ddpcr-absolute-quantification/pack.json
```

A has two wells with two positives among four partitions each: pooled p = 4/8, lambda = ln(2), partition volume 0.5 uL, dilution correction 2 and reaction-to-sample multiplier 3. Concentration is 12 ln(2) copies per sample-equivalent uL. Z has zero positives among eight pooled partitions: point estimate zero and exact upper concentration -12 ln(0.025)/8 at confidence 0.95. The NTC has zero positives among four partitions and meets the frozen maximum of zero. Tiny partition counts serve hand checks; they are not suitable assay acceptance thresholds.

negative-cases.json stores mutations, not executable inputs. tests/test_workflow_ddpcr_pack.py materializes each into a fresh hash-bound bundle and asserts the declared finding. The discordant-replicates mutation refreshes valid individual-well results while retaining the defective pooled sample estimate. Counts, failed controls, unavailable concentrations and negative results are preserved. No clinical, gene dosage, disease or copy-number state conclusion follows.

The validator writes nothing. Concurrent calls share no mutable record; interruption between reads leaves the bundle unchanged. Callers must capture stdout or refusal JSON separately. The owner registers artifacts and separate claims, retains one checkpoint and obtains independent review; the pack leaves review unavailable.
