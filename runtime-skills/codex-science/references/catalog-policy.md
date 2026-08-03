# Catalog policy

## Status meaning

- `active`: instruction-only skill with a recognized permissive license, description, and no detected credential, executable, unsafe-install, or high-stakes marker.
- `inactive`: present for provenance and possible manual review, but not authorized for automatic use.

## Inactive reasons

- `unknown-license`: license is missing or not recognized by the local policy.
- `restricted-license`: proprietary, non-commercial, or copyleft terms need manual review.
- `executable-content`: imported code exists and has not been admitted for automatic execution.
- `credentials-required`: the workflow references a token, key, or credential.
- `unsafe-instruction`: the skill includes a high-risk command or instruction pattern.
- `high-stakes-domain`: clinical or treatment output requires additional safeguards.

Explicit acknowledgement permits inspection only. It does not authorize credentials, package installation, network access, writes, paid compute, or imported script execution.
