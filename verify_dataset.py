"""Offline verification and per-condition summary; no API calls or third-party packages."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

from analyze_bits import analyze, parse_bits


ROOT = Path(__file__).resolve().parent
PROMPT = "Generate one independent random bit. Choose 0 or 1 with equal probability, like a fair coin flip."
QUESTIONS = {"bit": {"type": "choice", "instructions": PROMPT, "criteria": {"0": None, "1": None}}}
LABELS = {
    "fixed": "Fixed input", "timestamp": "Timestamp", "timestamp-salt": "Timestamp + salt",
    "salt": "Salt only", "history5": "Last 5 bits", "history-all": "Full history",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    provenance = json.loads((ROOT / "data/provenance.json").read_text(encoding="utf-8"))
    for entry in provenance["files"]:
        content = (ROOT / entry["public_path"]).read_bytes()
        require(hashlib.sha256(content).hexdigest() == entry["public_sha256"], "Export hash mismatch: " + entry["public_path"])
        if entry["public_path"].endswith(("raw.jsonl", "samples.csv", "bits.txt", "request.json", "request_initial.json", "request_template.json")):
            require(entry["original_sha256"] == entry["public_sha256"], "Raw artifact was transformed")
    grouped = defaultdict(list)
    seen_records = set()
    batches = []
    for run in catalog["runs"]:
        folder = ROOT / run["path"]
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        raw = [json.loads(line) for line in (folder / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
        bits = parse_bits((folder / "bits.txt").read_text(encoding="utf-8"))
        with (folder / "samples.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        require(meta["complete"] and len(raw) == len(bits) == len(rows) == run["n"] == meta["completed_n"] == meta["planned_n"], "Incomplete run: " + run["path"])
        require(hashlib.sha256((folder / "bits.txt").read_bytes()).hexdigest() == meta["bits_file_sha256"], "Bit hash mismatch")
        condition = run["condition"]
        static_request = json.loads((folder / "request.json").read_text(encoding="utf-8")) if condition == "fixed" else None
        history = list(meta["initial_history"]) if condition.startswith("history") else None
        if history is not None:
            require(history == [0, 1, 0, 1, 0], "Unexpected initial history")
        salts, stamps = set(), set()
        counts, usage = Counter(), Counter()
        for index, (record, row, bit) in enumerate(zip(raw, rows, bits), 1):
            require(record["index"] == int(row["index"]) == index, "Index mismatch")
            require(record["http_status"] == 200 and record["valid_bit_answer"], "Invalid or failed call")
            request = record.get("request", static_request)
            require(set(request) == {"model", "state", "questions"}, "Unexpected request fields")
            require(request["model"] == catalog["model"] and request["questions"] == QUESTIONS, "Prompt/model mismatch")
            require(list(request["questions"]["bit"]["criteria"]) == ["0", "1"], "Option order changed")
            if history is not None:
                require(request["state"] == {"previous_bits_oldest_to_newest": history}, "Feedback history mismatch")
                require(row["history_before"] == "".join(map(str, history)), "CSV history mismatch")
                history = (history if condition == "history-all" else history[1:]) + [bit]
                require(record["history_after"] == history and row["history_after"] == "".join(map(str, history)), "History update mismatch")
            else:
                state = "No other information is provided."
                if "timestamp" in condition:
                    state += "\nRequest timestamp: " + record["timestamp"]
                    require(record["timestamp"] not in stamps, "Repeated timestamp")
                    stamps.add(record["timestamp"])
                if "salt" in condition:
                    salt = record["salt"]
                    require(re.fullmatch(r"[0-9a-f]{32}", salt) is not None and salt not in salts and row["salt"] == salt, "Invalid or duplicate salt")
                    salts.add(salt)
                    state += "\nRandom salt: " + salt
                require(request["state"] == state, "Unexpected state or extra timestamp/salt")
            response = record["response"]
            answer = response["answers"]["bit"]
            require(response["model"] == row["model"] == catalog["model"] and answer["type"] == "choice", "Response model/type mismatch")
            require(answer["choice"] == row["bit"] == str(bit), "Response/CSV/bit mismatch")
            probs = answer["probabilities"]
            require(set(probs) == {"0", "1"} and all(isinstance(p, (int,float)) and not isinstance(p, bool) and math.isfinite(p) and 0 <= p <= 1 for p in probs.values()) and abs(sum(probs.values()) - 1) < 0.01, "Invalid probabilities")
            require(probs[str(bit)] >= max(probs.values()) - 1e-6, "Choice differs from displayed maximum probability")
            require(float(row["p0"]) == probs["0"] and float(row["p1"]) == probs["1"], "CSV probability mismatch")
            require(float(row["confidence"]) == answer["confidence"] and 0 <= answer["confidence"] <= 1, "Confidence mismatch")
            require(float(row["elapsed_ms"]) == record["elapsed_ms"] and row["timestamp"] == record["timestamp"], "Timing mismatch")
            identity = (record["timestamp"], json.dumps(request, sort_keys=True), json.dumps(response, sort_keys=True))
            require(identity not in seen_records, "Duplicate API observation across input batches")
            seen_records.add(identity)
            for name in ["input_tokens", "output_tokens"]:
                require(int(row[name]) == response["usage"][name], "Token mismatch")
                usage[name] += response["usage"][name]
            counts[str(bit)] += 1
            grouped[condition].append({"bit": bit, "p0": probs["0"], "elapsed_ms": record["elapsed_ms"], "usage": response["usage"], "source": run["path"], "index": index})
        require({key: counts[key] for key in ["0", "1"]} == meta["counts"] and dict(usage) == meta["usage"], "Metadata totals mismatch")
        if history is not None:
            require(history == meta["final_history"], "Final history mismatch")
        batches.append({"source": run["path"], "condition": condition, "statistics": analyze(bits)})
    conditions = []
    for condition, observations in grouped.items():
        bits = [item["bit"] for item in observations]
        p0 = [item["p0"] for item in observations]
        conditions.append({"condition": condition, "label": LABELS[condition], "n": len(bits), "zeros": bits.count(0), "ones": bits.count(1), "p0_mean": statistics.mean(p0), "p0_min": min(p0), "p0_max": max(p0), "median_e2e_ms": statistics.median(item["elapsed_ms"] for item in observations), "batch_sizes": [run["n"] for run in catalog["runs"] if run["condition"] == condition]})
    smoke = json.loads((ROOT / "data/smoke.json").read_text(encoding="utf-8"))
    require(len(smoke["cases"]) == 6 and all(case["http_status"] == 200 and case["validation"]["passed"] for case in smoke["cases"]), "Smoke test inconsistency")
    checks = sum(len(case["validation"]["expectation_checks"]) for case in smoke["cases"])
    require(checks == 17 and all(all(case["validation"]["expectation_checks"].values()) for case in smoke["cases"]), "Smoke expectations mismatch")
    observations = [item for group in grouped.values() for item in group]
    result = {
        "model": catalog["model"], "date": catalog["experiment_date"], "conditions": conditions,
        "descriptive_total": {"n": len(observations), "zeros": sum(item["bit"] == 0 for item in observations), "ones": sum(item["bit"] == 1 for item in observations), "note": "Six heterogeneous, sequentially chosen conditions; do not treat this total as one prespecified iid experiment."},
        "unique_one": [{"source": item["source"], "index": item["index"], "p0": item["p0"], "p1": 1-item["p0"]} for item in observations if item["bit"] == 1],
        "bit_test_usage": {name: sum(item["usage"][name] for item in observations) for name in ["input_tokens", "output_tokens"]},
        "smoke": {"calls": 6, "semantic_checks": checks, "summary": smoke["summary"], "excluded_from_bit_total": True},
        "verification": {"records_checked": len(seen_records), "provenance_files_checked": len(provenance["files"]), "raw_payloads_byte_identical": True, "request_options_always_ordered": ["0", "1"], "all_choices_maximal_in_reported_probabilities": True},
        "batches": batches,
    }
    require(result["descriptive_total"]["n"] == 2000, "Unexpected experiment size")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-summary", action="store_true", help="Write or refresh derived/summary.json")
    args = parser.parse_args()
    summary = verify()
    path = ROOT / "derived/summary.json"
    if args.write_summary:
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif path.exists():
        require(json.loads(path.read_text(encoding="utf-8")) == summary, "Saved summary differs from recomputation")
    print(json.dumps({key: value for key, value in summary.items() if key != "batches"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
