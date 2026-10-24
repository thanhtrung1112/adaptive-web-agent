import unittest
from pathlib import Path
from unittest import mock

import ranking.evaluate_w4 as ev
from ranking.encoders import HashingEncoder

SAMPLE = Path(__file__).resolve().parent.parent / "results" / "w4" / "binh_v1"


class MetricsTests(unittest.TestCase):
    def test_metrics_handle_misses(self):
        m = ev._metrics([1, 2, None, 3])
        self.assertEqual((m["pairs"], m["top1"], m["top3"], m["mrr"]), (4, 0.25, 0.75, 0.458))

    def test_split_keeps_all_mutations_of_a_task_together(self):
        pairs = ev.load_pairs(SAMPLE)
        by_task = {}
        for p in pairs:
            by_task.setdefault(p["task_id"], set()).add(ev.split_of(p["task_id"]))
        self.assertTrue(all(len(s) == 1 for s in by_task.values()))
        self.assertEqual(ev.split_of("T001"), ev.split_of("T001"))


class PipelineTests(unittest.TestCase):
    def test_ranker_never_receives_the_answer(self):
        pairs = ev.load_pairs(SAMPLE)[:3]
        seen = []

        def spy(descriptor, candidates, encoder, mode, alpha, top_k):
            seen.append((descriptor, candidates))
            return [{"element_id": candidates[0]["element_id"]}]

        with mock.patch.object(ev, "rank", spy):
            ev._run(SAMPLE, pairs, HashingEncoder(), "features", 1.0)
        self.assertEqual(len(seen), 3)
        for descriptor, candidates in seen:
            self.assertNotIn("target_element_id", descriptor)
            self.assertTrue(all("target_element_id" not in c for c in candidates))

    def test_evaluate_committed_sample(self):
        res = ev.evaluate(SAMPLE, HashingEncoder(), alphas=[0.0, 0.5, 1.0])
        self.assertEqual(res["pairs"], 18)
        self.assertIn(res["alpha_chosen_on_dev"], [0.0, 0.5, 1.0])
        for mutation in ("M1", "M2", "M3"):
            self.assertEqual(set(res["by_mutation"][mutation]["all"]), set(ev.MODES))
        self.assertEqual(res["overall"]["all"]["features"]["top1"], 1.0)
        self.assertEqual(res["misses"], [])


if __name__ == "__main__":
    unittest.main()
