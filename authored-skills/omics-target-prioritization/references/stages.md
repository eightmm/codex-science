# Identity and scope

`omics-target-input-v1` requires an explicit boolean `synthetic`, unique frozen
`gene_ids`, `expression_unit: log2-normalized-expression`, normalization provenance,
reference and case conditions, boolean `paired`, `minimum_donors >= 2`, desired
direction (`higher`/`lower`), nonnegative `minimum_signed_difference` and essential
controls. Gene IDs must already be reconciled to stable source identifiers.
The helper accepts one comparable tissue/cell context per analysis. Separate
contexts or normalization scales require separate inputs and review.

Each sample records unique `sample_id`, biological `donor_id`, `cohort_id`,
`condition`, `batch` and an expression object covering every gene. Null denotes
missingness. Finite negative log-expression values are allowed; raw counts,
NaN/Infinity, implicit missing fields and boolean expression values are refused.

# Design and descriptive estimator

Every cohort must contain both conditions and at least one batch spanning both;
otherwise condition is fully confounded with cohort/batch and analysis stops.
The output reports unique biological donor counts per condition in each batch,
case-donor proportions and an unresolved unadjusted imbalance diagnostic. Any
single-condition batch or unequal case/control donor proportions across batches
prevents prioritization of that cohort's targets while preserving descriptive
effects. Technical repeats never inflate these counts. Check both the declared
design and per-gene observed donors, because missing expression can introduce
imbalance in an otherwise balanced design. This is a conservative design check,
not fitted batch correction or proof that all confounding is removed.
Donors may not recur across independent cohorts.
Paired designs require both conditions for each donor; unpaired designs forbid
cross-condition donor reuse.

Average technical samples within donor/condition/cohort first. For paired data,
take case-minus-reference within each complete donor and average those contrasts.
For unpaired data, subtract the reference donor mean from the case donor mean.
Per-cohort SE uses sample variance: paired contrast variance/n, or the sum of each
unpaired group's variance/n, followed by sqrt. With fewer than two units SE is
unavailable. No p-values or hypothesis-testing claims are produced.

The cross-cohort descriptor is an equal-cohort mean of available contrasts; it is
not a meta-analysis. Each cohort must meet the frozen donor minimum per gene.
Missing technical samples and genes remain explicit. Opposite cohort directions,
insufficient donors, unresolved batch imbalance, failed essential controls and effects below the frozen
signed threshold exclude prioritization while retaining all descriptive values.

# Evidence and failure semantics

Each evidence row records unique `record_id`, `gene_id`, `origin_id`, source,
`source_release`, unique `cohort_ids` and direction (`supports`, `contradicts`,
`neutral`). Connected records sharing any origin or cohort form one dependency
group. The output marks overlaps with expression cohorts rather than treating
them as external replication. Opposing external evidence prevents prioritization;
missing evidence is labeled unavailable, never encoded as negative evidence.
The groups are bookkeeping over declared identities, not verified independence.

# Review and handoff

Review the biological sampling unit, normalization source, missingness, batch
design, source identifiers and evidence dependencies. The shortlist is exploratory
and ordered by the declared signed descriptive effect, not clinical utility.
Before screening/design, freeze a concrete protein target/construct and establish
which evidence would discriminate a causal or functional hypothesis.
