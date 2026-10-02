# API contract status

The existing FastAPI health route is implemented. Model inference, screening and portfolio endpoints are not established by this research task. The Node/Express HalalifyAPI backend needs an agreed, versioned integration contract before deployment.

The research artifact contains ordered feature names, training-fitted preprocessing, return/risk class thresholds and class order. Future inference must reuse these exactly, return model/data/methodology versions and explain missing inputs. Class probabilities must be named by class, never represented as percentage return.

Screening currently has no selected standard. The only truthful status is `needs_review`; missing metrics remain null and portfolio eligibility is false. Proposed endpoint examples in the experiment/dictionary are not implemented APIs or backend approvals.

Final endpoint schemas, authentication, error behavior, calibration, user risk category mapping and prediction cutoff behavior require backend agreement and tests. Historical bar-arrival timestamps were not collected; current research must not claim verified after-close execution timing.
