import unittest

from src.modeling.phase5_risk_review import _class_metrics


class RiskReviewChecks(unittest.TestCase):
    def test_high_to_low_and_class_order(self):
        # Rows/columns use Low, Medium, High (0, 1, 2).
        result = _class_metrics([0, 1, 2, 2], [0, 1, 0, 1])
        self.assertEqual(result["high_predicted_low_count"], 1)
        self.assertAlmostEqual(result["high_predicted_low_rate_among_high"], 0.5)
        self.assertEqual(result["confusion_matrix"], [[1, 0, 0], [0, 1, 0], [1, 1, 0]])
        self.assertEqual(result["per_class"]["High"]["support"], 2)
        self.assertAlmostEqual(result["ordinal_mae"], 0.75)


if __name__ == "__main__":
    unittest.main()
