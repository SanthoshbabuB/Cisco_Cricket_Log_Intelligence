
"""
End-to-end evaluation for Cisco Cricket Log Intelligence.

Reports:
1. evaluation_history.json  - All runs with all test results
2. evaluation_history.csv   - All test results across all runs
3. latest_evaluation.json   - Latest run only
4. latest_evaluation.csv    - Latest run only
5. Timestamped JSON/CSV     - Historical snapshot of each run
"""

import csv
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_URL = "http://127.0.0.1:8000/api/search/"
DEFAULT_LIMIT = 5
REQUEST_TIMEOUT = 60

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Store all evaluation reports in evaluation/reports/
REPORT_DIR = Path(__file__).resolve().parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_JSON = REPORT_DIR / "evaluation_history.json"
HISTORY_CSV = REPORT_DIR / "evaluation_history.csv"

LATEST_JSON = REPORT_DIR / "latest_evaluation.json"
LATEST_CSV = REPORT_DIR / "latest_evaluation.csv"


# ============================================================
# TEST CASES
# ============================================================

TEST_CASES = [
    {
        "id": "TC001",
        "category": "exact_query",
        "query": "Show LBW events in MATCH001",
        "route": "mongodb_exact_query",
        "expected_result_keywords": ["MATCH001", "lbw"],
        "expected_answer_keywords": ["lbw"],
    },
    {
        "id": "TC002",
        "category": "semantic_search",
        "query": "Find deliveries that resulted in a wicket",
        "route": None,
        "expected_result_keywords": ["wicket"],
        "expected_answer_keywords": ["wicket"],
    },
    {
        "id": "TC003",
        "category": "player_search",
        "query": "Show events involving <PLAYER_NAME>",
        "route": None,
        "expected_result_keywords": ["<PLAYER_NAME>"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC004",
        "category": "team_search",
        "query": "Show events involving <TEAM_NAME>",
        "route": None,
        "expected_result_keywords": ["<TEAM_NAME>"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC005",
        "category": "match_search",
        "query": "Show all events from MATCH001",
        "route": "mongodb_exact_query",
        "expected_result_keywords": ["MATCH001"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC006",
        "category": "event_search",
        "query": "Find catches in the cricket logs",
        "route": None,
        "expected_result_keywords": ["catch"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC007",
        "category": "event_search",
        "query": "Find run-out events",
        "route": None,
        "expected_result_keywords": ["run-out"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC008",
        "category": "event_search",
        "query": "Find stumping events",
        "route": None,
        "expected_result_keywords": ["stumping"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC009",
        "category": "boundary_search",
        "query": "Find fours and sixes",
        "route": None,
        "expected_result_keywords": [],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC010",
        "category": "match_status",
        "query": "What is the status of MATCH001?",
        "route": None,
        "expected_result_keywords": ["MATCH001"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC011",
        "category": "commentary",
        "query": "Show commentary for MATCH001",
        "route": None,
        "expected_result_keywords": ["MATCH001"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC012",
        "category": "over_search",
        "query": "Show events from over <OVER_NUMBER>",
        "route": None,
        "expected_result_keywords": [],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC013",
        "category": "timestamp_search",
        "query": "Show cricket events around <TIMESTAMP>",
        "route": None,
        "expected_result_keywords": [],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC014",
        "category": "runs_search",
        "query": "Find events where runs scored were 4",
        "route": None,
        "expected_result_keywords": [],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC015",
        "category": "semantic_search",
        "query": "Which events led to a batter getting dismissed?",
        "route": None,
        "expected_result_keywords": [],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC016",
        "category": "semantic_search",
        "query": "Find moments where a fielder caught the ball",
        "route": None,
        "expected_result_keywords": ["catch"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC017",
        "category": "match_summary",
        "query": "Summarize the events in MATCH001",
        "route": None,
        "expected_result_keywords": ["MATCH001"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC018",
        "category": "player_statistics",
        "query": "How many runs did <PLAYER_NAME> score?",
        "route": None,
        "expected_result_keywords": ["<PLAYER_NAME>"],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC019",
        "category": "unsupported_query",
        "query": "What was the weather on Mars during MATCH999?",
        "route": None,
        "expected_result_keywords": [],
        "expected_answer_keywords": [],
    },
    {
        "id": "TC020",
        "category": "empty_query",
        "query": "",
        "route": None,
        "expected_result_keywords": [],
        "expected_answer_keywords": [],
        "expect_api_success": False,
    },
]


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(value):
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value).lower()).strip()


def check_keywords(text, expected_keywords):
    normalized_text = normalize(text)
    matched = []
    missing = []

    for keyword in expected_keywords:
        if normalize(keyword) in normalized_text:
            matched.append(keyword)
        else:
            missing.append(keyword)

    return matched, missing


def serialize_results(results):
    return json.dumps(results, ensure_ascii=False, default=str)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================
# EVALUATE ONE TEST
# ============================================================

def evaluate_test(test_case, run_id, run_started_at):
    started_at = time.perf_counter()

    result = {
        "run_id": run_id,
        "run_started_at": run_started_at,
        "test_id": test_case["id"],
        "category": test_case.get("category", "general"),
        "query": test_case.get("query", ""),
        "http_status": None,
        "latency_ms": None,
        "api_success": False,
        "expected_api_success": test_case.get(
            "expect_api_success", True
        ),
        "expected_route": test_case.get("route"),
        "actual_route": None,
        "route_pass": None,
        "result_count": 0,
        "retrieval_keyword_pass": None,
        "matched_result_keywords": [],
        "missing_result_keywords": [],
        "answer": "",
        "expected_answer": test_case.get("expected_answer"),
        "answer_match": None,
        "answer_keyword_pass": None,
        "matched_answer_keywords": [],
        "missing_answer_keywords": [],
        "error": None,
        "test_pass": False,
    }

    try:
        response = requests.post(
            API_URL,
            json={
                "query": test_case.get("query", ""),
                "limit": DEFAULT_LIMIT,
            },
            timeout=REQUEST_TIMEOUT,
        )

        result["http_status"] = response.status_code
        result["latency_ms"] = round(
            (time.perf_counter() - started_at) * 1000, 2
        )

        try:
            data = response.json()
        except ValueError:
            data = {}

        if not isinstance(data, dict):
            data = {}

        expected_api_success = test_case.get(
            "expect_api_success", True
        )

        result["api_success"] = (
            200 <= response.status_code < 300
            and "error" not in data
        )

        api_behavior_pass = (
            result["api_success"] == expected_api_success
        )

        records = data.get("results", [])
        if not isinstance(records, list):
            records = []

        answer = data.get("answer", "")
        if not isinstance(answer, str):
            answer = str(answer)

        actual_route = data.get("method")

        result["actual_route"] = actual_route
        result["result_count"] = len(records)
        result["answer"] = answer
        result["error"] = data.get("error")

        # Route validation
        expected_route = test_case.get("route")

        if expected_route is not None:
            result["route_pass"] = (
                actual_route == expected_route
            )

        # Retrieved-record keyword validation
        expected_result_keywords = test_case.get(
            "expected_result_keywords", []
        )

        if expected_result_keywords:
            matched, missing = check_keywords(
                serialize_results(records),
                expected_result_keywords,
            )

            result["matched_result_keywords"] = matched
            result["missing_result_keywords"] = missing
            result["retrieval_keyword_pass"] = not missing

        # Answer keyword validation
        expected_answer_keywords = test_case.get(
            "expected_answer_keywords", []
        )

        if expected_answer_keywords:
            matched, missing = check_keywords(
                answer,
                expected_answer_keywords,
            )

            result["matched_answer_keywords"] = matched
            result["missing_answer_keywords"] = missing
            result["answer_keyword_pass"] = not missing

        # Optional exact-answer comparison
        expected_answer = test_case.get("expected_answer")

        if expected_answer is not None:
            result["answer_match"] = (
                normalize(answer) == normalize(expected_answer)
            )

        checks = [api_behavior_pass]

        for key in (
            "route_pass",
            "retrieval_keyword_pass",
            "answer_keyword_pass",
            "answer_match",
        ):
            if result[key] is not None:
                checks.append(result[key])

        result["test_pass"] = all(checks)

    except requests.RequestException as exc:
        result["latency_ms"] = round(
            (time.perf_counter() - started_at) * 1000, 2
        )
        result["error"] = f"{type(exc).__name__}: {exc}"

    except Exception as exc:
        result["latency_ms"] = round(
            (time.perf_counter() - started_at) * 1000, 2
        )
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


# ============================================================
# CSV HELPERS
# ============================================================

CSV_COLUMNS = [
    "run_id",
    "run_started_at",
    "test_id",
    "category",
    "query",
    "http_status",
    "latency_ms",
    "api_success",
    "expected_api_success",
    "expected_route",
    "actual_route",
    "route_pass",
    "result_count",
    "retrieval_keyword_pass",
    "matched_result_keywords",
    "missing_result_keywords",
    "answer",
    "expected_answer",
    "answer_match",
    "answer_keyword_pass",
    "matched_answer_keywords",
    "missing_answer_keywords",
    "error",
    "test_pass",
]

LIST_FIELDS = {
    "matched_result_keywords",
    "missing_result_keywords",
    "matched_answer_keywords",
    "missing_answer_keywords",
}


def csv_row(item):
    row = item.copy()

    for key in LIST_FIELDS:
        row[key] = ", ".join(
            str(value) for value in row.get(key, [])
        )

    return row


def write_csv(path, results, append=False):
    file_has_data = path.exists() and path.stat().st_size > 0
    mode = "a" if append and file_has_data else "w"

    with path.open(
        mode,
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_COLUMNS,
            extrasaction="ignore",
        )

        if mode == "w":
            writer.writeheader()

        for item in results:
            writer.writerow(csv_row(item))


# ============================================================
# SUMMARY
# ============================================================

def build_summary(
    results,
    run_id,
    run_started_at,
    run_finished_at,
):
    total = len(results)
    passed = sum(
        1 for item in results if item["test_pass"]
    )
    failed = total - passed

    latencies = [
        item["latency_ms"]
        for item in results
        if item["latency_ms"] is not None
    ]

    successful_requests = sum(
        1 for item in results if item["api_success"]
    )

    return {
        "run_id": run_id,
        "run_started_at": run_started_at,
        "run_finished_at": run_finished_at,
        "api_url": API_URL,
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "pass_rate_percent": round(
            passed / total * 100, 2
        ) if total else 0,
        "successful_api_requests": successful_requests,
        "failed_api_requests": total - successful_requests,
        "api_success_rate_percent": round(
            successful_requests / total * 100, 2
        ) if total else 0,
        "average_latency_ms": round(
            sum(latencies) / len(latencies), 2
        ) if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
    }


# ============================================================
# HISTORY LOADING AND REPORT GENERATION
# ============================================================

def load_history():
    if not HISTORY_JSON.exists():
        return {"runs": []}

    try:
        with HISTORY_JSON.open(
            "r", encoding="utf-8"
        ) as file:
            history = json.load(file)

    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"Could not read {HISTORY_JSON}: {exc}. "
            "Back up or repair the file; history was not overwritten."
        ) from exc

    if (
        not isinstance(history, dict)
        or not isinstance(history.get("runs"), list)
    ):
        raise RuntimeError(
            f"Unexpected format in {HISTORY_JSON}. "
            "Back up or repair the file before continuing."
        )

    return history


def generate_reports(
    results,
    run_id,
    run_started_at,
    run_finished_at,
):
    summary = build_summary(
        results,
        run_id,
        run_started_at,
        run_finished_at,
    )

    report = {
        "summary": summary,
        "results": results,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    timestamped_json = REPORT_DIR / f"evaluation_{timestamp}.json"
    timestamped_csv = REPORT_DIR / f"evaluation_{timestamp}.csv"

    # Add this complete run to JSON history.
    history = load_history()
    history["runs"].append(report)

    with HISTORY_JSON.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(
            history,
            file,
            indent=4,
            ensure_ascii=False,
        )

    # Append this run's test rows to cumulative CSV history.
    write_csv(HISTORY_CSV, results, append=True)

    # Save latest-run JSON and timestamped JSON snapshots.
    for path in (LATEST_JSON, timestamped_json):
        with path.open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(
                report,
                file,
                indent=4,
                ensure_ascii=False,
            )

    # Latest-run CSV and timestamped CSV snapshots.
    write_csv(LATEST_CSV, results, append=False)
    write_csv(timestamped_csv, results, append=False)

    return summary, timestamped_json, timestamped_csv


# ============================================================
# MAIN RUNNER
# ============================================================

def main():
    run_id = uuid.uuid4().hex[:12]
    run_started_at = utc_now()

    print("=" * 75, flush=True)
    print("CISCO CRICKET LOG INTELLIGENCE - API EVALUATION", flush=True)
    print("=" * 75, flush=True)
    print(f"Run ID: {run_id}", flush=True)
    print(f"Started: {run_started_at}", flush=True)
    print(f"API: {API_URL}", flush=True)
    print(f"Total test cases: {len(TEST_CASES)}", flush=True)
    print("-" * 75, flush=True)

    # A GET may return HTTP 405 for a POST-only endpoint.
    # That is still a response from the server, so warn only on connection errors.
    try:
        requests.get(API_URL, timeout=5)
    except requests.RequestException:
        print("WARNING: Could not reach the API endpoint.", flush=True)
        print("Start Django in another terminal:", flush=True)
        print("python manage.py runserver", flush=True)
        print("Continuing to record any failures.", flush=True)
        print()

    results = []
    total = len(TEST_CASES)

    for index, test_case in enumerate(
        TEST_CASES, start=1
    ):
        print(
            f"[{index:02d}/{total:02d}] "
            f"{test_case['id']} - {test_case['category']}",
            flush=True,
        )
        print(
            f"Query: {test_case.get('query', '')}",
            flush=True,
        )

        result = evaluate_test(
            test_case,
            run_id,
            run_started_at,
        )
        results.append(result)

        status = "PASS" if result["test_pass"] else "FAIL"

        print(
            f"Result: {status} | "
            f"HTTP: {result['http_status']} | "
            f"Latency: {result['latency_ms']} ms | "
            f"Route: {result['actual_route']} | "
            f"Retrieved: {result['result_count']}",
            flush=True,
        )

        if result["missing_result_keywords"]:
            print(
                "Missing retrieval keywords:",
                result["missing_result_keywords"],
                flush=True,
            )

        if result["missing_answer_keywords"]:
            print(
                "Missing answer keywords:",
                result["missing_answer_keywords"],
                flush=True,
            )

        if result["error"]:
            print(
                f"Error: {result['error']}",
                flush=True,
            )

        passed_so_far = sum(
            1 for item in results if item["test_pass"]
        )

        print(
            f"Progress: {index}/{total} | "
            f"Passed so far: {passed_so_far} | "
            f"Failed so far: {index - passed_so_far}",
            flush=True,
        )
        print("-" * 75, flush=True)

    run_finished_at = utc_now()

    summary, timestamped_json, timestamped_csv = generate_reports(
        results,
        run_id,
        run_started_at,
        run_finished_at,
    )

    print()
    print("=" * 75, flush=True)
    print("EVALUATION SUMMARY", flush=True)
    print("=" * 75, flush=True)
    print(f"Run ID            : {run_id}", flush=True)
    print(f"Total tests       : {summary['total_tests']}", flush=True)
    print(f"Passed            : {summary['passed']}", flush=True)
    print(f"Failed            : {summary['failed']}", flush=True)
    print(
        f"Pass rate         : {summary['pass_rate_percent']}%",
        flush=True,
    )
    print(
        f"API success rate  : {summary['api_success_rate_percent']}%",
        flush=True,
    )
    print(
        f"Average latency   : {summary['average_latency_ms']} ms",
        flush=True,
    )
    print(f"Latest JSON       : {LATEST_JSON}", flush=True)
    print(f"Latest CSV        : {LATEST_CSV}", flush=True)
    print(f"History JSON      : {HISTORY_JSON}", flush=True)
    print(f"History CSV       : {HISTORY_CSV}", flush=True)
    print(f"Timestamped JSON  : {timestamped_json}", flush=True)
    print(f"Timestamped CSV   : {timestamped_csv}", flush=True)
    print("=" * 75, flush=True)


if __name__ == "__main__":
    main()

