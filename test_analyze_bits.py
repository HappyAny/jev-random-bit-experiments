import math
import unittest

from analyze_bits import analyze, binomial_fair_test, parse_bits


class BitDiagnosticsTests(unittest.TestCase):
    def test_known_exact_binomial_probabilities(self):
        self.assertEqual(binomial_fair_test(0, 10)["p_two_sided"], 2 / 1024)
        self.assertEqual(binomial_fair_test(10, 10)["p_two_sided"], 2 / 1024)
        self.assertEqual(binomial_fair_test(5, 10)["p_two_sided"], 1)
        self.assertEqual(binomial_fair_test(6, 10)["p_two_sided"], 772 / 1024)

    def test_constant_sequence(self):
        result = analyze([1] * 200)
        self.assertEqual(result["ones"], 200)
        self.assertEqual(result["runs"]["observed_runs"], 1)
        self.assertEqual(result["runs"]["longest_identical_run"], 200)
        self.assertIsNone(result["lag1_pearson_correlation"])
        self.assertIsNone(result["runs"]["p_two_sided_normal_approx"])
        self.assertAlmostEqual(result["primary_frequency_test"]["log10_p_two_sided"], -199 * math.log10(2))

    def test_alternating_sequence_passes_balance_but_has_pattern(self):
        result = analyze([0, 1] * 50)
        self.assertEqual(result["one_fraction"], 0.5)
        self.assertEqual(result["primary_frequency_test"]["p_two_sided"], 1)
        self.assertEqual(result["runs"]["observed_runs"], 100)
        self.assertEqual(result["lag1_pearson_correlation"], -1)
        self.assertLess(result["runs"]["p_two_sided_normal_approx"], 1e-10)
        self.assertEqual(sum(result["transition_counts"].values()), 99)

    def test_parser_and_minimum_sample(self):
        self.assertEqual(parse_bits("0\n1 1\t0"), [0, 1, 1, 0])
        with self.assertRaises(ValueError):
            parse_bits("0102")
        with self.assertRaises(ValueError):
            parse_bits("  \n")
        result = analyze([0])
        self.assertEqual(result["primary_frequency_test"]["p_two_sided"], 1)
        self.assertIsNone(result["lag1_pearson_correlation"])


if __name__ == "__main__":
    unittest.main()
