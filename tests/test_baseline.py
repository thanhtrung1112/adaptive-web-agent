import json
import unittest
from pathlib import Path

from baseline.scripts import SCRIPTS

ROOT = Path(__file__).resolve().parent.parent


class BaselineScriptTests(unittest.TestCase):
    def test_every_pilot_task_has_script(self):
        ids = [t["id"] for t in json.loads((ROOT / "tasks" / "pilot_tasks.json").read_text(encoding="utf-8"))]
        self.assertEqual(sorted(ids), sorted(SCRIPTS))

    def test_every_locator_step_has_css_and_xpath(self):
        for task_id, steps in SCRIPTS.items():
            for step in steps:
                if step["do"] != "goto":
                    with self.subTest(task=task_id, step=step["do"]):
                        self.assertTrue(step["css"].strip())
                        self.assertTrue(step["xpath"].strip())


if __name__ == "__main__":
    unittest.main()
