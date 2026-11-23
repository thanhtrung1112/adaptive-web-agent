"""Record resolved MiniBiz browser actions and grade them with the existing API/CSV oracle."""

from copy import deepcopy
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from app.mutations import COOKIE, MODES, context_url
from app.mutations_w5 import MODES as W5_MODES
from app.seed import reset_database
from baseline.checker import check_all
from baseline.run_baseline import run_step
from w6.freeze import ROOT, digest, write_json

TRACE_VERSION = 1
MUTATIONS = (*MODES, *W5_MODES)
ACTIONS = {"navigate", "click", "fill", "select", "download"}

# Position and semantic attributes identify the concrete element selected from the live DOM.
TARGET = """element => {
    const path = [];
    for (let node = element; node.parentElement; node = node.parentElement) {
        path.unshift(Array.from(node.parentElement.children).indexOf(node));
    }
    const tag = element.localName;
    return {tag, path, id: element.id, name: element.getAttribute('name'),
            type: element.getAttribute('type'), href: element.getAttribute('href'),
            form: element.form?.getAttribute('action') ?? null,
            text: ['a', 'button'].includes(tag) ? element.textContent.replace(/\\s+/g, ' ').trim() : null,
            labels: Array.from(element.labels ?? [], label => label.textContent.trim())};
}"""


def case_identity(task, mutation, mutation_seed):
    if (task["seed"] != "seed_v1" or mutation not in MUTATIONS or type(mutation_seed) is not int
            or not 0 <= mutation_seed <= 2147483647 or not re.fullmatch(r"T[0-9]{3}", task["id"])):
        raise ValueError("Invalid MiniBiz task ID, seed or mutation")
    canonical = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    paths = sorted(p for p in (ROOT / "app").rglob("*") if p.suffix in (".py", ".html", ".js", ".css"))
    paths.append(ROOT / "baseline/checker.py")
    sources = "\n".join(f"{p.relative_to(ROOT).as_posix()} {digest(p)}" for p in paths)
    return {"task_id": task["id"], "task_sha256": hashlib.sha256(canonical).hexdigest(), "seed": task["seed"],
            "seed_sha256_lf": digest(ROOT / "data/seed_v1.json"),
            "app_and_checker_sha256": hashlib.sha256(sources.encode("utf-8")).hexdigest(),
            "mutation": mutation, "mutation_seed": mutation_seed}


def local_path(value):
    return (isinstance(value, str) and value.startswith("/") and not value.startswith("//")
            and "\\" not in value and not any(ord(char) < 32 for char in value))


def validate_request(request):
    if not isinstance(request, dict) or request.get("action") not in ACTIONS:
        raise ValueError("Unsupported browser action")
    action = request["action"]
    if action == "navigate":
        if set(request) != {"action", "url"} or not local_path(request["url"]):
            raise ValueError("Navigation must use a MiniBiz-relative URL")
        return
    locator = request.get("locator")
    if (not isinstance(locator, dict) or set(locator) != {"strategy", "value"}
            or locator["strategy"] not in {"css", "xpath"} or not isinstance(locator["value"], str)
            or not locator["value"].strip()):
        raise ValueError("A resolved CSS or XPath locator is required")
    fields = {"action", "locator"}
    if action in {"fill", "select"}:
        argument = "label" if action == "select" and "label" in request else "value"
        if not isinstance(request.get(argument), str):
            raise ValueError(f"{action} requires a string {argument}")
        fields.add(argument)
    if set(request) != fields:
        raise ValueError("Unexpected action fields")


def stable_api(value):
    """Ignore wall-clock creation time on MiniBiz order records when comparing replays."""
    if isinstance(value, dict):
        order = str(value.get("id", "")).startswith("ORD-") and "items" in value
        return {key: stable_api(item) for key, item in value.items() if not (order and key == "created_at")}
    if isinstance(value, list):
        return [stable_api(item) for item in value]
    return value


def grade(context, base, task, download=None):
    responses = {}

    def get(path):
        if not local_path(path) or not path.startswith("/api/"):
            raise ValueError("Task criteria must use a MiniBiz API path")
        if path not in responses:
            response = context.request.get(base + path, max_redirects=0)
            if not response.ok:
                raise ValueError(f"API {path}: HTTP {response.status}")
            responses[path] = response.json()
        return responses[path]

    passed, message = check_all(get, task, download)
    return {"passed": passed, "message": message, "api": stable_api(responses),
            "csv_sha256_lf": digest(download) if download else None}


