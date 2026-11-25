import copy
import json

import pytest
from playwright.sync_api import sync_playwright

from dom_snapshot.run import isolated_app
from w6.freeze import ROOT
from w8 import agent
from w8.harness import replay_case, run_case, validate_request
from w8.run import load_tasks, reference_producer


def test_w8_dataset_retains_the_30_frozen_tasks_and_adds_ten():
    frozen = json.loads((ROOT / "tasks/tasks_w4.json").read_text(encoding="utf-8"))
    tasks = load_tasks()
    assert len(tasks) == 40
    assert list(tasks.values())[:30] == frozen


@pytest.mark.parametrize("url", ["https://example.org", "//example.org/", r"/\example.org/", "/\n/customers"])
def test_recorded_navigation_is_limited_to_minibiz_paths(url):
    with pytest.raises(ValueError, match="MiniBiz-relative"):
        validate_request({"action": "navigate", "url": url})


@pytest.fixture(scope="module")
def minibiz(tmp_path_factory):
    server = tmp_path_factory.mktemp("w8-server")
    with isolated_app(server) as base, sync_playwright() as pw, pw.chromium.launch() as browser:
        yield browser, base


@pytest.mark.parametrize("task_id", ["T003", "T006"])
def test_replay_rechecks_persisted_api_or_csv_from_a_fresh_seed(minibiz, tmp_path, task_id):
    browser, base = minibiz
    task = load_tasks()[task_id]
    record = run_case(browser, base, task, tmp_path / "record", reference_producer("css"), agent="b0-css")
    assert record["success"], record
    replay = replay_case(browser, base, task, tmp_path / "replay", record)
    assert replay["replay_matches"], replay
    assert record["verification"] == replay["verification"]
    if task_id == "T003":
        endpoint = "/api/customers?email=nguyen.dung@example.com"
        assert replay["precheck"]["api"][endpoint]["customers"][0]["phone"] == "0900000002"
        assert replay["verification"]["api"][endpoint]["customers"][0]["phone"] == "0987654321"
    else:
        assert replay["verification"]["csv_sha256_lf"]
        assert (tmp_path / "replay" / replay["download"]).is_file()


def test_replay_stops_before_using_a_different_target(minibiz, tmp_path):
    browser, base = minibiz
    task = load_tasks()["T003"]
    original = run_case(browser, base, task, tmp_path / "record", reference_producer("css"), agent="b0-css")
    changed = copy.deepcopy(original)
    changed["steps"][1]["target"]["id"] = "another-input"
    replay = replay_case(browser, base, task, tmp_path / "replay", changed)
    assert replay["success"] is False
    assert "Replay diverged before action 1" in replay["error"]
    assert replay["verification"]["passed"] is False
    assert len(replay["steps"]) == 2


@pytest.mark.parametrize("seed", [17, 18])
def test_agent_replays_customer_update_after_submit_ids_change(minibiz, tmp_path, monkeypatch, seed):
    browser, base = minibiz
    task = load_tasks()["T003"]
    email, phone = "nguyen.dung@example.com", "0987654321"

    class PlannerFixture:
        def __init__(self, *_args, **_kwargs):
            pass

        def generate_json(self, *, schema_name, payload, **_kwargs):
            assert schema_name == "minibiz_intent", "The submit controls must resolve without model fallback"
            assert payload["goal"] == task["goal"]
            return {"operations": [{"kind": "update_phone", "items": [], "slots": [
                {"key": "customer_email", "value": email, "source": email},
                {"key": "phone", "value": phone, "source": phone},
            ]}]}

        def close(self):
            pass

    monkeypatch.setattr(agent, "StructuredClient", PlannerFixture)
    record = run_case(browser, base, task, tmp_path / "record", agent.producer,
                      agent="w7-semantic-llm", mutation="W5_ID", mutation_seed=seed)
    assert record["success"], record
    controls = {step["decision"]["control"]: step for step in record["steps"]}
    for control, legacy_id in (("search_submit", "search-customers"), ("save_phone", "save-customer")):
        step = controls[control]
        assert step["target"]["id"] != legacy_id
        assert step["decision"]["target_check"]["reason"] == "unique_submit_in_recorded_form"

    replay = replay_case(browser, base, task, tmp_path / "replay", record)
    endpoint = f"/api/customers?email={email}"
    assert replay["replay_matches"], replay
    assert replay["precheck"]["api"][endpoint]["customers"][0]["phone"] == "0900000002"
    assert replay["verification"]["api"][endpoint]["customers"][0]["phone"] == phone


def test_agent_rejects_ambiguous_customer_form_submit(minibiz):
    browser, base = minibiz
    with browser.new_page() as page:
        page.goto(base + "/customers")
        page.locator('form[action="/customers"]').evaluate("""form => {
            const button = document.createElement('button');
            button.type = 'submit';
            button.textContent = 'Tìm';
            form.append(button);
        }""")
        step = {"action": "click", "target": "Tìm", "context": {"control": "search_submit"}}
        with pytest.raises(ValueError, match="Expected one submit button"):
            agent._resolve_target(page, base, step, None, 0)
