import copy
import json

import pytest
from playwright.sync_api import sync_playwright

from dom_snapshot.run import isolated_app
from w6.freeze import ROOT
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
