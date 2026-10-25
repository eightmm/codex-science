import argparse
import runpy
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = [
    "package_run",
    "science_reviewer",
    "trace_citations",
    "check_claim_sufficiency",
    "retrieve_literature",
    "fetch_open_fulltext",
    "record_reference_use",
    "screen_candidates",
    "build_literature_snapshot",
    "estimate_saturation",
    "diff_literature_review",
    "resolve_citations",
    "science_checkpoint",
    "build_study_table",
    "build_evidence_graph",
    "validate_artifact",
    "search_skills",
    "verify_numerical_result",
    "validate_research_design",
    "run_statistical_analysis",
    "propagate_uncertainty",
    "check_formal_proof",
    "check_dimensions",
    "run_decision_analysis",
    "plan_next_experiment",
    "compute_probe",
    "search_counterexample",
    "science_job",
    "render_artifact_runtime",
    "render_artifact_index",
    "export_scientific_run",
    "promote_run_to_skill",
    "reference_lookup",
    "validate_manuscript_package",
    "describe_artifact",
    "diff_runs",
    "plan_selective_rerun",
    "resolve_study_families",
]

# script -> option names known to lack help (explicit expected failure).
KNOWN_MISSING: dict[str, list[str]] = {}


class _Captured(Exception):
    def __init__(self, parser):
        super().__init__("parser captured")
        self.parser = parser


def _capture_parser(script: str) -> argparse.ArgumentParser:
    def fake_parse_args(self, *args, **kwargs):
        raise _Captured(self)

    path = ROOT / "scripts" / f"{script}.py"
    with mock.patch.object(argparse.ArgumentParser, "parse_args", fake_parse_args), \
            mock.patch.object(sys, "argv", [str(path)]), \
            mock.patch.object(sys, "path", list(sys.path)):
        try:
            runpy.run_path(str(path), run_name="__main__")
        except _Captured as captured:
            return captured.parser
    raise AssertionError(f"{script}: main() never called parse_args")


def _missing_help(parser: argparse.ArgumentParser, name: str) -> list[str]:
    missing = []
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if isinstance(action, argparse._SubParsersAction):
            for sub_name, sub in action.choices.items():
                missing += _missing_help(sub, f"{name} {sub_name}".strip())
            continue
        if not action.help or action.help == argparse.SUPPRESS or not action.help.strip():
            option = "/".join(action.option_strings) or action.dest
            missing.append(f"{name or '<top>'}: {option}")
    return missing


class CliHelpCoverageTest(unittest.TestCase):
    def test_every_option_has_help(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                parser = _capture_parser(script)
                missing = _missing_help(parser, "")
                expected = KNOWN_MISSING.get(script)
                if expected:
                    self.skipTest(f"{script}: expected failure, options without help: {expected}")
                self.assertEqual(
                    [], missing,
                    f"scripts/{script}.py: option(s) lack help= (script: subcommand: option): {missing}",
                )


if __name__ == "__main__":
    unittest.main()
