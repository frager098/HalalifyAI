# Data investigation tools

These tools compare additional sources. They are not required by the normal
price research pipeline, and their candidate values are not automatically
accepted as historical financial facts.

- `python -m src.data.research.collect_external_candidates --out data/raw/NEW_CANDIDATE_VERSION`
- `python -m src.data.research.review_kaggle_financials --help`

Run a collection command only when a fresh provider investigation is needed.
Existing raw inputs and earlier results remain available.
