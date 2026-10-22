import os
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COMMANDS = {
    ("science_checkpoint.py", command)
    for command in ("advance", "attempt", "criterion", "review", "complete", "heartbeat")
} | {
    ("science_reviewer.py", command) for command in ("prepare", "finalize")
}


class SkillCommandShapeTests(unittest.TestCase):
    def test_documented_command_flags_match_cli(self) -> None:
        skill = (ROOT / "runtime-skills/codex-science/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("### Command shapes", skill)
        block = skill.split("### Command shapes", 1)[1].split("\n## ", 1)[0]
        lines = [line for line in block.splitlines() if line.startswith("-")]
        documented: dict[tuple[str, str], set[str]] = {}

        for line in lines:
            commands = re.findall(r"`([^`]*)`", line)
            self.assertTrue(commands, line)
            invocation = commands[0]
            if "science_reviewer.py" in invocation:
                match = re.search(r'science_reviewer\.py"\s+(\w+)', invocation)
                self.assertIsNotNone(match, line)
                script, command = "science_reviewer.py", match.group(1)
            else:
                script, command = "science_checkpoint.py", invocation.split()[0]
            key = (script, command)
            self.assertNotIn(key, documented, line)
            documented[key] = set(re.findall(r"--[a-z][a-z0-9-]*", line))

        self.assertEqual(EXPECTED_COMMANDS, set(documented))
        env = os.environ.copy()
        src = str(ROOT / "src")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (src, env.get("PYTHONPATH", ""))))

        for script, command in sorted(EXPECTED_COMMANDS):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / script), command, "--help"],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            usage = result.stdout.partition("\n\n")[0]
            optional_groups = re.sub(r"\[[^\[\]]*\]", " ", usage)
            required_flags = set(re.findall(r"--[a-z][a-z0-9-]*", optional_groups))
            accepted_flags = set(re.findall(r"--[a-z][a-z0-9-]*", result.stdout))
            self.assertTrue(
                documented[(script, command)] <= accepted_flags,
                f"{script} {command} documents unknown flags: "
                f"{sorted(documented[(script, command)] - accepted_flags)}",
            )
            self.assertTrue(
                required_flags <= documented[(script, command)],
                f"{script} {command} omits required flags: "
                f"{sorted(required_flags - documented[(script, command)])}",
            )


if __name__ == "__main__":
    unittest.main()
