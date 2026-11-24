import pytest
from llm.fallback import resolve, _top_k
from w7.target_check import check_found


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.kwargs = None
    def generate_json(self, **kwargs):
        self.kwargs = kwargs
        return self.result


def packet():
    return {"version": "w7-fallback-v1", "action": "click",
            "objective": "Lưu thông tin khách hàng, không lưu nhân viên",
            "descriptor": {"text": "Lưu"}, "trigger": "low_margin",
            "candidates": [
                {"candidate_id": "c1", "text": "Lưu", "context_text": "Nhân viên"},
                {"candidate_id": "c2", "text": "Lưu", "context_text": "Khách hàng"}],
            "semantic_topk": [{"candidate_id": "c1", "score": .9}]}


def test_resolve_selects_only_offered_top_k_candidate():
    client = FakeClient({"decision": "select", "candidate_id": "c2", "reason": "Đúng ngữ cảnh"})
    result = resolve(packet(), client)
    assert result["decision"] == "select" and result["candidate_id"] == "c2"
    assert [c["candidate_id"] for c in client.kwargs["payload"]["candidates"]] == ["c1", "c2"]
    assert "evaluation-only" not in str(client.kwargs)


def test_resolve_supports_abstention():
    client = FakeClient({"decision": "abstain", "candidate_id": None, "reason": "Mơ hồ"})
    assert resolve(packet(), client)["decision"] == "abstain"


def test_resolve_rejects_selection_outside_top_k():
    p = packet(); p["candidates"] = [{"candidate_id": f"c{i}", "text": "Lưu"} for i in range(1, 9)]
    client = FakeClient({"decision": "select", "candidate_id": "c8", "reason": "bad"})
    result = resolve(p, client)
    assert result == {"decision": "abstain", "candidate_id": None, "reason": "candidate_outside_top_k"}


def test_empty_candidates_abstain_without_api_call():
    client = FakeClient(None)
    p = packet(); p["candidates"] = []
    assert resolve(p, client)["decision"] == "abstain"
    assert client.kwargs is None


def test_check_found_detects_wrong_business_context_and_accepts_target():
    desc = {"text": "Lưu"}
    wrong = check_found(desc, {"text": "Lưu", "context_text": "Nhân viên"},
                        "Lưu thông tin khách hàng, không lưu nhân viên", threshold=.2)
    right = check_found(desc, {"text": "Lưu", "context_text": "Khách hàng"},
                        "Lưu thông tin khách hàng, không lưu nhân viên", threshold=.2)
    assert wrong["likely_wrong"] is True
    assert right["likely_wrong"] is False


def test_check_found_threshold_validation():
    with pytest.raises(ValueError):
        check_found({}, {}, "", threshold=1.5)


@pytest.mark.parametrize(("href", "rejected"), [
    ("/customers/2/edit?mutation=W5_ID&seed=17&next=detail", False),
    ("/customers/3/edit?next=detail", True),
    ("/customers/2/edit?next=orders", True),
    ("https://outside.example/customers/2/edit?next=detail", True),
])
def test_recorded_customer_link_uses_record_identity(href, rejected):
    descriptor = {"tag": "a", "text": "Sửa", "href": "/customers/2/edit?next=detail"}
    candidate = {"tag": "a", "text": "Sửa", "href": href}
    assert check_found(descriptor, candidate, page_url="http://localhost/customers/2")["likely_wrong"] is rejected


def test_save_button_must_submit_the_recorded_form():
    descriptor = {"tag": "button", "text": "Lưu", "type": "submit", "ord_n": 1, "form": "/customers/2/edit"}
    page_url = "http://localhost/customers/2/edit"
    found = check_found(descriptor, {**descriptor, "form": "/customers/2/edit?seed=17"}, page_url=page_url)
    assert found["reason"] == "unique_submit_in_recorded_form"
    wrong = check_found(descriptor, {**descriptor, "form": "/customers/3/edit"}, page_url=page_url)
    assert wrong["likely_wrong"] is True
    ambiguous = check_found(descriptor, {**descriptor, "ord_n": 2}, page_url=page_url)
    assert ambiguous["likely_wrong"] is True
