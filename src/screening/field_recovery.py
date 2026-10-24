"""Recover source-backed amounts without filling absent disclosures with zero."""
from decimal import Decimal, InvalidOperation
import json

from .yasaar import minimum_check


def recover_reviewed_debt(checks, financial, mappings, source_content, config):
    """Use a reviewed source footnote to remove leases from mixed debt.

    Each mapping binds issuer, accession, file hash, exact original narrative and
    the mixed-debt concepts. It cannot authorize arbitrary segment aggregation.
    """
    from lxml import html
    import hashlib
    text=None
    for mapping in mappings:
        if mapping['ticker'] != financial['ticker']:
            continue
        if any(mapping[key] != financial[key] for key in ['cik','accession_number','source_sha256','report_date']):
            raise ValueError('Reviewed debt source does not match financial filing')
        if hashlib.sha256(source_content).hexdigest() != mapping['source_sha256']:
            raise ValueError('Reviewed debt original file hash mismatch')
        if text is None:
            text=' '.join(' '.join(html.fromstring(source_content).itertext()).split())
        if mapping['expected_narrative'] not in text:
            raise ValueError('Reviewed lease liability footnote changed')
        if mapping.get('kind')=='source_bound_pure_borrowing_floor':
            if mapping['concept']!='ShortTermBorrowings':
                raise ValueError('Pure borrowing floor requires the reviewed standard borrowing concept')
            dimensions=tuple(sorted((d['axis'],d['member']) for d in mapping['dimensions']))
            facts=[f for f in financial['facts'] if f['namespace']=='us-gaap']
            component=reconcile_amount(facts,mapping['concept'],financial['report_date'],dimensions)
            if not component or Decimal(component['value'])!=Decimal(mapping['expected_value']):
                raise ValueError('Reviewed borrowing component missing or changed')
            component.update(source_url=financial['source_url'],source_sha256=mapping['source_sha256'],
                accession_number=mapping['accession_number'],evidence_note=mapping['interpretation'])
            previous=checks['debt'].get('minimum_amount')
            if previous is None or Decimal(component['value'])>Decimal(previous):
                checks['debt']=minimum_check([component],checks['assets'],config['debt_assets_limit'])
            continue
        facts=[f for f in financial['facts'] if f['namespace']=='us-gaap']
        parts=[reconcile_amount(facts, tag, financial['report_date']) for tag in mapping['mixed_debt_concepts']]
        if not all(parts):
            raise ValueError('Reviewed mixed-debt carrying amounts missing or conflicting')
        lease=Decimal(mapping['finance_lease_liability_usd'])
        if not lease.is_finite() or lease < 0:
            raise ValueError('Invalid reviewed finance-lease liability')
        value=sum(Decimal(p['value']) for p in parts)-lease
        if value < 0:
            raise ValueError('Lease liability exceeds mixed debt')
        component=dict(value=str(value),concept='SourceReviewedDebtLessFinanceLeases',
            reported_components=parts,finance_lease_liability_subtracted=str(lease),
            source_url=financial['source_url'],source_sha256=mapping['source_sha256'],
            accession_number=mapping['accession_number'],evidence_note=mapping['interpretation'])
        previous=checks['debt'].get('minimum_amount')
        if previous is None or value > Decimal(previous):
            checks['debt']=minimum_check([component],checks['assets'],config['debt_assets_limit'])
    return checks


def dimensions_key(dimensions):
    return tuple(sorted((d['axis'],d['member']) for d in dimensions))


def reconcile_amount(facts, concept, end, dimensions=()):
    """Reconcile repeated XBRL values using their declared rounding intervals.

    A precise note amount and its rounded narrative representation may agree.
    Disjoint intervals, missing precision on differing values or mixed contexts
    remain unresolved. This does not assert whole-category completeness.
    """
    rows=[f for f in facts if f['concept']==concept and f['period_end']==end
          and not f['period_start'] and dimensions_key(f.get('dimensions',[]))==tuple(dimensions)]
    if not rows:return None
    intervals=[]
    for row in rows:
        value=Decimal(row['value'])
        if not value.is_finite() or value<0:return None
        precision=row.get('reported_decimals')
        try:
            radius=(Decimal(0) if precision=='INF' else Decimal(10)**(-int(precision))/2)
        except (ValueError,TypeError,InvalidOperation):
            if len({Decimal(f['value']) for f in rows})>1:return None
            radius=Decimal(0)
        intervals.append((max(Decimal(0),value-radius),value+radius,row))
    lower=max(v[0] for v in intervals);upper=min(v[1] for v in intervals)
    if lower>upper:return None
    chosen=min(intervals,key=lambda v:v[1]-v[0])[2]
    value=Decimal(chosen['value'])
    if not lower<=value<=upper:return None
    return dict(value=str(value),lower_bound=str(lower),upper_bound=str(upper),concept=concept,
        period_end=end,context_ids=sorted({r['context_id'] for r in rows}),
        dimensions=chosen.get('dimensions',[]),row_labels=sorted({r['row_label'] for r in rows if r.get('row_label')}),
        reported_values=sorted({r['value'] for r in rows}),
        rounding_reconciled=len({Decimal(r['value']) for r in rows})>1)


