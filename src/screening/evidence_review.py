"""Source-bound reviews and honest coverage diagnostics for the public rules.

A review is a recorded research interpretation, not religious approval. Finding
an amount never supplies the separate assertion that all categories are covered.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import re
import csv

from .source_facts import read_facts
from .yasaar import income_rule, business_revenue_rule


def select_annual_revenue(check, annual):
    """Prefer a reported consolidated total over a sales-only candidate.

    This repairs field selection, not the full denominator interpretation. Keep
    the earlier observation so the choice and its effect remain auditable.
    """
    choices = []
    for f in annual['facts']:
        if (f.get('dimensions') or not f.get('period_start')
                or f['period_end'] != annual['report_date'] or f.get('unit') != 'USD'):
            continue
        days = (date.fromisoformat(f['period_end']) - date.fromisoformat(f['period_start'])).days
        if not 330 <= days <= 380 or Decimal(f['value']) <= 0:
            continue
        label = re.sub(r'\s+', ' ', f.get('row_label') or '').strip().casefold()
        if f.get('namespace') == 'us-gaap' and label in {'total revenue', 'total revenues'}:
            choices.append(f)
    unique = {(f['period_start'], f['period_end'], f['value']) for f in choices}
    result = deepcopy(check)
    if len(unique) == 1:
        chosen = choices[0]
        old = result.get('revenue_candidate')
        if old and (old['period_start'], old['period_end']) != (chosen['period_start'], chosen['period_end']):
            result['revenue_selection_issue'] = 'Annual periods differ; original candidate preserved'
            return result
        result['previous_revenue_candidate'] = old
        result['revenue_candidate'] = dict(chosen, value_decimal=chosen['value'],
            source_url=annual['source_url'], source_sha256=annual['source_sha256'],
            accession_number=annual['accession_number'], filing_date=annual['filing_date'],
            available_from_session=annual['available_from_session'],
            source_kind='original_reported_consolidated_total_candidate')
        result['revenue_selection_basis'] = 'Original annual consolidated row explicitly labelled Total revenue or Total revenues'
        result['revenue_amount_changed'] = bool(old and Decimal(old['value_decimal']) != Decimal(chosen['value']))
    elif len(unique) > 1:
        result['revenue_selection_issue'] = 'Conflicting consolidated annual totals require review'
    return result


def coverage_issues(income, business):
    """Distinguish unavailable observations from unfinished category assessment."""
    found = bool(income.get('interest_candidate'))
    combined = [f for f in income.get('recovered_interest_disclosures', [])
                if f.get('classification') in {'combined_or_partial_interest_candidate',
                                              'reported_combined_interest_candidate',
                                              'combined_interest_and_dividends_not_separate_gross_interest'}]
    issues = []
    if not income.get('revenue_candidate'):
        issues.append('annual_revenue_observation_not_found')
    if not found:
        issues.append('interest_combined_with_other_income' if combined else 'separate_gross_interest_observation_not_found')
    if income.get('completeness') != 'complete_reviewed_total':
        issues.append('complete_income_category_review_required')
    if business['status'] == 'needs_review':
        issues.append('business_activity_revenue_review_required')
    return dict(gross_interest_observation_found=found,
                combined_interest_observations_found=bool(combined),
                combined_interest_observations=combined,
                annual_revenue_observation_found=bool(income.get('revenue_candidate')),
                total_revenue_field_corrected=income.get('revenue_amount_changed', False),
                issues=issues)


def _amount(reference, facts, start, end):
    """Resolve exact reviewed original facts, including explicit segment contexts."""
    dimensions = reference.get('dimensions', [])
    candidates = [f for f in facts if f['concept'] == reference['concept']
                  and f.get('namespace') == reference.get('namespace', 'us-gaap')
                  and f['period_start'] == start and f['period_end'] == end
                  and f.get('dimensions', []) == dimensions
                  and (not reference.get('context_id') or f['context_id'] == reference['context_id'])]
    values = {Decimal(f['value']) for f in candidates}
    expected = Decimal(reference['expected_value'])
    if len(values) != 1 or expected not in values or not expected.is_finite() or expected < 0:
        raise ValueError('Reviewed amount is absent, conflicting, negative or different')
    return dict(candidates[0], value=str(expected))


def _interval(amount):
    precision = amount.get('reported_decimals')
    try:
        places = 0 if precision == 'INF' else int(precision)
        if not -30 <= places <= 30:
            raise ValueError('Unreasonable declared precision')
        radius = Decimal(0) if precision == 'INF' else Decimal(10) ** -places / 2
    except (ValueError, TypeError):
        raise ValueError('Reviewed amount has no usable source precision')
    value = Decimal(amount['value'])
    return max(Decimal(0), value-radius), value+radius


def _review_bounds(components, denominator, kind):
    selected = [c for c in components if c['classification'] == 'prohibited'] if kind == 'business' else components
    denominator_lower, denominator_upper = _interval(denominator)
    if denominator_lower <= 0:
        raise ValueError('Revenue precision interval reaches zero')
    intervals = [_interval(c) for c in selected]
    lower = sum((x[0] for x in intervals), Decimal(0)) / denominator_upper
    upper = sum((x[1] for x in intervals), Decimal(0)) / denominator_lower
    return dict(minimum_ratio=str(lower), maximum_ratio=str(upper))


def _precision_status(bounds, limit):
    if Decimal(bounds['minimum_ratio']) > Decimal(limit):
        return 'fails_initial_filter'
    if Decimal(bounds['maximum_ratio']) <= Decimal(limit):
        return 'passes_filter'
    return 'needs_review'


def apply_evidence_review(checks, business, report, content, review, config):
    """Finish income/business checks only through a complete recorded review.

    The registry must supply source-resolvable amounts plus a genuine explicit
    coverage assessment. Neither a found tag nor an unsigned draft can pass.
    """
    if review is None:
        return checks, business
    for key in ['ticker', 'cik', 'accession_number', 'source_url']:
        if review.get(key) != report.get(key):
            raise ValueError('Evidence review belongs to another issuer or filing')
    if (review.get('source_sha256') != report['sha256']
            or hashlib.sha256(content).hexdigest() != report['sha256']):
        raise ValueError('Evidence review original source hash differs')
    if (review.get('period_end') != report['report_date']
            or review.get('available_from_session') != report['available_from_session']
            or report['available_from_session'] > config['as_of_date']):
        raise ValueError('Evidence review period or historical availability differs')
    proposed = review.get('checks', {})
    if not proposed:
        return checks, business
    facts = read_facts(content, report['cik'], include_custom=True, include_dimensions=True)
    checks, business = deepcopy(checks), deepcopy(business)
    for key, rule in [('income', income_rule), ('business', business_revenue_rule)]:
        decision = proposed.get(key)
        if not decision or decision.get('review_state') != 'complete':
            continue
        if (decision.get('coverage_confirmed') is not True
                or decision.get('disjoint_components_confirmed') is not True
                or decision.get('total_revenue_confirmed') is not True
                or (key == 'income' and decision.get('gross_income_confirmed') is not True)
                or not decision.get('coverage_rationale', '').strip()
                or not decision.get('reviewer', '').strip()):
            raise ValueError('A complete decision requires an explicit reasoned source review')
        start, end = review['period_start'], review['period_end']
        if not 330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 380:
            raise ValueError('Reviewed income/business period is not a full annual period')
        denominator = _amount(decision['denominator'], facts, start, end)
        if denominator.get('dimensions') or Decimal(denominator['value']) <= 0:
            raise ValueError('Reviewed denominator must be positive consolidated annual revenue')
        revenue_tags = {'Revenues','SalesRevenueNet','RevenueFromContractWithCustomerExcludingAssessedTax',
                        'RevenueFromContractWithCustomerIncludingAssessedTax'}
        if denominator['concept'] not in revenue_tags:
            raise ValueError('Reviewed denominator is not a supported revenue concept')
        components = []
        identities = set()
        for ref in decision['components']:
            amount = _amount(ref, facts, start, end)
            identity = (amount['namespace'], amount['concept'], amount['context_id'])
            if identity in identities or not ref.get('classification_rationale', '').strip():
                raise ValueError('Repeated or unclassified reviewed amount')
            identities.add(identity)
            kind = ref.get('classification')
            allowed = {'noncompliant_interest', 'noncompliant_other'} if key == 'income' else {'permitted', 'prohibited'}
            if kind not in allowed:
                raise ValueError('Incomplete or incompatible classification in complete review')
            if key == 'income' and kind == 'noncompliant_interest' and any(
                    word in amount['concept'].lower() for word in ['net','expense','cashflow']):
                raise ValueError('Net income, expense or cash receipt cannot stand in for gross earned interest')
            components.append(dict(amount, classification=kind,
                                   classification_rationale=ref['classification_rationale']))
        if not components:
            raise ValueError('No source-resolvable amount; missing income cannot become zero')
        if key == 'business':
            # Whole-revenue coverage prevents a permitted segment from clearing
            # other, unexplained activities. Exact mapping is deliberate here.
            if sum(Decimal(c['value']) for c in components) != Decimal(denominator['value']):
                raise ValueError('Reviewed business activities do not reconcile to all revenue')
            prohibited = [c for c in components if c['classification'] == 'prohibited']
            # Zero is derived from a complete classified revenue partition,
            # never from an absent tag or a keyword search.
            numerator = sum(Decimal(c['value']) for c in prohibited)
            amounts = [dict(value=str(numerator), concept='ReviewedClassifiedProhibitedRevenue')]
        else:
            amounts = components
        result = rule(amounts, denominator, config, complete=True)
        bounds = _review_bounds(components, denominator, key)
        limit = config['noncompliant_income_limit' if key == 'income' else 'prohibited_business_revenue_limit']
        result['status'] = _precision_status(bounds, limit)
        result['review_ratio_bounds'] = bounds
        if result['status'] == 'needs_review':
            result['reason'] = 'Complete reviewed categories, but source rounding spans the five-percent limit'
        result['reviewed_evidence'] = dict(source_sha256=review['source_sha256'],
            accession_number=review['accession_number'], cik=review['cik'],
            source_url=review['source_url'], period_start=start, period_end=end,
            available_from_session=review['available_from_session'],
            reviewer=decision['reviewer'], coverage_rationale=decision['coverage_rationale'],
            coverage_confirmed=True, denominator=denominator, classified_components=components,
            kind=key, domain_approved=False)
        if key == 'income':
            if checks[key]['status'] == 'fails_initial_filter' and result['status'] != 'fails_initial_filter':
                raise ValueError('A passing review contradicts an existing income failure')
            checks[key].update(result)
        else:
            # A draft or a newly reviewed pass must never erase an established
            # independent business failure.
            if business['status'] == 'fails_initial_filter' and result['status'] != 'fails_initial_filter':
                raise ValueError('A passing review contradicts an existing business failure')
            business.update(result)
    return checks, business


def validate_reviewed_result(check, kind, config, cutoff):
    """Independently recompute saved review arithmetic and date safeguards."""
    proof = check['reviewed_evidence']
    if (proof['kind'] != kind or proof['coverage_confirmed'] is not True
            or not proof['reviewer'] or not proof['coverage_rationale']
            or proof['domain_approved'] is not False
            or proof['available_from_session'] > cutoff or proof['period_end'] > cutoff
            or len(proof['source_sha256']) != 64):
        raise ValueError('Incomplete or future review proof')
    start, end = proof['period_start'], proof['period_end']
    components, denominator = proof['classified_components'], proof['denominator']
    if any((c['period_start'], c['period_end']) != (start, end) for c in [denominator] + components):
        raise ValueError('Reviewed amount periods differ')
    if kind == 'business':
        if sum(Decimal(c['value']) for c in components) != Decimal(denominator['value']):
            raise ValueError('Business coverage arithmetic differs')
        amount = sum(Decimal(c['value']) for c in components if c['classification'] == 'prohibited')
        recalculated = business_revenue_rule([dict(value=str(amount))], denominator, config, complete=True)
    else:
        recalculated = income_rule(components, denominator, config, complete=True)
    bounds = _review_bounds(components, denominator, kind)
    limit = config['noncompliant_income_limit' if kind == 'income' else 'prohibited_business_revenue_limit']
    recalculated['status'] = _precision_status(bounds, limit)
    if check.get('review_ratio_bounds') != bounds:
        raise ValueError('Reviewed source precision calculation differs')
    if any(check[k] != recalculated[k] for k in ['status', 'ratio', 'minimum_amount', 'completeness']):
        raise ValueError('Reviewed result arithmetic or decision differs')
    return True


def write_source_gaps(target, records):
    """One practical handoff row per stock; found amounts stay labelled partial."""
    rows = []
    for r in records:
        income, coverage = r['checks']['income'], r['source_coverage']
        revenue = income.get('revenue_candidate') or {}
        interest = income.get('interest_candidate') or {}
        combined = coverage['combined_interest_observations']
        rows.append(dict(ticker=r['ticker'], research_result=r['research_status'],
            annual_revenue_observation_usd=revenue.get('value_decimal',''),
            revenue_amount_corrected=coverage['total_revenue_field_corrected'],
            gross_interest_observation_or_component_usd=interest.get('value_decimal',''),
            gross_interest_is_complete=income.get('completeness')=='complete_reviewed_total',
            combined_interest_amount_found=bool(combined),
            combined_interest_labels='; '.join(sorted({f.get('row_label') or f.get('concept','') for f in combined})),
            income_still_needed=('None for this check' if income['status']=='passes_filter' else
                'Complete classification of interest and other prohibited income with matching total revenue; found amounts alone do not cover every category'),
            business_still_needed=('Original business finding already fails a rule' if r['business']['status']=='fails_initial_filter' else
                'None for this check' if r['business']['status']=='passes_filter' else
                'Reviewed revenue by permitted and prohibited activities; explain ambiguous or combined categories'),
            other_financial_checks_needed='; '.join(k for k in r['missing_or_incomplete_checks']
                if k not in {'income','business_revenue_exposure'}),
            annual_source=revenue.get('source_url') or r['business'].get('source_url',''),
            information_cutoff=r['as_of_date']))
    with (target/'data_gaps.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
