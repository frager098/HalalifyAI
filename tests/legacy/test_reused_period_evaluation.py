import unittest

import pandas as pd

from src.legacy.model_experiments.run_reused_test_evaluation import cohort_masks, frozen_protocol


class FinalEvaluationChecks(unittest.TestCase):
    def test_training_labels_cannot_reach_test_start(self):
        frame = pd.DataFrame([
            {"ticker": "AAA", "session_date": "2024-06-01", "target_window_end": "2024-06-29", "dataset_split": "train"},
            {"ticker": "AAA", "session_date": "2024-06-20", "target_window_end": "2024-07-10", "dataset_split": "purged"},
            {"ticker": "AAA", "session_date": "2024-07-01", "target_window_end": "2024-07-30", "dataset_split": "test"},
            {"ticker": "AAA", "session_date": "2024-07-30", "target_window_end": None, "dataset_split": "unlabeled"},
        ])
        frame["risk_volatility_next_20d"] = [0.2, 0.3, 0.4, None]
        frame["return_next_20d"] = [0.01, 0.02, 0.03, None]
        factors = pd.DataFrame({"momentum_20d": [0.1, 0.2, 0.3, 0.4]})
        train, test = cohort_masks(frame, factors, "2024-07-01", ["momentum_20d"])
        self.assertEqual(train.tolist(), [True, False, False, False])
        self.assertEqual(test.tolist(), [False, False, True, False])

    def test_protocol_selects_only_development_supported_inputs(self):
        protocol = frozen_protocol()
        self.assertEqual(protocol["risk_model"]["name"], "ridge")
        self.assertEqual(protocol["return_choice"], "momentum_20d")
        self.assertNotIn("cash_to_assets", protocol["risk_model"]["feature_columns"])
        self.assertEqual(protocol["status"], "predeclared_reused_test_check_not_blind")


if __name__ == "__main__":
    unittest.main()
