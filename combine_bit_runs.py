"""Verify and concatenate completed Jev runs without modifying source files."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import statistics

from analyze_bits import analyze, parse_bits


def read_run(directory):
    directory = directory.resolve()
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    raw = [json.loads(line) for line in (directory / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    bit_bytes = (directory / "bits.txt").read_bytes()
    bits = parse_bits(bit_bytes.decode("utf-8"))
    with (directory / "samples.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not meta.get("complete") or not (len(bits) == len(raw) == len(rows) == meta["planned_n"] == meta["completed_n"]):
        raise ValueError(f"Incomplete or inconsistent run: {directory.name}")
    if meta["bits_file_sha256"] != hashlib.sha256(bit_bytes).hexdigest():
        raise ValueError(f"Source bit-file hash mismatch: {directory.name}")
    for index, (bit, response, row) in enumerate(zip(bits, raw, rows), 1):
        answer = response["response"]["answers"]["bit"]
        if not (response["index"] == index == int(row["index"]) and response["http_status"] == 200 and response["valid_bit_answer"] and str(bit) == answer["choice"] == row["bit"]):
            raise ValueError(f"Raw/CSV/bit mismatch: {directory.name}, row {index}")
        if response["response"]["model"] != row["model"]:
            raise ValueError(f"Model mismatch at row {index}")
        for name, field in [("p0", "0"), ("p1", "1")]:
            if float(row[name]) != answer["probabilities"][field]:
                raise ValueError(f"Probability mismatch at row {index}")
    return directory, meta, request, raw, bits, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="Source directories in desired sequence order")
    parser.add_argument("--expected-n", type=int)
    args = parser.parse_args()
    if len({path.resolve() for path in args.runs}) != len(args.runs):
        parser.error("The same source run must not be counted twice")
    sources = [read_run(path) for path in args.runs]
    first_request = sources[0][2]
    first_order = list(first_request["questions"]["bit"]["criteria"])
    for directory, _, request, _, _, _ in sources:
        if request != first_request or list(request["questions"]["bit"]["criteria"]) != first_order:
            raise ValueError(f"Request or criteria order differs: {directory.name}")
    all_bits = [bit for _, _, _, _, bits, _ in sources for bit in bits]
    if args.expected_n is not None and len(all_bits) != args.expected_n:
        parser.error(f"Expected {args.expected_n} bits, got {len(all_bits)}")
    stamp = datetime.now(timezone(timedelta(hours=8)))
    output = Path(__file__).resolve().parent / "results" / ("random-bits-combined-" + stamp.strftime("%Y%m%d-%H%M%S-%f"))
    output.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save("request.json", first_request)
    (output / "bits.txt").write_text("".join(f"{bit}\n" for bit in all_bits), encoding="utf-8")
    batch_statistics = []
    manifests = []
    all_responses = []
    index = 0
    with (output / "raw.jsonl").open("w", encoding="utf-8") as raw_out, (output / "samples.csv").open("w", encoding="utf-8", newline="") as csv_out:
        writer = csv.DictWriter(csv_out, fieldnames=["combined_index", "source_run", "source_index", "timestamp", "bit", "p0", "p1", "confidence", "model", "elapsed_ms", "input_tokens", "output_tokens"])
        writer.writeheader()
        for directory, meta, _, raw, bits, rows in sources:
            start_index = index + 1
            for record, row in zip(raw, rows):
                index += 1
                raw_out.write(json.dumps({**record, "combined_index": index, "source_run": directory.name}, ensure_ascii=False) + "\n")
                source_index = row["index"]
                writer.writerow({**{k: v for k, v in row.items() if k != "index"}, "source_index": source_index, "combined_index": index, "source_run": directory.name})
            all_responses.extend(raw)
            batch_statistics.append({"source_directory": str(directory), **analyze(bits)})
            manifests.append({
                "source_directory": str(directory), "n": len(bits), "combined_range": [start_index, index],
                "started_at": meta["started_at"], "finished_at": meta["finished_at"],
                "sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in ["bits.txt", "raw.jsonl", "samples.csv", "metadata.json", "request.json"]},
            })
    result = analyze(all_bits)
    result["source_sha256"] = hashlib.sha256((output / "bits.txt").read_bytes()).hexdigest()
    result["batch_sizes"] = [len(source[4]) for source in sources]
    result["extension_note"] = "The later batch was requested after observing the first. Report batch diagnostics separately; pooled fixed-n p-values are descriptive, not a claim of full preregistration. Sequence diagnostics concatenate across session boundaries."
    save("statistics.json", result)
    save("batch_statistics.json", batch_statistics)
    p0 = [r["response"]["answers"]["bit"]["probabilities"]["0"] for r in all_responses]
    summary = {
        "n": len(all_bits), "zeros": result["zeros"], "ones": result["ones"],
        "p0_range": [min(p0), max(p0)], "p0_mean": statistics.mean(p0),
        "median_request_ms": statistics.median(r["elapsed_ms"] for r in all_responses),
        "models": sorted({r["response"]["model"] for r in all_responses}),
        "usage": {name: sum(r["response"]["usage"][name] for r in all_responses) for name in ["input_tokens", "output_tokens"]},
    }
    save("manifest.json", {"created_at": stamp.isoformat(), "sources": manifests, "summary": summary, "bit_file_sha256": result["source_sha256"]})
    print(json.dumps({"output_directory": str(output), "summary": summary, "batches": [{"n": b["n"], "zeros": b["zeros"], "ones": b["ones"], "p_two_sided": b["primary_frequency_test"]["p_two_sided"]} for b in batch_statistics]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
