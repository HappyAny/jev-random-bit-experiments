"""Collect Jev fair-bit Choice outputs with optional timestamp, salt, or history."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import time

import requests

from smoke import BASE_URL, call, probability


class BodyRecordingSession(requests.Session):
    """Record the serialized JSON body passed to the HTTP adapter, never headers."""
    last_request_body = None

    def send(self, request, **kwargs):
        self.last_request_body = request.body.decode("utf-8") if isinstance(request.body, bytes) else request.body
        return super().send(request, **kwargs)


def with_timestamp(payload, timestamp):
    return {**payload, "state": payload["state"] + "\nRequest timestamp: " + timestamp}


def with_salt(payload, salt):
    return {**payload, "state": payload["state"] + "\nRandom salt: " + salt}


def with_history(payload, history):
    return {**payload, "state": {"previous_bits_oldest_to_newest": list(history)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=200, help="Fixed number of sequential requests; no outcome-based stopping")
    parser.add_argument("--model", default="jev-1.13.0")
    parser.add_argument("--one-first", action="store_true", help="Order the criteria keys as 1 then 0; keep the prompt wording unchanged")
    parser.add_argument("--timestamp", action="store_true", help="Append the actual per-request timestamp to model-visible state")
    parser.add_argument("--salt", action="store_true", help="Append a fresh secrets.token_hex(16) random salt to model-visible state")
    history_options = parser.add_mutually_exclusive_group()
    history_options.add_argument("--history", action="store_true", help="Use the previous five returned bits as a rolling model-visible state")
    history_options.add_argument("--history-all", action="store_true", help="Keep the five initial bits and every returned bit in model-visible state")
    parser.add_argument("--initial-history", help="Five initial bits, e.g. 01011; default uses five local secrets.randbits(1) draws")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    history_enabled = args.history or args.history_all
    if args.n < 1:
        parser.error("--n must be positive")
    if history_enabled and (args.timestamp or args.salt):
        parser.error("History modes cannot be combined with --timestamp or --salt")
    if args.initial_history is not None and (not history_enabled or len(args.initial_history) != 5 or set(args.initial_history) - {"0", "1"}):
        parser.error("--initial-history requires a history mode and exactly five binary digits")
    tz = timezone(timedelta(hours=8))
    criteria_order = ["1", "0"] if args.one_first else ["0", "1"]
    payload = {
        "model": args.model,
        "state": "No other information is provided.",
        "questions": {
            "bit": {
                "type": "choice",
                "instructions": "Generate one independent random bit. Choose 0 or 1 with equal probability, like a fair coin flip.",
                "criteria": {key: None for key in criteria_order},
            }
        },
    }
    history = ([int(c) for c in args.initial_history] if args.initial_history is not None else [secrets.randbits(1) for _ in range(5)]) if history_enabled else None
    initial_history = list(history) if history_enabled else None
    if args.dry_run:
        preview = with_history(payload, history) if history_enabled else (with_timestamp(payload, datetime.now(tz).isoformat(timespec="microseconds")) if args.timestamp else payload)
        if args.salt:
            preview = with_salt(preview, secrets.token_hex(16))
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0
    secret = os.environ.get("TYPESAFE_API_KEY", "").strip() or getpass.getpass("TypeSafe API key (hidden): ").strip()
    if not secret:
        parser.error("A TypeSafe API key is required")
    started = datetime.now(tz)
    prefix = "random-bits" + ("-timestamp" if args.timestamp else "") + ("-salt" if args.salt else "") + "-"
    if history_enabled:
        prefix = "random-bits-history-all-" if args.history_all else "random-bits-history5-"
    if args.one_first:
        prefix += "one-first-"
    root = Path(__file__).resolve().parent / "results" / (prefix + started.strftime("%Y%m%d-%H%M%S-%f"))
    root.mkdir(parents=True, exist_ok=False)
    request_filename = "request_template.json" if args.timestamp or args.salt else "request.json"
    request_definition = with_timestamp(payload, "<per-request ISO 8601 timestamp>") if args.timestamp else payload
    if history_enabled:
        request_filename = "request_initial.json"
        request_definition = with_history(payload, history)
    if args.salt:
        request_definition = with_salt(request_definition, "<per-request 32 hex chars from secrets.token_hex(16)>")
    (root / request_filename).write_text(json.dumps(request_definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "started_at": started.isoformat(), "base_url": BASE_URL,
        "planned_n": args.n, "model": args.model,
        "design": ("One Choice per request; sequential; state contains the five initial bits and ALL earlier actual outputs, oldest to newest; append each actual output without truncation; initial seed excluded from sample count; no timestamp, salt, local output sampling, automatic retry or outcome-dependent stopping." if args.history_all else "One Choice per request; sequential; state is previous five bits, oldest to newest; each actual output replaces the oldest history bit; initial seed excluded from sample count; no timestamp, salt, local output sampling, automatic retry or outcome-dependent stopping." if args.history else "One Choice question per HTTP request; sequential; only enabled timestamp/salt lines vary in state; other input unchanged; no history, local output sampling, automatic retry or outcome-dependent stopping."),
        "history_mode": history_enabled,
        "history_retention": "all" if args.history_all else "last5" if args.history else None,
        "history_window": None if args.history_all else 5 if args.history else 0,
        "initial_history": initial_history,
        "initial_history_source": ("explicit --initial-history" if args.initial_history is not None else "five local secrets.randbits(1) draws") if history_enabled else None,
        "timestamp_mode": args.timestamp,
        "timestamp_location": "state: appended Request timestamp line" if args.timestamp else "local log only, not sent to model",
        "salt_mode": args.salt,
        "salt_source": "secrets.token_hex(16), operating-system randomness" if args.salt else None,
        "salt_bytes": 16 if args.salt else 0,
        "salt_location": "state: appended Random salt line" if args.salt else None,
        "request_definition_file": request_filename,
        "criteria_order": criteria_order, "transport": "requests.Session, redirects disabled, default TLS verification",
        "serialized_request_body_recorded": args.one_first,
    }
    (root / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_directory": str(root), "planned_n": args.n, "initial_history": initial_history}), flush=True)
    counts = {"0": 0, "1": 0}
    tokens = {"input_tokens": 0, "output_tokens": 0}
    elapsed = []
    probabilities_seen = {}
    completed = 0
    overall_start = time.perf_counter()
    with BodyRecordingSession() as session, (root / "raw.jsonl").open("w", encoding="utf-8") as raw, (root / "bits.txt").open("w", encoding="utf-8") as bits, (root / "samples.csv").open("w", encoding="utf-8", newline="") as csvfile:
        session.headers.update({"Authorization": "Bearer " + secret, "Accept": "application/json"})
        columns = ["index", "timestamp", "bit", "p0", "p1", "confidence", "model", "elapsed_ms", "input_tokens", "output_tokens"]
        if args.salt:
            columns.append("salt")
        if history_enabled:
            columns.extend(["history_before", "history_after"])
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        for index in range(1, args.n + 1):
            stamp = datetime.now(tz).isoformat(timespec="microseconds")
            request_payload = with_history(payload, history) if history_enabled else (with_timestamp(payload, stamp) if args.timestamp else payload)
            request_salt = secrets.token_hex(16) if args.salt else None
            if args.salt:
                request_payload = with_salt(request_payload, request_salt)
            result = call(session, "POST", "/v1/systemone", secret, request_payload)
            result.update({"index": index, "timestamp": stamp})
            if args.timestamp or args.salt or history_enabled or args.one_first:
                result["request"] = request_payload
            if args.one_first:
                result["request_body"] = session.last_request_body
                prepared = json.loads(session.last_request_body)
                if prepared != request_payload or list(prepared["questions"]["bit"]["criteria"]) != criteria_order:
                    raise ValueError("Serialized request body or criteria order mismatch")
            if args.salt:
                result["salt"] = request_salt
            data = result.get("response", {})
            answer = data.get("answers", {}).get("bit", {}) if isinstance(data, dict) else {}
            distribution = answer.get("probabilities", {})
            bit = answer.get("choice")
            valid = (
                result["http_status"] == 200 and answer.get("type") == "choice"
                and bit in counts and set(distribution) == {"0", "1"}
                and all(probability(p) for p in distribution.values())
                and abs(sum(distribution.values()) - 1) < 0.01
                and probability(answer.get("confidence"))
                and distribution[bit] >= max(distribution.values()) - 1e-6
                and isinstance(data.get("model"), str)
            )
            result["valid_bit_answer"] = valid
            next_history = (history if args.history_all else history[1:]) + [int(bit)] if history_enabled and valid else None
            if history_enabled and valid:
                result["history_after"] = next_history
            raw.write(json.dumps(result, ensure_ascii=False) + "\n")
            raw.flush()
            if not valid:
                print(json.dumps({"stopped_at": index, "http_status": result["http_status"], "reason": "HTTP or response validation failure; raw error retained; no replacement draw"}), flush=True)
                break
            usage = data.get("usage", {})
            counts[bit] += 1
            completed += 1
            for name in tokens:
                tokens[name] += usage.get(name, 0)
            elapsed.append(result["elapsed_ms"])
            distribution_key = f"{distribution['0']},{distribution['1']}"
            probabilities_seen[distribution_key] = probabilities_seen.get(distribution_key, 0) + 1
            bits.write(bit + "\n")
            bits.flush()
            sample_row = {"index": index, "timestamp": stamp, "bit": bit, "p0": distribution["0"], "p1": distribution["1"], "confidence": answer["confidence"], "model": data["model"], "elapsed_ms": result["elapsed_ms"], **{k: usage.get(k, 0) for k in tokens}}
            if args.salt:
                sample_row["salt"] = request_salt
            if history_enabled:
                sample_row["history_before"] = "".join(map(str, history))
                sample_row["history_after"] = "".join(map(str, next_history))
            writer.writerow(sample_row)
            csvfile.flush()
            if history_enabled:
                history = next_history
            if index % 20 == 0 or index == args.n:
                print(json.dumps({"completed": index, "zero": counts["0"], "one": counts["1"], "wall_seconds": round(time.perf_counter() - overall_start, 1)}), flush=True)
    metadata.update({
        "finished_at": datetime.now(tz).isoformat(), "completed_n": completed,
        "complete": completed == args.n, "counts": counts, "usage": tokens,
        "final_history": history,
        "probability_pairs_frequency": probabilities_seen,
        "request_latency_ms": elapsed,
        "bits_file_sha256": hashlib.sha256((root / "bits.txt").read_bytes()).hexdigest(),
    })
    (root / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete": metadata["complete"], "n": completed, "counts": counts, "usage": tokens, "probabilities": probabilities_seen, "output_directory": str(root)}), flush=True)
    return 0 if metadata["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
