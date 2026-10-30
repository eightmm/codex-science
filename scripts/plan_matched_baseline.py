#!/usr/bin/env python3
"""Write a matched literature baseline preregistration; never launch Codex or connect online."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.literature_evaluation_runner import _argv, load_task_set  # noqa: E402

LIFE_SCIENCE = ("alphafold", "pubmed", "uniprot", "pride")
SELECTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9._-]*")
SCORING_ENTRY_POINTS = (
    "scripts/run_literature_evaluation.py",
    "scripts/report_literature_evaluation.py",
    "src/codex_science/citation_trace.py",
    "src/codex_science/literature_evaluation_report.py",
)


def scoring_inventory(root: Path) -> list[dict[str, str]]:
    """Conservatively follow local imports in every AST branch without executing sources."""
    pending = [Path(name) for name in SCORING_ENTRY_POINTS]
    contents = {}

    def enqueue_module(module: str, *, required: bool = True) -> bool:
        if module != "codex_science" and not module.startswith("codex_science."):
            return False
        parts = module.split(".")
        prefix = root / "src" / Path(*parts)
        candidates = (prefix / "__init__.py", prefix.with_suffix(".py"))
        source = next((candidate for candidate in candidates if candidate.is_file()), None)
        if source is None:
            if required:
                raise ValueError(f"missing scoring module: {module}")
            return False
        pending.append(source.relative_to(root))
        for length in range(1, len(parts)):
            initializer = root / "src" / Path(*parts[:length]) / "__init__.py"
            if initializer.is_file():
                pending.append(initializer.relative_to(root))
        return True

    while pending:
        relative = pending.pop()
        name = relative.as_posix()
        if name in contents:
            continue
        source = root / relative
        if not source.is_file():
            raise ValueError(f"missing scoring source: {name}")
        content = source.read_bytes()
        try:
            tree = ast.parse(content, filename=name)
        except SyntaxError as error:
            raise ValueError(f"invalid scoring source: {name}") from error
        contents[name] = content
        package = list(relative.parts[1:-1]) if relative.parts[0] == "src" else []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    enqueue_module(alias.name)
            elif isinstance(node, ast.ImportFrom):
                parts = node.module.split(".") if node.module else []
                if node.level:
                    if node.level > len(package):
                        raise ValueError(f"invalid relative scoring import: {name}")
                    parts = package[:len(package) - node.level + 1] + parts
                module = ".".join(parts)
                if enqueue_module(module):
                    # An imported name may be a submodule or an attribute of the base module.
                    for alias in node.names:
                        if alias.name != "*":
                            enqueue_module(f"{module}.{alias.name}", required=False)
    benchmark = root / "benchmarks/literature-review"
    if not benchmark.is_dir():
        raise ValueError("missing scoring data directory: benchmarks/literature-review")
    for path in benchmark.rglob("*"):
        if path.is_file():
            contents[path.relative_to(root).as_posix()] = path.read_bytes()
    return [{"path": name, "sha256": hashlib.sha256(contents[name]).hexdigest()} for name in sorted(contents)]


def local_evidence() -> dict:
    """Return reviewed local observations, not a live installation or access assertion."""
    return {
        "observed_on": "2026-10-30",
        "codex_version": "codex-cli 0.166.0",
        "plain_isolation": {
            "status": "unresolved_user_decision",
            "sources": ["codex exec --help", "codex --help", "codex features list",
                        "docs/EVALUATION.md: Stage 7/8",
                        "src/codex_science/literature_evaluation_runner.py: _argv, run_evaluation"],
            "finding": "CLI supports per-invocation -c TOML overrides without editing global config. "
                       "The runner uses an inline plugins table to switch science marketplaces, "
                       "but always requests $codex-science and has no model/config passthrough. "
                       "No locally established mechanism disables all science plugins AND host skills "
                       "with the shared Codex home. Baseline command emission is blocked.",
            "candidates": [
                {"mechanism": "-c inline plugins table with science selectors disabled",
                 "side_effects": "Requires complete selector inventory; separately installed skills, "
                                 "hooks and memory may remain. Quoted dotted plugin keys are ignored "
                                 "according to docs/EVALUATION.md."},
                {"mechanism": "--ignore-user-config",
                 "side_effects": "Retains the same home but removes broader user configuration; "
                                 "host skill discovery is not established as disabled. Existing runner "
                                 "execution tests forbid this flag."},
                {"mechanism": "features.skip_host_skill_discovery with explicit plugin overrides",
                 "side_effects": "Local features list marks this under development; semantics and "
                                 "coverage are unverified. Do not assume isolation."},
                {"mechanism": "isolated CODEX_HOME",
                 "side_effects": "Excluded by this baseline requirement; changes configuration and "
                                 "may require separate sign-in. Never created by this planner."},
            ],
        },
        "life_science_plugins": {
            "status": "unverified",
            "sources": ["$HOME/.agents/plugins/marketplace.json",
                        "$CODEX_HOME/plugins/cache/<marketplace>/<plugin> (directory names only)"],
            "marketplace_sha256": "a94ed61a65e55c7c2596f95cbf66e9f163a67623e5eaa13404ddfb0ad84098e4",
            "finding": "The local marketplace is personal (one entry). None of AlphaFold, PubMed, "
                       "UniProt or PRIDE was present by name in the eight inspected cache marketplace "
                       "roots. No exact official identifier or official marketplace was established. "
                       "This bounded inspection does not prove remote unavailability.",
            "cache_marketplaces": ["claude-plugins-official", "openai-bundled", "openai-curated",
                                   "openai-curated-remote", "oh-my-setting-local", "personal",
                                   "codex-science", "codex-science-branch"],
            "refresh": "Owner must verify official provenance, exact selectors and installed versions "
                       "before an approved execution. Supplied flags are assertions, not local verification.",
        },
    }


def plugin_assignments(values: list[str]) -> dict[str, str]:
    supplied = {}
    for value in values:
        name, separator, selector = value.partition("=")
        if (not separator or name not in LIFE_SCIENCE or not SELECTOR.fullmatch(selector)
                or selector.split("@", 1)[0] == "codex-science" or name in supplied
                or selector in supplied.values()):
            raise ValueError("--life-science-plugin requires unique NAME=PLUGIN@MARKETPLACE; "
                             "NAME must be alphafold, pubmed, uniprot or pride")
        supplied[name] = selector
    return supplied


def build_plan(args: argparse.Namespace) -> dict:
    if args.repetitions < 3:
        raise ValueError("--repetitions must be at least 3")
    if not 1 <= args.timeout_seconds <= 1800:
        raise ValueError("--timeout-seconds must be between 1 and the frozen cap of 1800")
    if not args.model.strip() or any(c.isspace() for c in args.model):
        raise ValueError("--model requires one exact model/version identifier")
    if "rosalind" in args.model.lower():
        raise ValueError("GPT-Rosalind is excluded: approved institutions only")
    if not SELECTOR.fullmatch(args.plugin) or not args.plugin.startswith("codex-science@"):
        raise ValueError("--plugin must be codex-science@MARKETPLACE")
    supplied = plugin_assignments(args.life_science_plugin)
    task_set = load_task_set(args.tasks)
    tasks = task_set["tasks"]
    plugins = [{"name": name, "selector": supplied.get(name),
                "status": "user_supplied_unverified_provenance" if name in supplied else "unverified_placeholder",
                "source": "--life-science-plugin" if name in supplied else "local_evidence.life_science_plugins"}
               for name in LIFE_SCIENCE]
    conditions = [
        {"id": "A", "name": "plain Codex", "plugins": [],
         "prompt_policy": "Frozen question and tier instruction, without $codex-science.",
         "command_blockers": ["plain_plugin_and_skill_isolation_unresolved", "runner_baseline_adapter_unresolved"]},
        {"id": "B", "name": "plain Codex with official OpenAI life-science plugins", "plugins": plugins,
         "prompt_policy": "Same as A; only AlphaFold, PubMed, UniProt and PRIDE added.",
         "command_blockers": ["plain_plugin_and_skill_isolation_unresolved", "runner_baseline_adapter_unresolved"]
                             + (["unverified_plugin_identifiers"] if len(supplied) != 4 else [])},
        {"id": "C", "name": "Codex with codex-science", "plugins": [args.plugin],
         "prompt_policy": "Existing runner $codex-science prompt and tier instruction.",
         "command_blockers": []},
    ]
    environment = {"CODEX_HOME": str(args.codex_home) if args.codex_home else "<inherit existing CODEX_HOME>"}
    schedule = []
    rng = random.Random(args.seed)
    for repetition in range(1, args.repetitions + 1):
        ordered_tasks = list(tasks)
        rng.shuffle(ordered_tasks)
        for task in ordered_tasks:
            order = list(conditions)
            rng.shuffle(order)
            for condition in order:
                run_id = f"{condition['id'].lower()}-r{repetition:03d}-{task['id']}"
                run_root = args.out / "runs" / run_id
                task_root = run_root / task["id"]
                runner_argv = None
                codex_argv = None
                if condition["id"] == "C":
                    runner_argv = ["python3", str(ROOT / "scripts/run_literature_evaluation.py"), "--tasks", str(args.tasks),
                                   "--out", str(run_root), "--task", task["id"],
                                   "--timeout-seconds", str(args.timeout_seconds), "--plugin", args.plugin]
                    if args.codex_home:
                        runner_argv.extend(["--codex-home", str(args.codex_home)])
                    codex_argv = _argv("codex", task, task_root / "project", task_root / "last.md",
                                       plugin=args.plugin)
                    codex_argv[2:2] = ["--model", args.model]
                    if args.plugin == "codex-science@codex-science":
                        codex_argv[2:2] = ["-c", 'plugins={"codex-science@codex-science"={enabled=true}}']
                schedule.append({"position": len(schedule) + 1, "run_id": run_id,
                                 "condition": condition["id"], "repetition": repetition,
                                 "task_id": task["id"], "task_digest": task["digest"], "model": args.model,
                                 "timeout_seconds": args.timeout_seconds, "environment": dict(environment),
                                 "runner_plan_only_argv": runner_argv, "codex_argv": codex_argv,
                                 "command_blockers": list(condition["command_blockers"]),
                                 "runner_out": str(run_root), "receipt_directory": str(task_root),
                                 "report_argv": ["python3", str(ROOT / "scripts/report_literature_evaluation.py"),
                                                 "--tasks", str(args.tasks), "--runs", str(run_root)]})
    frozen_files = scoring_inventory(ROOT)
    grader_digest = hashlib.sha256(json.dumps(frozen_files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    count = len(schedule)
    return {
        "schema": "matched-baseline-plan-v1", "execute": False,
        "execution_authorized": False, "empirical_status": "not_run",
        "excluded": {"GPT-Rosalind": "approved institutions only"},
        "model": args.model, "model_status": "operator supplied; exact availability/version requires preflight",
        "seed": args.seed, "schedule_method": "seeded task shuffle per repetition; shuffled A/B/C within each task block",
        "tasks_path": str(args.tasks), "set_digest": task_set["set_digest"],
        "tasks": [{"id": t["id"], "digest": t["digest"], "tier": t["spec"]["expected_tier"]} for t in tasks],
        "conditions": conditions, "schedule": schedule, "frozen_files": frozen_files,
        "local_evidence": local_evidence(),
        "budget": {"conditions": 3, "tasks": len(tasks), "repetitions": args.repetitions,
                   "run_count": count, "per_task_cap_seconds": args.timeout_seconds,
                   "worst_case_wall_seconds": count * args.timeout_seconds,
                   "maximum_capacity_reruns": count,
                   "worst_case_with_reruns_seconds": 2 * count * args.timeout_seconds,
                   "scope": "Serial task wall-clock caps; excludes setup, grading and queue waits. "
                            "Reruns require a separately approved additional count and cap."},
        "grader": {"sources": [item["path"] for item in frozen_files], "sha256": grader_digest,
                   "metrics": ["all-criteria completion and 95% Wilson interval", "answered coverage and precision",
                               "citation tracing (available, traced, orphan, unavailable)", "equal-weight rubric partial_credit",
                               "wall_seconds", "input/cached-input/output/reasoning tokens when available"],
                   "analysis": "Report by condition and task/tier, paired within task and repetition; "
                               "retain per-run rows and all attempts. Independent reviewers receive anonymized outputs "
                               "and the same frozen criteria before condition labels are revealed.",
                   "limitation": "Frozen structural criteria request science-specific checkpoints and artifacts. "
                                 "Scores measure workflow compliance and can favor C; they do not establish semantic "
                                 "citation support, scientific quality or general research superiority. Missing tracing "
                                 "or usage is unknown, never zero. Do not modify the grader after seeing results."},
        "rules": {
            "invalid_run": "Digest mismatch, missing/altered receipt or artifact, wrong model/cap, or condition "
                           "contamination is invalid; retain evidence and planned slot, report attrition separately. "
                           "Never silently replace invalid runs with successes.",
            "attrition": "Keep all scheduled slots in the primary completion denominator; show missing, rejected, "
                         "unsure, failed and valid outcomes separately, plus the frozen grader's valid-receipt summaries. "
                         "Use the first eligible non-infrastructure attempt; stop after the preregistered grid/cap.",
            "infrastructure_rerun": "Only independently evidenced provider_unavailable/capacity failures are eligible "
                                    "for at most one linked rerun per slot under the same model/task/cap. Preserve both "
                                    "attempts and costs; place approved reruns after the original grid in original order. "
                                    "A second capacity failure remains attrition. No automatic launches.",
            "policy_blocks": "provider_policy_block counts as failure; never retry, rephrase or exclude it.",
            "timeouts": "Timeouts and implementation errors count as failures; reconnect/stall diagnostics alone "
                        "do not justify reruns or change grader outcomes.",
        },
        "open_decisions": [
            "Approve an exact model/version, task count and per-task time cap separately before real runs; "
            "approve any additional capacity-rerun budget separately.",
            "Resolve A/B per-run plugin AND skill isolation without global edits or an isolated CODEX_HOME; "
            "inventory shared hooks, memory, skills, tool/data access and instruction sources, and audit loaded events.",
            "Verify and supply all four official plugin selectors, marketplaces, installed versions and data access.",
            "Resolve the existing runner's science-only prompt/plugin restriction for A/B within a separately "
            "authorized adapter change; do not execute its unmodified science prompt as a plain baseline.",
            "The emitted C runner commands are plan-only scaffolding and do not pin the model. The per-run "
            "codex_argv pins it using the runner's pure argv builder. Future execution must retain the runner's "
            "timeout, event capture and receipt collection; do not append --execute to scaffolding commands.",
        ],
    }


def render_summary(plan: dict) -> str:
    budget = plan["budget"]
    hours = budget["worst_case_wall_seconds"] / 3600
    lines = ["# Matched baseline dry-run plan", "", "Status: planned only; no Codex execution or network access.",
             f"Model/version: `{plan['model']}` (operator supplied). Seed: {plan['seed']}.",
             f"Run count: 3 x {budget['tasks']} x {budget['repetitions']} = {budget['run_count']} runs.",
             f"Per-task cap: {budget['per_task_cap_seconds']} seconds; serial worst-case task wall-clock: "
             f"{budget['worst_case_wall_seconds']} seconds ({hours:g} hours), excluding setup/grading/queue waits.",
             f"Optional capacity reserve: at most {budget['maximum_capacity_reruns']} additional attempts; "
             f"combined ceiling {budget['worst_case_with_reruns_seconds']} seconds; separate approval required.",
             f"Scoring closure: {len(plan['frozen_files'])} files; SHA256: {plan['grader']['sha256']}.",
             "GPT-Rosalind excluded: approved institutions only.", "", "| Condition | Command status |", "| --- | --- |"]
    for condition in plan["conditions"]:
        status = ", ".join(condition["command_blockers"]) or "C plan-only scaffolding and pinned argv recorded"
        lines.append(f"| {condition['id']}: {condition['name']} | {status} |")
    lines.extend(["", "Exact schedule, run IDs, task/grader hashes, environment, metrics and attrition rules: `plan.json`.",
                  "Local evidence: codex-cli 0.166.0 help/features, frozen runner and docs/EVALUATION.md; "
                  "personal marketplace and bounded cache-name inspection. These are dated observations, not live verification.",
                  "A isolation remains unresolved. B plugin selectors remain locally unverified; explicit flags record "
                  "operator assertions without proving official provenance. A/B commands stay blocked until isolation and "
                  "runner adaptation are resolved.",
                  "The shared frozen grader measures structural workflow compliance and may favor C; missing citation "
                  "tracing/tokens remain unknown. Provider capacity failures may receive one approved linked rerun; "
                  "policy blocks count as failures without retry.", "", "Open decisions:"])
    lines.extend(f"- {decision}" for decision in plan["open_decisions"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new output directory; parent must exist; never overwritten")
    parser.add_argument("--tasks", type=Path, default=Path("benchmarks/literature-review/tasks.json"))
    parser.add_argument("--model", required=True, help="same exact model/version for every condition; no implicit default")
    parser.add_argument("--repetitions", type=int, default=3, help="at least 3 per condition/task")
    parser.add_argument("--seed", type=int, default=20261030, help="recorded shuffle seed")
    parser.add_argument("--timeout-seconds", type=int, default=1800, help="shared per-task cap, 1..1800 seconds")
    parser.add_argument("--plugin", default="codex-science@codex-science", help="condition C codex-science@MARKETPLACE")
    parser.add_argument("--codex-home", type=Path, help="shared existing home for future commands; never created or read here")
    parser.add_argument("--life-science-plugin", action="append", default=[], metavar="NAME=PLUGIN@MARKETPLACE",
                        help="explicit selector assertion for alphafold/pubmed/uniprot/pride; repeat for all four")
    args = parser.parse_args(argv)
    try:
        args.out = args.out.expanduser().absolute()
        args.tasks = args.tasks.expanduser().absolute()
        if args.codex_home:
            args.codex_home = args.codex_home.expanduser().absolute()
        plan = build_plan(args)
        summary = render_summary(plan)
        plan["summary_sha256"] = hashlib.sha256(summary.encode("utf-8")).hexdigest()
        payload = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        args.out.mkdir(mode=0o700)
        # Reserve the directory once; publish JSON last so partial bundles are detectable.
        for name, content in (("summary.md", summary), ("plan.json", payload)):
            with (args.out / name).open("x", encoding="utf-8") as handle:
                handle.write(content)
        print(summary, end="")
    except (OSError, ValueError) as error:
        print(f"matched baseline plan failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