def greatest(options):
    return max((x for x in options if x),key=lambda x:Decimal(x['value']),default=None)


def recovered_balance(facts, end, checks, config):
    """Improve lower bounds only. Never claim completeness from extra tags."""
    facts=[f for f in facts if f.get('namespace')=='us-gaap' or 'fasb.org/us-gaap/' in f.get('namespace','')]
    pick=lambda tag:reconcile_amount(facts,tag,end)
    assets=checks['assets']
    new_debt=[pick(tag) for tag in ['DebtInstrumentCarryingAmount','NotesPayable','LongTermDebt',
        'LongTermDebtNoncurrent','LongTermDebtCurrent','DebtCurrent','ShortTermBorrowings']]
    # Only instrument/type breakdowns of debt, never business segments, fair-value
    # measurements or finance-lease categories. A single component is a floor;
    # it is not added to possibly overlapping totals.
    debt_tags={'DebtInstrumentCarryingAmount','NotesPayable','LongTermDebt','LongTermDebtNoncurrent','LongTermDebtCurrent'}
    axes={'us-gaap:DebtInstrumentAxis','us-gaap:LongtermDebtTypeAxis','us-gaap:ShortTermDebtTypeAxis'}
    for fact in facts:
        dims=fact.get('dimensions',[])
        if not dims or fact['concept'] not in debt_tags:continue
        if not all(d['axis'] in axes for d in dims):continue
        if any('lease' in d['member'].lower() for d in dims):continue
        new_debt.append(reconcile_amount(facts,fact['concept'],end,dimensions_key(dims)))
    previous=checks['debt'].get('components',[])
    if previous:
        new_debt.append(dict(value=str(sum(Decimal(c['value']) for c in previous)),
            concept='PreviouslyEvidencedDebtFloor',components=previous))
    chosen=greatest(new_debt)
    if chosen:checks['debt']=minimum_check([chosen],assets,config['debt_assets_limit'])

    receivables=greatest([pick(tag) for tag in ['AccountsReceivableNetCurrent','ReceivablesNetCurrent',
        'AccountsNotesAndLoansReceivableNetCurrent','AccountsReceivableNet','AccountsAndNotesReceivableNet',
        'TradeReceivablesHeldForSaleAmount','ReceivablesFromCustomers']])
    cash=next((pick(tag) for tag in ['CashAndCashEquivalentsAtCarryingValue','Cash'] if pick(tag)),None)
    if receivables and cash:
        recovered=minimum_check([cash,receivables],assets,config['receivables_cash_assets_limit'])
        prior=checks['receivables_and_cash'].get('minimum_amount')
        if prior is None or Decimal(recovered['minimum_amount'])>Decimal(prior):
            checks['receivables_and_cash']=recovered

    # Standard consolidated debt-securities balances are interest-bearing floors.
    # Cash is NOT added: some securities may already be classified as cash.
    securities=greatest([pick(tag) for tag in ['AvailableForSaleSecuritiesDebtSecurities',
        'DebtSecuritiesAvailableForSaleExcludingAccruedInterest','DebtSecurities',
        'TradingSecuritiesDebt','HeldToMaturitySecurities']])
    previous=checks['cash_and_interest_items'].get('components',[])
    options=[securities]
    if previous:options.append(dict(value=str(sum(Decimal(c['value']) for c in previous)),
        concept='PreviouslyEvidencedCashItemsFloor',components=previous))
    # AAPL reports a whole Level-2 debt-securities subtotal and the exact part
    # allocated to cash equivalents in the same classification table. Subtract
    # that overlap before adding total cash; never add cash and securities blindly.
    level2=(('us-gaap:FairValueByFairValueHierarchyLevelAxis','us-gaap:FairValueInputsLevel2Member'),)
    if config.get('recover_apple_classification_table') is True:
        debt= reconcile_amount(facts,'AvailableForSaleSecuritiesDebtSecurities',end,level2)
        overlap=reconcile_amount(facts,'CashAndCashEquivalentsAtCarryingValue',end,level2)
        if debt and overlap and cash and Decimal(debt['value'])>=Decimal(overlap['value']):
            value=Decimal(cash['value'])+Decimal(debt['value'])-Decimal(overlap['value'])
            options.append(dict(value=str(value),concept='CashPlusDebtSecuritiesLessIncludedCash',
                cash=cash,debt_securities=debt,included_cash_subtracted=overlap,
                basis='Reviewed source table subtotal and cash-allocation column, without double counting'))
    selected=greatest(options)
    if selected:checks['cash_and_interest_items']=minimum_check([selected],assets,config['cash_items_assets_limit'])
    return checks


