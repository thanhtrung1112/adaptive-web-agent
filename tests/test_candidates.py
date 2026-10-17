import unittest

from candidates.evaluate import evaluate
from candidates.features import controls, list_states, load_state
from candidates.generator import rank
from candidates.mutate import mutate
from candidates.targets import build_targets


class FeatureTests(unittest.TestCase):
    def test_controls_of_customer_form(self):
        cs = controls(load_state("customers-new"))
        self.assertEqual(len(cs), 9)
        save = next(c for c in cs if c["id"] == "save-customer")
        self.assertEqual((save["tag"], save["text"], save["form"]), ("button", "Lưu", "/customers/new"))
        self.assertEqual(next(c for c in cs if c["id"] == "customer-email")["label"], "Email")


class TargetTests(unittest.TestCase):
    def test_ground_truth_covers_all_baseline_selectors(self):
        targets, skipped = build_targets()
        self.assertEqual(skipped, [])
        self.assertEqual(len(targets), 79)


class GeneratorTests(unittest.TestCase):
    def test_original_element_ranks_first_on_unchanged_page(self):
        for st, eid, css in build_targets()[0]:
            cs = controls(load_state(st))
            desc = next(c for c in cs if c["element_id"] == eid)
            with self.subTest(state=st, selector=css):
                self.assertEqual(rank(desc, cs, 1)[0]["element_id"], eid)

    def test_survives_id_and_text_change(self):
        cs = controls(load_state("customers-new"))
        desc = next(c for c in cs if c["id"] == "save-customer")
        changed = [dict(c, id=f"x{i}", text="Xác nhận" if c["element_id"] == desc["element_id"] else c["text"])
                   for i, c in enumerate(cs)]
        top = rank(desc, changed, 2)
        self.assertEqual(top[0]["element_id"], desc["element_id"])
        self.assertGreater(top[0]["score"], top[1]["score"])


class MutationTests(unittest.TestCase):
    def test_mutations_keep_original_element_ids(self):
        for st in list_states():
            snap = load_state(st)
            original = {e["element_id"] for e in snap["elements"]}
            for kind in ("ids", "labels", "wrap", "decoy", "combined"):
                with self.subTest(state=st, kind=kind):
                    self.assertTrue(original <= {e["element_id"] for e in mutate(snap, kind, 0)["elements"]})

    def test_mutation_is_deterministic(self):
        snap = load_state("orders-list")
        self.assertEqual(mutate(snap, "combined", 7), mutate(snap, "combined", 7))

    def test_unchanged_and_single_mutations_are_perfect(self):
        table, _ = evaluate(kinds=["none", "ids", "labels"])
        for kind, row in table.items():
            with self.subTest(kind=kind):
                self.assertEqual(row["top1"], 1.0)


if __name__ == "__main__":
    unittest.main()
