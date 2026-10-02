# Experiment log

## 2026-10-02 — provisional core readiness

Starting integration reference: published develop `255436b`. Dependencies: published reconciliation `741f60c`, context update `c720d57`, BAC identity verification `5640424`. Their changes were combined in an isolated feature branch; no develop merge or peer approval is claimed.

Inputs: saved split/all SIP prices (`alpaca_sip_20261001T192530002523Z`), action ledger (`20261001T193109154154Z`), new raw SIP reference (`raw_reference_20261002`), and BAC-normalized financial candidates (`bac_identity_20261002`). Original provider pages are preserved. Reports record SHA-256 values. The raw reference was downloaded with the same 2016–2025 request scope and asof symbol mapping. Per-page timestamps were not captured by the original raw-reference run; the new collector captures them for subsequent runs.

Calendar: XNYS, exchange-calendars 4.11.2, 2,514 sessions. Universe: proposed US50_V1_1 with SPY separate. Features: core_v1, ordered 16 predictors. Targets: core_20d_readiness_v1, future 20 complete sessions, training-only linear terciles. Dataset contains provisional US_symbol instrument identifiers, not a certified historical security master.

127,501 input market rows; share-basis and saved split/dividend reconciliation checked within rounding tolerance. Five spin-off transitions remain unsupported. 118,643 usable company rows after window/action/target/boundary exclusions: 58,157 train; 24,150 validation; 36,336 test. Test features/labels were built, but model test metrics were not inspected.

Twenty-two train/validation fits used the registered grid and seed 42. Selected return LR C=1 and risk RF depth=6/minimum leaf=20. Reports contain comparisons, baselines, fitted thresholds, model checksums and input ordering. Models are uncalibrated initial-training artifacts, not final deployment models. Per-fit wall time was not captured; do not infer it.

Verification: 35 tests passed in a new environment, dependency check passed, rebuilt dataset matched exactly, selected-model validation predictions reproduced. Full candidate grid rerun, teammate reproduction and sign-off remain outstanding. See [evaluation_report.md](evaluation_report.md).

Screening decision: user replied “not decided” for standard/edition. All 50 handoff packs preserve candidates; approved amounts remain null and portfolio eligibility false. No standard, income evidence or issuer debt mapping was fabricated.
