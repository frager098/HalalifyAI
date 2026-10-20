from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.screening.verify_results import validate_results

ROOT = Path(__file__).resolve().parents[1]


def reports():
    result = json.loads((ROOT/'reports/screening/ftse_yasaar_2025/results.json').read_text())
    universe = json.loads((ROOT/'configs/screening_universe.json').read_text())['company_tickers']
    return result, universe


def test_saved_report_reconciles_and_has_no_unsafe_eligibility():
    result, universe = reports()
    assert validate_results(result, universe)['unsafe_eligibility_flags'] is False


def test_unresolved_stock_cannot_be_changed_to_eligible():
    result, universe = reports()
    broken = deepcopy(result)
    broken['companies'][0]['portfolio_eligible'] = True
    with pytest.raises(ValueError, match='eligibility'):
        validate_results(broken, universe)
