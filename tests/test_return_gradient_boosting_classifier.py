import unittest

import numpy as np
import pandas as pd

from src.model_training.return_gradient_boosting_classifier import fit_predict


class ReturnBoostedTreeChecks(unittest.TestCase):
    def test_only_allowlisted_inputs_and_fixed_classes(self):
        x_train = pd.DataFrame({"momentum_20d": np.arange(30, dtype=float) / 30,
                                "volatility_20d": np.tile([0.1, 0.2, 0.3], 10)})
        y_train = np.tile([0, 1, 2], 10)
        x_eval = x_train.iloc[:3].copy()
        fixed = {"max_iter": 100, "learning_rate": 0.1,
                 "early_stopping": False, "random_state": 42}
        probabilities = fit_predict(x_train, y_train, x_eval, 15, fixed)
        self.assertEqual(probabilities.shape, (3, 3))
        np.testing.assert_allclose(probabilities.sum(axis=1), 1)
        with self.assertRaisesRegex(ValueError, "Non-allowlisted"):
            fit_predict(x_train.assign(return_next_20d=y_train), y_train,
                        x_eval.assign(return_next_20d=[0, 1, 2]), 15, fixed)


if __name__ == "__main__":
    unittest.main()
