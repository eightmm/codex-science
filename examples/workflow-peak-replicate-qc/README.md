# Synthetic fixture: replicate peak QC

Every input and expected output here is a redistributable synthetic fixture. The tiny genome, library counts and intervals are invented; none is biological evidence.

Run `python3 scripts/validate_peak_replicate_qc_pack.py examples/workflow-peak-replicate-qc/pack.json` from the repository root. It prints JSON, writes nothing and requires only Python's standard library. `pack.json` binds the rules, blacklist, peaks, report and evidence by path plus SHA-256. `expected.json` contains the expected complete result. `negative-cases.json` defines per-field mutations applied to a copy of this fixture with hashes refreshed, so defects reach their intended validation checks.

A/B have 100 reads and 50/40 reads in peaks; C has 50 reads and 5 in peaks. Thus FRiP is 0.5, 0.4 and 0.1; C fails the frozen minimum 100 reads and 0.3 FRiP and never contributes to consensus. A and B each have a blacklist-hit [80,90) peak. Their remaining 20-base sets intersect for 15 bases and cover a 25-base union: Jaccard is 3/5. Both of each replicate's two clean peaks match at reciprocal interval fraction 1/2, so their reciprocal matched-peak fraction is 1. Consensus segments [15,20) and [40,50) have support A/B.

The claim is explicitly unsupported as scientific evidence: reference computation agreement cannot establish binding, regulation, function or clinical validity. Review remains unavailable. Failed controls, unavailable records and empty peak sets retain distinct meanings. Concurrent runs write nothing; interruption leaves no partial artifacts.
