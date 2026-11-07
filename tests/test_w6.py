"""Real browser record/replay and failure-path tests for W6 online healing."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from dom_snapshot.run import isolated_app
from w6.freeze import MANIFEST, ROOT, digest, structural_hash, write_json
from w6.run_heal import SCRIPTS, action, load_record, replay, summarize


class FreezeTests(unittest.TestCase):
    def test_transport_seed_changes_are_not_dom_diversity(self):
        a = '<form action="/f?mutation=W5_ORDER&seed=17"><input type="hidden" name="seed" value="17"><input id="x"></form>'
        b = '<form action="/f?seed=23&mutation=W5_ORDER"><input type="hidden" name="seed" value="23"><input id="x"></form>'
        self.assertEqual(structural_hash(a), structural_hash(b))
        self.assertNotEqual(structural_hash(a), structural_hash(b.replace('id="x"', 'id="y"')))

    def test_recovery_requires_final_task_success(self):
        rows = [{"mutation": "W5_ID", "success": False, "heal_attempts": 1,
                 "heal_actions_succeeded": 1, "abstentions": 0, "seconds": 1.0}]
        result = summarize(rows, 1)
        self.assertEqual(result["task_recovery_rate"], 0)
        self.assertIsNone(result["wrong_heal_count"])
        self.assertFalse(summarize(rows, 2)["complete"])

    def test_record_rejects_changed_manifest_and_answer_fields(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        task_id = "T001"
        record = {"manifest_sha256_lf": "stale", "locator": "css",
                  "scripts_sha256_lf": {p: manifest["source_sha256_lf"][p] for p in ("baseline/scripts.py", "baseline/w4_scripts.py")},
                  "task_success": {task_id: True},
                  "descriptors": {f"{task_id}:{i}": {"step": s, "descriptor": {"target_element_id": "e1"}}
                                  for i, s in enumerate(SCRIPTS[task_id]) if s["do"] != "goto"}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            write_json(path / "descriptors.json", record)
            with self.assertRaisesRegex(ValueError, "manifest/locator"):
                load_record(path, [task_id], manifest, "css")
            record["manifest_sha256_lf"] = digest(MANIFEST)
            write_json(path / "descriptors.json", record)
            with self.assertRaisesRegex(ValueError, "Answer/location"):
                load_record(path, [task_id], manifest, "css")


class OnlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="w6-tests-")
        cls.out = Path(cls.temp.name)
        cls.app_cm = isolated_app(cls.out)
        cls.base = cls.app_cm.__enter__()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.tasks = {t["id"]: t for t in json.loads((ROOT / "tasks/tasks_w4.json").read_text(encoding="utf-8"))}

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.app_cm.__exit__(None, None, None)
        cls.temp.cleanup()

    def output(self, name):
        path = self.out / self._testMethodName / name
        path.mkdir(parents=True)
        return path

    def record(self, task_id):
        descriptors = {}
        result = replay(self.browser, self.base, self.tasks[task_id], "M0", 0, "record", "css",
                        self.output("record"), descriptors, {})
        self.assertTrue(result["success"], result)
        self.assertTrue(descriptors)
        for value in descriptors.values():
            self.assertFalse({"element_id", "xpath", "target_element_id", "ref_eid"} & value["descriptor"].keys())
        return descriptors

    def test_records_and_recovers_id_mutation(self):
        descriptors = self.record("T001")
        out = self.output("heal")
        result = replay(self.browser, self.base, self.tasks["T001"], "W5_ID", 17, "heal", "css", out, descriptors, {})
        self.assertTrue(result["success"], result)
        self.assertGreater(result["heal_attempts"], 0)
        steps = json.loads(next((out / "traces").glob("*.json")).read_text(encoding="utf-8"))["steps"]
        self.assertTrue(all(s["executed_locator"] == s["heal"]["xpath"] for s in steps if s["heal"]))

    def test_repeated_rows_recover_in_combined_mode(self):
        descriptors = self.record("T004")
        result = replay(self.browser, self.base, self.tasks["T004"], "W5_COMBINED", 18, "heal", "css",
                        self.output("heal"), descriptors, {})
        self.assertTrue(result["success"], result)

    def test_no_healing_when_b0_matches_one(self):
        descriptors = self.record("T001")
        with patch("w6.run_heal.heal", side_effect=AssertionError("Unexpected healing")):
            result = replay(self.browser, self.base, self.tasks["T001"], "M0", 0, "heal", "css",
                            self.output("heal"), descriptors, {})
        self.assertTrue(result["success"], result)
        self.assertEqual(result["heal_attempts"], 0)

    def test_multiple_matches_abstain_and_keep_failed_step(self):
        descriptors = self.record("T001")
        def duplicate(page, base, step, locator, out):
            value = action(page, base, step, locator, out)
            if step["do"] == "goto":
                page.locator("#add-customer").evaluate("el => el.after(el.cloneNode(true))")
            return value
        out = self.output("heal")
        with patch("w6.run_heal.action", side_effect=duplicate):
            result = replay(self.browser, self.base, self.tasks["T001"], "M0", 0, "heal", "css", out, descriptors, {})
        self.assertFalse(result["success"])
        self.assertEqual(result["abstentions"], 1)
        steps = json.loads(next((out / "traces").glob("*.json")).read_text(encoding="utf-8"))["steps"]
        self.assertEqual(steps[-1]["b0_count"], 2)
        self.assertEqual(steps[-1]["trigger"], "multiple")
        self.assertEqual(steps[-1]["heal"]["status"], "abstain")
        self.assertFalse(steps[-1]["success"])

    def test_missing_candidates_does_not_execute_fallback(self):
        descriptors = self.record("T001")
        def remove(page, base, step, locator, out):
            value = action(page, base, step, locator, out)
            if step["do"] == "goto":
                page.locator("body").evaluate("el => el.innerHTML = '<main>Empty</main>'")
            return value
        out = self.output("heal")
        with patch("w6.run_heal.action", side_effect=remove):
            result = replay(self.browser, self.base, self.tasks["T001"], "M0", 0, "heal", "css", out, descriptors, {})
        self.assertFalse(result["success"])
        steps = json.loads(next((out / "traces").glob("*.json")).read_text(encoding="utf-8"))["steps"]
        self.assertEqual(steps[-1]["heal"]["reason"], "no_candidates")
        self.assertEqual(result["steps_done"], 1)


if __name__ == "__main__":
    unittest.main()