class TraceSession:
    """The executor passes the concrete action it chose. The harness owns browser execution."""

    def __init__(self, page, base, output, case, max_steps):
        self.page = page
        self.base = base
        self.output = output
        self.case = case
        self.max_steps = max_steps
        self.steps = []
        self.download = None

    def location(self):
        url = self.page.url
        if url == "about:blank":
            return None
        if not url.startswith(self.base + "/"):
            raise ValueError("Browser left MiniBiz")
        parts = urlsplit(url)
        return urlunsplit(("", "", parts.path, parts.query, parts.fragment))

    def act(self, request, *, decision=None, expected=None):
        validate_request(request)
        index = len(self.steps)
        if index >= self.max_steps:
            raise ValueError("Task exceeded max_steps")
        step = {"index": index, "request": deepcopy(request), "target": None, "before_url": None, "after_url": None,
                "success": False, "decision": deepcopy(decision)}
        self.steps.append(step)
        started = time.perf_counter()
        try:
            step["before_url"] = self.location()
            action = request["action"]
            if action == "navigate":
                url = context_url(request["url"], self.case["mutation"], self.case["mutation_seed"])
                legacy = {"do": "goto", "url": url}
                strategy = "css"
            else:
                strategy, value = request["locator"]["strategy"], request["locator"]["value"]
                locator = self.page.locator(value if strategy == "css" else "xpath=" + value)
                if locator.count() != 1:
                    raise ValueError("Locator must match exactly one element")
                step["target"] = locator.evaluate(TARGET)
                legacy = {"do": action, strategy: value,
                          **{key: request[key] for key in ("value", "label") if key in request}}
            if expected and any(step[field] != expected[field] for field in ("before_url", "target")):
                raise ValueError(f"Replay diverged before action {index}")
            if action == "select" and "value" in request:
                locator.select_option(value=request["value"])
            else:
                filename = self.output / "downloads" / f"{self.case['task_id']}-{index:02d}.csv"
                self.download = run_step(self.page, self.base, legacy, strategy, filename) or self.download
            step["after_url"] = self.location()
            cookies = {cookie["name"]: cookie["value"] for cookie in self.page.context.cookies(self.base)}
            if cookies.get(COOKIE) != f"{self.case['mutation']}:{self.case['mutation_seed']}":
                raise ValueError("MiniBiz lost the configured mutation context")
            if expected and step["after_url"] != expected["after_url"]:
                raise ValueError(f"Replay diverged after action {index}")
            step["success"] = True
        except Exception as exc:
            step["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
            raise
        finally:
            step["seconds"] = round(time.perf_counter() - started, 4)
        return step


def run_case(browser, base, task, output, producer, *, agent, mutation="M0", mutation_seed=0, original=None):
    """Run one task in an isolated, reset MiniBiz; the agent sees only public task inputs."""
    case = case_identity(task, mutation, mutation_seed)
    reset_database()
    trace = {"version": TRACE_VERSION, "case": case, "agent": agent, "success": False}
    with browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 800}) as context:
        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
        context.add_cookies([{"name": COOKIE, "value": f"{mutation}:{mutation_seed}", "url": base}])
        page = context.new_page()
        page.set_default_timeout(5000)
        session = TraceSession(page, base, Path(output), case, task["max_steps"])
        trace["steps"] = session.steps
        trace["precheck"] = grade(context, base, task)
        started = time.perf_counter()
        try:
            if trace["precheck"]["passed"]:
                raise ValueError("Task already meets success criteria on the seed")
            if original and trace["precheck"] != original["precheck"]:
                raise ValueError("Replay precheck differs from the recorded seed state")
            public_task = {key: task[key] for key in ("id", "goal", "start_url", "max_steps")}
            producer(session, public_task)
            if not session.steps or not all(step["success"] for step in session.steps):
                raise ValueError("Agent has no complete sequence of browser actions")
        except Exception as exc:
            trace["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
        trace["seconds"] = round(time.perf_counter() - started, 4)
        trace["verification"] = grade(context, base, task, session.download)
        trace["download"] = session.download.relative_to(output).as_posix() if session.download else None
        trace["success"] = not trace.get("error") and trace["verification"]["passed"]
        if original:
            if trace["success"] and trace["verification"] != original["verification"]:
                trace.update(success=False, error="Replay API/CSV observations differ from the recorded result")
            trace["replay_matches"] = trace["success"]
    write_json(Path(output) / "traces" / f"{task['id']}.json", trace)
    return trace


def replay_case(browser, base, task, output, trace):
    """Replay only resolved browser actions, never rerun the planner, model or ranker."""
    if trace.get("version") != TRACE_VERSION or not trace.get("success"):
        raise ValueError("Replay requires a successful W8 trace of the supported version")
    case, steps = trace["case"], trace["steps"]
    if case != case_identity(task, case["mutation"], case["mutation_seed"]):
        raise ValueError("Trace task, data seed, app or checker differs from the local benchmark")
    if not steps or len(steps) > task["max_steps"]:
        raise ValueError("Invalid recorded step count")
    for index, step in enumerate(steps):
        if step.get("index") != index or step.get("success") is not True:
            raise ValueError("Recorded steps must be consecutive and successful")
        validate_request(step["request"])

    def play(session, _task):
        for step in steps:
            session.act(step["request"], decision=step.get("decision"), expected=step)

    return run_case(browser, base, task, output, play, agent="replay", mutation=case["mutation"],
                    mutation_seed=case["mutation_seed"], original=trace)
