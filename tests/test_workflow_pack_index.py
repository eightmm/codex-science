import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPackIndexTests(unittest.TestCase):
    def test_every_workflow_skill_is_indexed_with_existing_files(self):
        text = (ROOT / "docs" / "WORKFLOW_PACKS.md").read_text(encoding="utf-8")
        skills = {path.name for path in (ROOT / "authored-skills").glob("workflow-*")}
        rows = re.findall(r"^\| `(workflow-[^`]+)` \|.*\| `(scripts/[^`]+)` \| `(examples/[^`]+)` \|$",
                          text, re.M)
        names = [row[0] for row in rows]
        self.assertEqual(skills, set(names))
        self.assertEqual(len(names), len(set(names)))
        for _, script, example in rows:
            self.assertTrue((ROOT / script).is_file(), script)
            self.assertTrue((ROOT / example).is_dir(), example)


if __name__ == "__main__":
    unittest.main()