GROSS_INTEREST_TAGS={'InterestIncomeNonOperating','InvestmentIncomeInterest','InterestIncomeOperating','InterestIncomeOther'}


def income_inventory(annual):
    """Keep net, combined and label-only disclosures distinct from gross totals."""
    out=[];seen=set()
    for fact in annual['facts']:
        tag=fact['concept'];label=(fact.get('row_label') or '').lower()
        if fact.get('dimensions') or not fact['period_start'] or fact['period_end']!=annual['report_date']:continue
        if any(word in tag.lower() for word in ['tax','beforeincome','noncontrollinginterest','minorityinterest','ownershipinterest']):continue
        kind=None
        if tag in GROSS_INTEREST_TAGS:kind='reported_gross_interest_candidate'
        elif 'interest' in tag.lower() and 'net' in tag.lower():kind='net_interest_not_gross'
        elif 'interest' in tag.lower() and ('income' in tag.lower() or 'dividend' in tag.lower()):
            kind='combined_or_partial_interest_candidate'
        elif label.startswith('interest income'):
            kind='reported_label_requires_tag_and_period_review'
        if not kind:continue
        key=(tag,fact['value'],fact['period_start'],fact['period_end'])
        if key in seen:continue
        seen.add(key);out.append(dict(fact,classification=kind))
    return out


def recover_income_check(check, annual, mappings):
    """Recover gross-interest candidates, not a complete prohibited-income total."""
    candidates=income_inventory(annual)
    for mapping in mappings:
        if mapping['ticker']!=annual['ticker']:continue
        if (mapping['cik']!=annual['cik'] or mapping['accession_number']!=annual['accession_number']
                or mapping['source_sha256']!=annual['source_sha256']):
            raise ValueError('Manual source review does not match annual filing')
        row=next((r for r in annual['table_rows'] if r['row_ordinal']==mapping['row_ordinal']),None)
        if not row or row['cells']!=mapping['expected_cells']:
            raise ValueError('Reviewed interest-income table changed')
        candidates.append(dict(mapping,concept='SourceReviewedAnnualTable',value=mapping['value_decimal'],
            dimensions=[],row_label=mapping['reported_label'],context_id='original-table-row-'+str(mapping['row_ordinal'])))
    exact=[f for f in candidates if f['classification']=='reported_gross_interest_candidate'
           and Decimal(f['value'])>=0 and f['period_end']==annual['report_date']]
    revenue=check.get('revenue_candidate')
    if revenue:
        exact=[f for f in exact if f['period_start']==revenue['period_start']]
    # Distinct interest components are not summed blindly. Choose the largest
    # reported component as an additional candidate; full income is still unknown.
    best=greatest(exact)
    if best and not check.get('interest_candidate'):
        check['interest_candidate']=dict(best,value_decimal=best['value'],source_url=annual['source_url'],
            source_sha256=annual['source_sha256'],accession_number=annual['accession_number'],
            available_from_session=annual['available_from_session'],
            source_kind='source_reviewed_original_report_candidate')
    check['recovered_interest_disclosures']=candidates
    # Candidate recovery must not erase an independently completed source review.
    if check.get('completeness') != 'complete_reviewed_total':
        check['reason']='Amounts recovered; complete prohibited-income and matching total-revenue review is not yet recorded'
        check['status']='needs_review'
    return check
