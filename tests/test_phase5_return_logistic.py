import unittest

import numpy as np
import pandas as pd

from src.modeling.phase5_return_logistic import _fit_and_predict


class ReturnLogisticChecks(unittest.TestCase):
    def test_training_only_features_and_probability_order(self):
        x_train = pd.DataFrame({"momentum_20d": [-3, -2, -1, 0, 1, 2, 3, 4, 5],
                                "volatility_20d": [1, 2, 3, 1, 2, 3, 1, 2, 3]})
        y_train = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
        x_eval = pd.DataFrame({"momentum_20d": [0, 2], "volatility_20d": [2, 2]})
        model, probabilities = _fit_and_predict(x_train, y_train, x_eval, 0.1)
        self.assertEqual(probabilities.shape, (2, 3))
        np.testing.assert_allclose(probabilities.sum(axis=1), 1)
        self.assertEqual(model.named_steps["logisticregression"].classes_.tolist(), [0, 1, 2])
        # Evaluation values cannot change the scaler fitted on training rows.
        changed_eval = x_eval.copy()
        changed_eval.loc[1, "momentum_20d"] = 1_000_000
        changed_model, changed_probabilities = _fit_and_predict(x_train, y_train, changed_eval, 0.1)
        np.testing.assert_allclose(model.named_steps["standardscaler"].mean_,
                                   changed_model.named_steps["standardscaler"].mean_)
        np.testing.assert_allclose(probabilities[0], changed_probabilities[0])
        with self.assertRaisesRegex(ValueError, "Non-allowlisted"):
            _fit_and_predict(x_train.assign(relative_return_class=y_train), y_train,
                             x_eval.assign(relative_return_class=[0, 1]), 0.1)


if __name__ == "__main__":
    unittest.main()
