import json
import unittest
from pathlib import Path

from healing.heal import heal

BASE = dict(tag="input", type="email", text="", label="Email", placeholder="", href="",
            form="/customers/new", options=[])
DESC = {**BASE, "id": "customer-email", "name": "email", "path": "body > main > form > p[2] > input"}


def cand(eid, **kw):
    return {**BASE, "id": "", "name": "", "path": "body > main > div > form > p[1] > input", "element_id": eid,
            "xpath": f"/x/{eid}", **kw}


TRUE = cand("e11", id="f3a91c", name="x72b", label="E-mail", path="body > main > div > form > p[2] > input")
NAME = cand("e9", type="text", id="k19dd", name="q03", label="Họ tên")
PHONE = cand("e13", type="tel", id="m77aa", name="z41", label="Số điện thoại")
BUTTON = cand("e15", tag="button", type="submit", label="", text="Lưu")


class HealCore(unittest.TestCase):
    def test_heals_when_id_name_label_changed(self):
        r = heal(DESC, [NAME, PHONE, TRUE, BUTTON])
        self.assertEqual((r["status"], r["eid"], r["xpath"]), ("healed", "e11", "/x/e11"))
        self.assertGreater(r["margin"], 0.2)

    def test_abstains_on_exact_duplicates_instead_of_trusting_dom_order(self):
        r = heal(DESC, [{**TRUE, "element_id": "a"}, {**TRUE, "element_id": "b"}], min_margin=0.02)
        self.assertEqual((r["status"], r["reason"], r["eid"]), ("abstain", "low_margin", None))
        self.assertEqual(r["top1_eid"], "a")  # vẫn ghi log ứng viên hạng 1

    def test_no_candidates(self):
        self.assertEqual(heal(DESC, [])["reason"], "no_candidates")

    def test_abstains_when_best_score_too_low(self):
        r = heal(DESC, [BUTTON], min_score=0.5)
        self.assertEqual((r["status"], r["reason"]), ("abstain", "low_score"))

    def test_single_candidate_has_full_margin(self):
        self.assertEqual(heal(DESC, [TRUE])["margin"], 1.0)

    def test_element_id_does_not_change_the_decision(self):
        cands = [NAME, PHONE, TRUE, BUTTON]
        a = heal({**DESC, "element_id": "e9"}, cands)
        b = heal({**DESC, "element_id": "e11"}, cands)
        c = heal(DESC, [{**x, "element_id": f"z{i}"} for i, x in enumerate(cands)])
        self.assertEqual(a["top1_eid"], b["top1_eid"])
        self.assertEqual(c["top1_eid"], "z2")

    def test_order_of_candidates_does_not_change_the_choice(self):
        self.assertEqual(heal(DESC, [BUTTON, TRUE, PHONE, NAME])["eid"], "e11")


class HealOrdinal(unittest.TestCase):
    ROW = dict(BASE, tag="input", type="text", label="Sản phẩm", id="", name="")

    def rows(self):  # hai dòng lặp giống hệt, chỉ khác vị trí
        return [dict(self.ROW, element_id="a", xpath="/r/a", path="p[1]"), dict(self.ROW, element_id="b", xpath="/r/b", path="p[1]")]

    def desc(self, ord_, n):
        return dict(self.ROW, id="order-sku-2", name="sku2", path="p[1]", ord=ord_, ord_n=n)

    def test_ordinal_resolves_identical_rows(self):
        r = heal(self.desc(1, 2), self.rows(), min_margin=0.02, use_order=True)
        self.assertEqual((r["status"], r["eid"], r["via"]), ("healed", "b", "ordinal"))
        r0 = heal(self.desc(0, 2), self.rows(), min_margin=0.02, use_order=True)
        self.assertEqual(r0["eid"], "a")

    def test_abstains_when_row_count_changed(self):
        r = heal(self.desc(1, 3), self.rows(), min_margin=0.02, use_order=True)
        self.assertEqual((r["status"], r["reason"]), ("abstain", "ambiguous_order"))

    def test_off_by_default(self):
        r = heal(self.desc(1, 2), self.rows(), min_margin=0.02)
        self.assertEqual((r["status"], r["reason"]), ("abstain", "low_margin"))

    def test_ordinal_not_used_when_margin_is_clear(self):
        r = heal(DESC, [NAME, PHONE, TRUE, BUTTON], min_margin=0.02, use_order=True)
        self.assertEqual((r["eid"], r["via"]), ("e11", "score"))

    def test_descriptor_has_ordinal_and_no_ids(self):
        from healing.descriptor import build_descriptor
        snap = {"elements": [
            {"element_id": "e1", "parent_id": "", "tag": "form", "text": "", "attributes": {"action": "/o"}, "label": None,
             "visible": True, "enabled": True},
            *[{"element_id": f"e{i}", "parent_id": "e1", "tag": "input", "text": "", "attributes": {"type": "text"},
               "label": "SKU", "visible": True, "enabled": True} for i in (2, 3)]]}
        d = build_descriptor(snap, "e3")
        self.assertEqual((d["ord"], d["ord_n"]), (1, 2))
        self.assertNotIn("element_id", d)
        self.assertNotIn("xpath", d)


class HealOnSample(unittest.TestCase):
    ROOT = Path("results/w4/binh_v1")

    def test_features_heal_sample_pairs(self):
        from w4.dataset import ranking_inputs
        pf = self.ROOT / "ground_truth" / "pairs.json"
        if not pf.exists():
            self.skipTest("không có mẫu dataset")
        pairs = json.loads(pf.read_text(encoding="utf-8"))
        self.assertTrue(pairs)
        wrong = []
        for p in pairs:
            d, cands = ranking_inputs(self.ROOT, p)
            r = heal(d, cands, mode="features")
            if r["eid"] != p["target_element_id"]:
                wrong.append((p["task_id"], p["mutation"]))
        self.assertEqual(wrong, [])


if __name__ == "__main__":
    unittest.main()
