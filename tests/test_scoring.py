from pathlib import Path
import sys
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from scoring import price_similarity_score, rating_score, sales_scores, total_score


class ScoringTests(unittest.TestCase):
    def test_sales_scores_use_min_max_normalization(self):
        self.assertEqual(sales_scores([100, 200, 300]), [0.0, 50.0, 100.0])

    def test_equal_sales_all_receive_full_score(self):
        self.assertEqual(sales_scores([50, 50]), [100.0, 100.0])

    def test_price_similarity_is_symmetric_around_target(self):
        self.assertEqual(price_similarity_score(150, 150), 100.0)
        self.assertEqual(price_similarity_score(135, 150), 90.0)
        self.assertEqual(price_similarity_score(165, 150), 90.0)
        self.assertEqual(price_similarity_score(120, 150), 80.0)
        self.assertEqual(price_similarity_score(180, 150), 80.0)

    def test_price_score_never_goes_below_zero(self):
        self.assertEqual(price_similarity_score(400, 150), 0.0)

    def test_invalid_price_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            price_similarity_score(-1, 150)
        with self.assertRaises(ValueError):
            price_similarity_score(150, 0)

    def test_rating_and_weighted_total(self):
        self.assertEqual(rating_score(4.5), 90.0)
        self.assertEqual(total_score(100, 90, 80), 92.0)

    def test_every_scoring_function_rejects_non_finite_inputs(self):
        non_finite_values = (float("nan"), float("inf"), float("-inf"))
        for value in non_finite_values:
            with self.subTest(function="sales_scores", value=value):
                with self.assertRaises(ValueError):
                    sales_scores([100, value])
            with self.subTest(function="price_similarity_score.actual", value=value):
                with self.assertRaises(ValueError):
                    price_similarity_score(value, 100)
            with self.subTest(function="price_similarity_score.target", value=value):
                with self.assertRaises(ValueError):
                    price_similarity_score(100, value)
            with self.subTest(function="rating_score.rating", value=value):
                with self.assertRaises(ValueError):
                    rating_score(value)
            with self.subTest(function="rating_score.maximum", value=value):
                with self.assertRaises(ValueError):
                    rating_score(4.5, value)
            for position in range(3):
                scores = [80.0, 90.0, 100.0]
                scores[position] = value
                with self.subTest(function="total_score", position=position, value=value):
                    with self.assertRaises(ValueError):
                        total_score(*scores)


if __name__ == "__main__":
    unittest.main()
