import pytest

from w7.real_site_eval import summarize
from w7.target_check import check_link_destination


@pytest.mark.parametrize(("candidate", "rejected"), [
    ("https://docs.example.org/tutorial/topic.html#lists", False),
    ("./topic.html#lists", False),
    ("topic.html#sets", True),
    ("topic.html?version=2#lists", True),
    ("subtopic.html#lists", True),
    ("//other.example.org/tutorial/topic.html#lists", True),
    ("", True),
])
def test_recorded_link_destination(candidate, rejected):
    result = check_link_destination("https://docs.example.org/tutorial/index.html", "topic.html#lists", candidate)
    assert result["likely_wrong"] is rejected


def test_wrong_recovery_counts_accepted_wrong_choices_only():
    wrong = {"correct": False, "guard": {"likely_wrong": False}}
    rejected = {"correct": False, "guard": {"likely_wrong": True}}
    base = {"attempted_recovery": True, "task_seconds": 0.8, "recovery_seconds": 0.2}
    rows = [{**base, "outcome": "wrong_recovery", "proposals": [wrong]},
            {**base, "outcome": "correct_abstention", "proposals": [rejected]},
            {**base, "outcome": "no_recovery", "proposals": []}]
    summary = summarize(rows, [])
    assert summary["wrong_recovery_rate"] == pytest.approx(1 / 3)
    assert summary["wrong_proposals_rejected"] == 1
    assert summarize([], [])["wrong_recovery_rate"] is None


def test_unknown_usage_does_not_become_zero_cost():
    summary = summarize([], [{"seconds": 0.2, "status": "error", "usage": {"input_tokens": None}}])
    assert summary["llm_errors"] == 1
    assert summary["input_tokens"] is None
    assert summary["estimated_cost_usd"] is None
