# Synthetic time-to-event fixtures

Every file in this directory and `tiny/` is a redistributable synthetic fixture under the repository MIT license. No row represents a patient or a real clinical outcome.

`pack.json` names the immutable input identities. `protocol.json` freezes baseline grouping, endpoint, censoring, ties, alpha, subject/event minima and the allowed censoring imbalance before table admission. `cohort.json` supplies 32 subjects with a planted group difference. `report.json` contains statistical-only proposals, explicit censoring fractions and an unavailable group B median; `evidence.json` links those proposals to the synthetic table rather than reviewer approval or a computed agreement. `expected.json` captures the read-only validator output. No fixture claims prior independent review.

Run `python3 scripts/validate_survival_pack.py examples/workflow-survival-time-to-event/pack.json` from the repository root. It prints JSON, writes nothing and exits 0. A labelled refusal prints JSON and exits 2. There is no output option.

The planted fixture has 16 subjects per group, 12/4 observed events and 4/12 censorings in A/B, respectively. The maximum frozen censoring imbalance is 0.5, exactly the observed difference; this fixture tests admission at equality and does not justify censoring assumptions. The planted log-rank p-value is approximately 9.20645081678707e-6. Group B never reaches S=0.5. Event minimum 8 is a fixture control, never a power calculation.

`tiny/` is hand-computable: A has an event at 1 and censoring at 2; B has events at 2 and 3. Events precede tied censoring. A and B first reach S=0.5 at 1 and 2; Greenwood variance there is 1/8. Log-rank has E_A=1/2+1/3=5/6, V=1/4+2/9=17/36, chi-square=1/17 and exploratory O/E ratio=13/10. The test derives the values independently of expected artifacts.

`negative-cases.json` contains labelled synthetic-fixture changes. The tests apply the changes, rebuild raw-byte hashes without weakening scientific checks and call the public validator and CLI. Cases cover too few events despite a significant report, invented median, mixed units, duplicate subject, post-baseline grouping, hidden censoring imbalance, unlabelled hazard ratio, inconsistent event flags, unlabelled post-hoc groups/test, causal/treatment/clinical wording, review/computed evidence, empty evidence, positive unavailable claims, independence aliasing, missing freeze, hazard headlines, zero time and misreported censoring. Failures and nulls are retained as inputs; missing records are unavailable.

Independent source, record and method review remains required and unavailable. Association never establishes causality. Numerical agreement never establishes physical or clinical validity. Review approval never establishes truth. Repeated or concurrent validator calls leave these files unchanged; interrupting a call may truncate stdout but cannot publish or modify an artifact.
