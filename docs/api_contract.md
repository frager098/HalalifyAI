# API contract status

The existing FastAPI service exposes GET / and GET /health. This task supplies a batch screening command and versioned report schema; it does not add a live screening endpoint or claim backend/dashboard integration.

Consumers of the batch result must retain profile ID, evidence cutoff, source dates, research_status, failed_checks, missing_or_incomplete_checks and portfolio_eligible. A missing verdict or needs_review must never become an eligible stock. Only a complete pass with the separate approval state can become portfolio eligible. All 50 flags are false in the current snapshot.

A live/backend contract remains to be agreed and tested with HalalifyAPI. Display the 2025-12-31 cutoff prominently; do not show the historical batch as a current October 2026 decision.
