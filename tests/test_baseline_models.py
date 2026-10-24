import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.model_training.baseline_models import (
    DEFAULT_PROTOCOL, _prior_probability_metrics, _return_ranking,
    score_baselines, verify_inputs,
)


class Phase5BaselineChecks(unittest.TestCase):
    def test_constant_prior_has_no_artificial_ranking(self):
        frame = pd.DataFrame({"session_date": ["2020-01-02"] * 3,
                              "ticker": ["C", "A", "B"],
                              "return_next_20d": [0.3, 0.1, 0.2]})
        result = _return_ranking(frame, [0.1, 0.1, 0.1])
        self.assertIsNone(result["mean_daily_spearman"])
        self.assertIsNone(result["mean_top10_minus_universe"])
        self.assertEqual(result["defined_spearman_dates"], 0)
        self.assertAlmostEqual(_return_ranking(frame, [3, 1, 2])["mean_daily_spearman"], 1)
        metrics = _prior_probability_metrics([0, 1, 2], [1 / 3] * 3)
        self.assertAlmostEqual(metrics["multiclass_brier"], 2 / 3)

    def test_frozen_gate_and_matched_baselines(self):
        frame, _, protocol = verify_inputs()
        self.assertEqual(len(protocol["folds"]), 4)
        results = score_baselines(frame, protocol)
        self.assertEqual(len(results), 16)
        for result in results:
            saved = protocol["folds"][result["fold"] - 1]["tasks"][result["task"]][result["role"]]
            self.assertEqual(result["evaluation_keys_sha256"], saved["evaluation_keys_sha256"])
            self.assertEqual(result["evaluation_rows"], saved["evaluation_rows"])
            self.assertEqual(sum(result["train_class_counts"]), result["train_rows"])
            self.assertAlmostEqual(sum(result["training_class_prior"]), 1)
            if result["task"] == "risk":
                self.assertEqual(result["risk_boundaries"], saved["risk_boundaries"])
            else:
                self.assertEqual(result["momentum_20d_ranking"]["defined_spearman_dates"],
                                 saved["ranking_dates"])
                self.assertIsNone(result["prior_ranking"]["mean_daily_spearman"])

    def test_modified_protocol_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            altered = Path(tmp) / "protocol.json"
            report = json.loads(DEFAULT_PROTOCOL.read_text(encoding="utf-8"))
            report["folds"][0]["tasks"]["risk"]["outer"]["risk_boundaries"][0] = 0.5
            altered.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "protocol checksum"):
                verify_inputs(protocol_path=altered)


if __name__ == "__main__":
    unittest.main()
