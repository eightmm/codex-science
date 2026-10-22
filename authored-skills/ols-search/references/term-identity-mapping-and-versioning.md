# OLS term identity and mapping decisions

## Claim semantics

A **search-result claim** states that OLS returned a candidate for the recorded query, filters, service version, and access time. A **term-identity claim** assigns a concept to a term only when the ontology namespace, stable IRI/CURIE, definition, context, and intended use agree. A **synonym match** is candidate-generation evidence, not proof of equivalence. A **replacement claim** states that an ontology marks an obsolete term as replaced by a named term; it does not authorize silently rewriting historical annotations. A **cross-ontology mapping** is an asserted relation with an explicit source, direction, relation type, and confidence basis. A **biological claim** cannot be inferred from term identity, labels, or hierarchy alone.

The canonical identity is the ontology plus term IRI (and CURIE where defined), not a label. Labels can change, overlap, be multilingual, or be reused. Preserve exact returned label, synonyms, definition, namespace, IRI/CURIE, and obsolete flag. A missing definition or synonym field is unknown metadata, not evidence against identity.

For candidate decisions, record one of: `selected` (identity fits contract), `rejected` (specific mismatch), `ambiguous` (multiple plausible terms), `obsolete_with_replacement` (source declares replacement but user-level use must be assessed), `unmapped`, or `unavailable`. Do not report confidence as a calibrated probability. Describe mapping confidence as `high`, `moderate`, `low`, or `unknown` only with explicit reasons: namespace/context match; definition match; synonym-only match; organism mismatch; relation type; obsolete status; or missing provenance. Cross-ontology mappings must remain distinct from exact identity.

## Dependencies, propagation, and release

Record the ontology identifier and the release/version or update metadata reported by OLS and, where available, the upstream ontology version. Record OLS endpoint, query, filters, access time, result pages/count, and response hash. If a service or ontology version is absent, write `unknown`; never infer one from the current date. Preserve the source term's original identity in downstream evidence even if an active replacement is also recorded.

Hierarchy results are dependent on the ontology graph and selected release. Ancestor/descendant membership is propagated through graph paths and is not an independent annotation or validation. If a target term is returned by an ancestor/descendant filter, preserve the path and relation; do not count the path as extra evidence. A mapping published by a cross-reference source may derive from the same ontology axioms or curated annotation; record the mapping source and do not treat multiple representations as independent support.

## Uncertainty and controls

Carry uncertainty separately for lexical ambiguity, ontology scope, organism applicability, obsolete status, mapping direction/relation, version drift, pagination, and missing metadata. Distinguish successful zero results from unavailable service, filtered results, truncation, and a term that exists only in another ontology. State whether synonym matching, exact identifier lookup, hierarchy traversal, or cross-ontology mapping generated the candidate.

Use a known, stable term in the intended ontology as a positive control and a semantically unrelated query as a negative control. Confirm that the positive control resolves to its expected namespace/IRI and that the negative query does not yield an accepted candidate under the selected criteria. Controls check query/filter behavior, not scientific correctness. Also test a known obsolete identifier when obsolete handling matters and verify the returned obsolete flag/replacement metadata.

## Sensitivity and fragility

Repeat selection under the intended ontology alone versus the allowed ontology set; exact label/identifier versus synonym expansion; obsolete terms included versus excluded; and direct identifier matching versus any proposed cross-ontology mapping. Where hierarchy matters, compare the result with propagation disabled or the exact path removed. Record candidate identities and reasons under every setting. Mark selection **fragile** if a reasonable change switches the canonical IRI, changes an obsolete term to a different replacement, alters organism/context fit, or changes whether the claim is resolvable. Do not resolve fragility by choosing the most convenient label.

## Applicability domain and failure detection

OLS supports discovery and inspection of ontology content loaded into the service; it does not guarantee that every ontology is current, complete, authoritative for every use, or semantically aligned with another ontology. Ontology content and mapping coverage vary by release. Text search can miss a term or return lexical false positives. Broad cross-ontology searches are especially weak where labels are generic, concepts are context-dependent, or organism distinctions matter. A term match cannot validate a biomarker, diagnosis, mechanism, or experimental result.

