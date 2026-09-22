"""Offline diagnostics of a text file containing only 0, 1 and whitespace."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re


def parse_bits(text):
    if re.search(r"[^01\s]", text):
        raise ValueError("The file must contain only 0, 1 and whitespace")
    bits = [int(c) for c in text if c in "01"]
    if not bits:
        raise ValueError("The file contains no bits")
    return bits


def binomial_fair_test(ones, n):
    """Exact two-sided fair-coin binomial test, symmetric at p=0.5."""
    tail_numerator = sum(math.comb(n, i) for i in range(min(ones, n - ones) + 1))
    numerator = min(1 << n, 2 * tail_numerator)
    return {
        "null": "The bits are iid Bernoulli(0.5)",
        "p_two_sided": numerator / (1 << n),
        "log10_p_two_sided": math.log10(numerator) - n * math.log10(2),
        "note": "A small p-value is evidence against the fair-iid null; a large value does not establish randomness.",
    }


def analyze(bits):
    if not bits or any(type(b) is not int or b not in (0, 1) for b in bits):
        raise ValueError("Expected a nonempty sequence of integer bits")
    n = len(bits)
    ones = sum(bits)
    zeros = n - ones
    fraction = ones / n
    z95 = 1.959963984540054
    denominator = 1 + z95 * z95 / n
    center = (fraction + z95 * z95 / (2 * n)) / denominator
    margin = z95 * math.sqrt(fraction * (1 - fraction) / n + z95 * z95 / (4 * n * n)) / denominator
    runs = 1
    longest = current = 1
    for a, b in zip(bits, bits[1:]):
        if a == b:
            current += 1
        else:
            runs += 1
            current = 1
        longest = max(longest, current)
    run_result = {"observed_runs": runs, "longest_identical_run": longest}
    if zeros >= 10 and ones >= 10:
        expected = 1 + 2 * zeros * ones / n
        variance = 2 * zeros * ones * (2 * zeros * ones - n) / (n * n * (n - 1))
        z = (runs - expected) / math.sqrt(variance)
        run_result.update({"expected_runs_given_counts": expected, "z_no_continuity_correction": z, "p_two_sided_normal_approx": math.erfc(abs(z) / math.sqrt(2)), "note": "Exploratory conditional runs test; normal approximation, not a randomness certification."})
    else:
        run_result.update({"p_two_sided_normal_approx": None, "note": "Normal approximation omitted: fewer than 10 observations of at least one symbol."})
    transitions = Counter(f"{a}{b}" for a, b in zip(bits, bits[1:]))
    lag1 = None
    if n >= 3:
        x, y = bits[:-1], bits[1:]
        count = n - 1
        numerator = count * sum(a * b for a, b in zip(x, y)) - sum(x) * sum(y)
        scale = (count * sum(a * a for a in x) - sum(x) ** 2) * (count * sum(b * b for b in y) - sum(y) ** 2)
        if scale > 0:
            lag1 = numerator / math.sqrt(scale)
    return {
        "n": n, "zeros": zeros, "ones": ones,
        "zero_fraction": zeros / n, "one_fraction": fraction,
        "one_probability_wilson_95_if_iid": [max(0.0, center - margin), min(1.0, center + margin)],
        "primary_frequency_test": binomial_fair_test(ones, n),
        "runs": run_result, "lag1_pearson_correlation": lag1,
        "lag1_note": "Descriptive correlation of adjacent pairs; null if either shifted sequence has zero variance or there are fewer than 3 bits.",
        "transition_counts": {key: transitions[key] for key in ("00", "01", "10", "11")},
        "blocks_of_50": [{"start": start + 1, "n": len(bits[start:start + 50]), "ones": sum(bits[start:start + 50]), "one_fraction": sum(bits[start:start + 50]) / len(bits[start:start + 50])} for start in range(0, n, 50)],
        "interpretation_boundary": "Finite output tests can detect particular biases or patterns. Passing them cannot prove physical randomness, unpredictability or cryptographic security; 010101 also has a 50/50 proportion.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bits_file", type=Path)
    parser.add_argument("--json", type=Path, help="Optionally save results in a NEW JSON file")
    args = parser.parse_args()
    try:
        bits = parse_bits(args.bits_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = analyze(bits)
    result["source_file"] = str(args.bits_file.resolve())
    result["source_sha256"] = hashlib.sha256(args.bits_file.read_bytes()).hexdigest()
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        with args.json.open("x", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
