import unittest

import numpy as np

from candidates.features import controls, load_state
from candidates.generator import rank as feature_rank
from candidates.targets import build_targets
from ranking.encoders import HashingEncoder, SentenceTransformerEncoder
from ranking.evaluate import evaluate, split_of
from ranking.rank import rank
from ranking.stress import stress_mutate
from ranking.text import element_text


class TextTests(unittest.TestCase):
    def test_element_text_of_save_button_and_email_field(self):
        cs = controls(load_state("customers-new"))
        save = next(c for c in cs if c["id"] == "save-customer")
        email = next(c for c in cs if c["id"] == "customer-email")
        self.assertEqual(element_text(save), "nút Lưu; trong biểu mẫu /customers/new")
        self.assertEqual(element_text(email), "ô nhập Email; trong biểu mẫu /customers/new")


class EncoderTests(unittest.TestCase):
    def test_hashing_encoder_is_deterministic_and_normalized(self):
        a, b = HashingEncoder().encode(["nút Lưu", "nút Lưu"]), HashingEncoder().encode(["nút Lưu", "nút Lưu"])
        np.testing.assert_array_equal(a, b)
        np.testing.assert_allclose(np.linalg.norm(a, axis=1), 1.0)

    def test_similar_text_is_closer_than_different_text(self):
        v = HashingEncoder().encode(["nút Lưu khách hàng", "nút Lưu khách", "liên kết Đơn hàng"])
        self.assertGreater(float(v[0] @ v[1]), float(v[0] @ v[2]))

    def test_sentence_transformer_wrapper_with_stub_model(self):
        class Stub:  # không tải mô hình thật: chỉ kiểm tra cách gói (thứ tự, chuẩn hóa, cache)
            calls = 0
            def encode(self, texts, normalize_embeddings=True):
                Stub.calls += 1
                return np.array([[3.0, 4.0] if t == "a" else [0.0, 2.0] for t in texts])
        enc = SentenceTransformerEncoder(model=Stub())
        v = enc.encode(["a", "b", "a"])
        np.testing.assert_allclose(v, [[0.6, 0.8], [0.0, 1.0], [0.6, 0.8]])
        enc.encode(["a", "b"])
        self.assertEqual(Stub.calls, 1)  # lần hai lấy từ cache


class RankTests(unittest.TestCase):
    def test_features_mode_matches_generator_v01(self):
        cs = controls(load_state("customers-new"))
        d = next(c for c in cs if c["id"] == "save-customer")
        self.assertEqual([r["element_id"] for r in rank(d, cs, mode="features", top_k=5)],
                         [r["element_id"] for r in feature_rank(d, cs, 5)])

    def test_every_mode_scores_the_original_element_highest_on_unchanged_page(self):
        # Chỉ yêu cầu điểm cao nhất (được phép hòa): embedding không phân biệt được hai dòng sản phẩm
        # có chữ giống hệt nhau (order-sku-1 và order-sku-2), nên ở đó hai control hòa điểm.
        enc = HashingEncoder()
        for st, eid, css in build_targets()[0]:
            cs = controls(load_state(st))
            d = next(c for c in cs if c["element_id"] == eid)
            for mode in ("features", "embedding", "hybrid"):
                with self.subTest(state=st, selector=css, mode=mode):
                    ranked = rank(d, cs, enc, mode, 0.5, top_k=len(cs))
                    own = next(r["score"] for r in ranked if r["element_id"] == eid)
                    self.assertEqual(own, ranked[0]["score"])

    def test_features_and_hybrid_separate_identical_repeated_rows_but_embedding_cannot(self):
        enc = HashingEncoder()
        cs = controls(load_state("orders-two-lines"))
        second = next(c for c in cs if c["id"] == "order-sku-2")
        self.assertEqual(rank(second, cs, enc, "features", top_k=1)[0]["element_id"], second["element_id"])
        self.assertEqual(rank(second, cs, enc, "hybrid", 0.5, top_k=1)[0]["element_id"], second["element_id"])
        top2 = rank(second, cs, enc, "embedding", top_k=2)
        self.assertEqual(top2[0]["score"], top2[1]["score"])  # hòa điểm với dòng đầu

    def test_flatten_removes_form_and_path_cues_but_keeps_ids(self):
        snap = load_state("customers-new")
        flat = stress_mutate(snap, "flatten")
        self.assertTrue({e["element_id"] for e in snap["elements"]} <= {e["element_id"] for e in flat["elements"]})
        self.assertEqual({c["form"] for c in controls(flat)}, {""})


class EvaluateTests(unittest.TestCase):
    def test_split_is_deterministic_and_has_both_parts(self):
        states = {t[0] for t in build_targets()[0]}
        parts = {split_of(s) for s in states}
        self.assertEqual(parts, {"dev", "test"})
        self.assertEqual(split_of("orders-list"), split_of("orders-list"))

    def test_evaluate_structure_and_unchanged_is_perfect(self):
        res = evaluate(HashingEncoder(), kinds=["none"], alphas=[0.0, 0.5, 1.0])
        t = res["kinds"]["none"]["test"]
        self.assertEqual(set(t), {"features", "embedding", "hybrid"})
        for mode in t.values():
            self.assertEqual(mode["top1"], 1.0)


if __name__ == "__main__":
    unittest.main()