- **Label mistaken for identity:** compare namespace and IRI/CURIE; reject label-only reporting.
- **Synonym false positive:** inspect definition, ontology, organism, and intended use; retain as candidate until these agree.
- **Obsolete term silently replaced:** check obsolete status and explicit replacement metadata; preserve both historical ID and proposed current term.
- **Cross-ontology false equivalence:** inspect mapping predicate, direction, source, and context; mark confidence low/unknown when semantics differ or mapping provenance is absent.
- **Hierarchy mistaken for evidence:** retain the graph path and report it only as ontology structure, not independent experiment or causality.
- **Silent empty result:** inspect response status, result count, filters, pages, and a positive control; distinguish zero matches from unavailable service or truncated search.
- **Release drift:** pin reported versions and rerun controls after an ontology/OLS update; withhold direct equivalence claims if identities or mappings changed.

## Candidate comparison record

Compare candidates in a fixed order and retain rejected alternatives rather than reducing the choice to a label match.

1. **Namespace:** Is the candidate in the requested ontology or explicitly allowed ontology set?
2. **Identifier:** Does the exact IRI/CURIE resolve to the returned ontology entity?
3. **Definition:** Does the definition cover the intended concept and exclude nearby concepts?
4. **Context:** Do organism, anatomy, disease stage, assay, or other qualifiers match the task?
5. **Status:** Is the term active, obsolete, or replaced, and is the replacement explicit?
6. **Relation:** Is the proposed mapping exact identity, broader/narrower, related, or unknown?
7. **Provenance:** Which ontology release, OLS response, or mapping assertion supports the choice?

Use a replacement only after checking whether it preserves the intended meaning and whether historical records must retain the obsolete identifier. An obsolete term may have more than one suggested replacement or none. Preserve that multiplicity, the source's relation semantics, and the unresolved choice; do not assume one replacement is an exact synonym.

Use a cross-ontology mapping only for the relation actually supplied. `equivalent`, `close`, `broader`, `narrower`, and `related` relations have different consequences. A broader mapping may support a coarse grouping but cannot justify replacing a specific term without losing information. A related mapping is a retrieval lead only. If the OLS response does not expose a mapping predicate or provenance, call the match lexical/curated candidate evidence rather than equivalence.

## Output decision examples

- Exact requested CURIE returned, active, matching definition/context: `selected`, confidence described as high for identity in the observed release.
- Same label in another ontology but different meaning or context: `rejected`; keep the candidate and mismatch reason.
- Synonym-only match with no definition or organism metadata: `ambiguous` or `low`, not selected by lexical overlap alone.
- Obsolete source term with one declared replacement: retain historical ID, record the declared replacement, and assess whether the downstream purpose permits migration.
- Search returned no term but endpoint and positive control worked: `unmapped` for this scope/query, not absence of the biological concept.
- Endpoint failed, truncated pages, or positive control failed: `unavailable` or incomplete retrieval, not `unmapped`.

For downstream use, preserve both the original search phrase and the selected identifier. If an annotation or source record already contains an obsolete identifier, keep that identity intact and add a separately named replacement link; do not overwrite the source record. If only a broad parent term can be resolved, report the broader granularity explicitly and do not imply that the specific child concept was found.

Term mappings can change when an ontology release adds, merges, obsoletes, or splits classes. Record the service's reported update and the upstream ontology release where available so a later analyst can distinguish an identity change from a changed search ranking. Revalidation after a release update should rerun the known-term and obsolete-term controls, then compare identifiers and mapping predicates rather than labels alone.

If the service reports multiple ontologies or languages, preserve the requested language and ontology filters. A translated label can be useful for discovery, but it does not create a new identity or justify cross-ontology equivalence. Retain the returned label language when available.

Use a mapping confidence label only as a compact summary of these recorded reasons; it is not a score produced by OLS. If a downstream contract requires a numeric confidence, obtain that value from the designated mapping method and report its calibration and version separately.

For a material scientific conclusion, route the selected term and rejected alternatives with their evidence to `$science-review`. Reviewer agreement can assess whether the mapping rationale is coherent, but it does not turn ontology membership into empirical validation.

When reporting an unresolved mapping, name the next discriminating lookup: exact identifier retrieval, ontology release check, definition comparison, or inspection of the mapping predicate. Avoid repeating a broader keyword search that cannot resolve the identity question.

## Sources

- McLaughlin et al., “OLS4: A new Ontology Lookup Service for a growing interdisciplinary knowledge ecosystem” (2025), for OLS4 service/API context; it does not establish cross-ontology equivalence.
- EMBL-EBI OLS4 API documentation and obsolete-term mapping documentation (living primary documentation; record access date and returned release metadata).
- Côté et al., “The Ontology Lookup Service: more data and better tools for controlled vocabulary queries” (2008), for the service's ontology-term lookup role, not for present-day OLS4 behavior.
