"""Verify the fixed-input 1-before-0 follow-up offline, including serialized JSON order."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics

from analyze_bits import analyze, parse_bits


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(run, baseline, prompt_one_first=False):
    meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    request = json.loads((run / "request.json").read_text(encoding="utf-8"))
    original_request = json.loads(baseline.read_text(encoding="utf-8"))
    baseline_prompt = "Generate one independent random bit. Choose 0 or 1 with equal probability, like a fair coin flip."
    require(original_request["questions"]["bit"]["instructions"] == baseline_prompt, "Unexpected baseline prompt")
    expected_request = json.loads(json.dumps(original_request))
    if prompt_one_first:
        expected_request["questions"]["bit"]["instructions"] = baseline_prompt.replace("Choose 0 or 1", "Choose 1 or 0")
    require(request == expected_request, "Request changed beyond selected prompt and criteria ordering")
    require(meta.get("prompt_one_first", False) == prompt_one_first, "Prompt-mode metadata mismatch")
    if prompt_one_first:
        require(meta["prompt_order"] == ["1", "0"], "Unexpected prompt-order metadata")
    require(list(original_request["questions"]["bit"]["criteria"]) == ["0", "1"], "Unexpected baseline order")
    require(list(request["questions"]["bit"]["criteria"]) == meta["criteria_order"] == ["1", "0"], "Unexpected follow-up order")
    require(request["model"] == meta["model"] == "jev-1.13.0", "Unexpected model")
    require(not meta["timestamp_mode"] and not meta["salt_mode"] and not meta["history_mode"], "Unexpected input mode")
    require(meta["serialized_request_body_recorded"], "Serialized request bodies missing")
    records = [json.loads(line) for line in (run / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    with (run / "samples.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    content = (run / "bits.txt").read_bytes()
    bits = parse_bits(content.decode("utf-8"))
    require(meta["complete"] and len(bits) == len(records) == len(rows) == meta["completed_n"] == meta["planned_n"] == 200, "Incomplete sample")
    require(hashlib.sha256(content).hexdigest() == meta["bits_file_sha256"], "Bit hash mismatch")
    bodies, p0, elapsed = set(), [], []
    usage, counts, pairs = Counter(), Counter(), Counter()
    for i, (record, row, bit) in enumerate(zip(records, rows, bits), 1):
        require(record["index"] == int(row["index"]) == i, "Index mismatch")
        require(record["http_status"] == 200 and record["valid_bit_answer"], "Request failed validation")
        serialized = json.loads(record["request_body"])
        require(serialized == record["request"] == request, "Request body mismatch")
        require(list(serialized["questions"]["bit"]["criteria"]) == list(record["request"]["questions"]["bit"]["criteria"]) == ["1", "0"], "Serialized request criteria order mismatch")
        bodies.add(record["request_body"])
        answer = record["response"]["answers"]["bit"]
        require(record["response"]["model"] == row["model"] == meta["model"], "Response model mismatch")
        require(answer["type"] == "choice" and answer["choice"] == row["bit"] == str(bit), "Output mismatch")
        probs = answer["probabilities"]
        require(set(probs) == {"0", "1"} and all(isinstance(p, (int, float)) and not isinstance(p, bool) and 0 <= p <= 1 for p in probs.values()) and abs(sum(probs.values())-1) < 1e-12, "Invalid probabilities")
        require(probs[str(bit)] >= max(probs.values()), "Choice differs from reported maximum probability")
        require(float(row["p0"]) == probs["0"] and float(row["p1"]) == probs["1"], "CSV probability mismatch")
        require(float(row["confidence"]) == answer["confidence"] and 0 <= answer["confidence"] <= 1, "Confidence mismatch")
        require(row["timestamp"] == record["timestamp"] and float(row["elapsed_ms"]) == record["elapsed_ms"], "Timing mismatch")
        for name in ["input_tokens", "output_tokens"]:
            require(int(row[name]) == record["response"]["usage"][name], "Usage mismatch")
            usage[name] += record["response"]["usage"][name]
        counts[str(bit)] += 1
        pairs[f"{probs['0']},{probs['1']}"] += 1
        p0.append(probs["0"])
        elapsed.append(record["elapsed_ms"])
    require(len(bodies) == 1, "Input body was not fixed across all requests")
    require({key: counts[key] for key in ["0", "1"]} == meta["counts"], "Count mismatch")
    require(dict(usage) == meta["usage"] and dict(pairs) == meta["probability_pairs_frequency"] and elapsed == meta["request_latency_ms"], "Metadata aggregate mismatch")
    result = {
        "condition": "fixed-input-both-one-first" if prompt_one_first else "fixed-input-one-first", "n": len(bits), "counts": meta["counts"],
        "model": meta["model"], "criteria_order": ["1", "0"],
        "started_at": meta["started_at"], "finished_at": meta["finished_at"],
        "p0": {"mean": statistics.mean(p0), "min": min(p0), "max": max(p0)},
        "median_e2e_ms": statistics.median(elapsed), "usage": dict(usage),
        "verification": {"records_checked": len(records), "identical_serialized_request_bodies": len(bodies), "serialized_criteria_order_verified": True, "baseline_matches_except_key_order": not prompt_one_first, "timestamp_salt_history_in_input": False, "all_choices_maximal_in_reported_probabilities": True},
        "bits_sha256": meta["bits_file_sha256"],
        "request_body_sha256": hashlib.sha256(next(iter(bodies)).encode("utf-8")).hexdigest(),
        "statistics": analyze(bits),
        "boundary": "Only outbound JSON key order changed. Prompt still says '0 or 1'. Server-side reordering is unknown. Earlier baseline and this follow-up ran at different times, without randomized interleaving.",
    }
    if prompt_one_first:
        result["instructions"] = expected_request["questions"]["bit"]["instructions"]
        result["prompt_order"] = ["1", "0"]
        result["verification"]["baseline_matches_except_key_order_and_prompt_word_order"] = True
        result["boundary"] = "Both outbound criteria order and prompt wording use 1 before 0. Server-side criteria reordering is unknown. Earlier control batches and this follow-up ran at different times, without randomized interleaving."
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--baseline", type=Path, default=Path("data/fixed-200/request.json"))
    parser.add_argument("--prompt-one-first", action="store_true", help="Verify the additional prompt-word-order reversal")
    parser.add_argument("--write-audit", action="store_true", help="Save a new audit.json without overwriting an existing file")
    args = parser.parse_args()
    if args.run is None:
        args.run = Path("followups/fixed-both-one-first-200" if args.prompt_one_first else "followups/fixed-one-first-200")
    result = verify(args.run, args.baseline, args.prompt_one_first)
    audit_path = args.run / "audit.json"
    if args.write_audit:
        with audit_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif audit_path.exists():
        require(result == json.loads(audit_path.read_text(encoding="utf-8")), "Saved audit differs from recomputation")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
