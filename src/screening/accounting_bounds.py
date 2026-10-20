"""Clear a carrying-amount ceiling when a source-backed maximum is below it.

These proofs do not estimate missing amounts or clear business/income screens.
Only consolidated, same-period standard USD observations enter the proof.
"""
from copy import deepcopy
from decimal import Decimal
from .field_recovery import reconcile_amount


def standard(facts):
    return [f for f in facts if f.get('unit')=='USD' and (f.get('namespace')=='us-gaap'
            or 'fasb.org/us-gaap/' in f.get('namespace',''))]


def bounded_amount(facts, tag, end):
    rows=[f for f in facts if f['concept']==tag and f['period_end']==end
          and not f['period_start'] and not f.get('dimensions')]
    for row in rows:
        precision=row.get('reported_decimals')
        if precision!='INF':
            try:int(precision)
            except (ValueError,TypeError):return None
    return reconcile_amount(rows,tag,end)


def financial_asset_envelope(facts, end):
    """All cash/receivables/interest assets fit inside remaining recognized assets.

    Subtract only disjoint nonfinancial classes, using their lower precision
    bounds. Alternative disclosures within one class are NEVER added together.
    The numerator uses assets' upper bound and the denominator its lower bound.
    """
    facts=standard(facts)
    pick=lambda tag:bounded_amount(facts,tag,end)
    assets=pick('Assets')
    if not assets or Decimal(assets['lower_bound'])<=0:return None
    groups=[]
    ppe=[pick(t) for t in ['PropertyPlantAndEquipmentNet',
        'PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization']]
    ppe=[p for p in ppe if p]
    if ppe:groups.append(dict(category='property_and_equipment',facts=[max(ppe,key=lambda p:Decimal(p['lower_bound']))]))
    inventory=pick('InventoryNet')
    if inventory:groups.append(dict(category='inventory',facts=[inventory]))
    goodwill=pick('Goodwill')
    intangible=[pick(t) for t in ['IntangibleAssetsNetExcludingGoodwill','FiniteLivedIntangibleAssetsNet']]
    intangible=[p for p in intangible if p]
    separate=([goodwill] if goodwill else [])
    if intangible:separate.append(max(intangible,key=lambda p:Decimal(p['lower_bound'])))
    alternatives=[separate] if separate else []
    combined=pick('GoodwillAndIntangibleAssetsNet')
    if combined:alternatives.append([combined])
    if alternatives:
        groups.append(dict(category='goodwill_and_other_intangibles',facts=max(alternatives,
            key=lambda ps:sum(Decimal(p['lower_bound']) for p in ps))))
    if not groups:return None
    removed=sum(Decimal(f['lower_bound']) for g in groups for f in g['facts'])
    upper=Decimal(assets['upper_bound'])-removed
    if upper<0:
        return dict(status='conflicting_asset_classes_no_proof',assets=assets,nonfinancial_groups=groups)
    return dict(kind='remaining_recognized_assets',status='source_bound',
        numerator_upper=str(upper),denominator_lower=assets['lower_bound'],
        assets=assets,nonfinancial_groups=groups,
        scope='Recognized carrying amounts; nonfinancial classes are disjoint. No complete interest-income or business determination.')


def liability_envelope(facts,end):
    """Recognized interest debt cannot exceed total recognized liabilities.

    Do not infer total liabilities from parent equity alone: noncontrolling
    interests can have a negative balance. Only an explicit liabilities total is
    used here; missing totals remain missing rather than becoming zero.
    """
    facts=standard(facts)
    assets=bounded_amount(facts,'Assets',end)
    liabilities=bounded_amount(facts,'Liabilities',end)
    if not assets or not liabilities or Decimal(assets['lower_bound'])<=0:return None
    return dict(kind='all_recognized_liabilities',status='source_bound',
        numerator_upper=liabilities['upper_bound'],denominator_lower=assets['lower_bound'],
        assets=assets,liabilities=liabilities,
        scope='Recognized debt carrying amounts are a subset of recognized liabilities; this is not a bound on undisclosed commitments or debt face value.')


def apply_upper_proof(check, proof, limit):
    if not proof or proof.get('status')!='source_bound':return check
    check=deepcopy(check)
    upper=Decimal(proof['numerator_upper']);denominator=Decimal(proof['denominator_lower'])
    lower=check.get('minimum_amount')
    if lower is not None and Decimal(lower)>upper:
        # Conflicting evidence must not silently become a clearance.
        check['upper_bound_diagnostic']='Contradicts reported lower amount; proof withheld'
        return check
    ratio=upper/denominator
    check['maximum_amount']=str(upper)
    check['maximum_ratio']=str(ratio)
    check['upper_bound_proof']=proof
    if ratio<Decimal(limit) and check['status']!='fails_initial_filter':
        check.update(status='passes_filter',completeness='source_backed_upper_bound',
            reason='Even the source-backed maximum is below the limit; exact missing components are not imputed')
    return check


def apply_accounting_bounds(checks, facts, end, config):
    checks=deepcopy(checks)
    financial=financial_asset_envelope(facts,end)
    debt=liability_envelope(facts,end)
    checks['debt']=apply_upper_proof(checks['debt'],debt,config['debt_assets_limit'])
    checks['cash_and_interest_items']=apply_upper_proof(checks['cash_and_interest_items'],financial,config['cash_items_assets_limit'])
    checks['receivables_and_cash']=apply_upper_proof(checks['receivables_and_cash'],financial,config['receivables_cash_assets_limit'])
    return checks


def validate_upper_proof(check,limit,end=None):
    """Recompute proof arithmetic from its underlying precision-bound observations."""
    proof=check['upper_bound_proof']
    assets=proof['assets']
    if assets['concept']!='Assets':raise ValueError('Proof denominator is not assets')
    if end is not None and assets['period_end']!=end:raise ValueError('Proof uses another period')
    def validate_fact(f):
        lo,value,hi=(Decimal(f[k]) for k in ['lower_bound','value','upper_bound'])
        if (not all(v.is_finite() for v in [lo,value,hi]) or not 0<=lo<=value<=hi
                or f.get('dimensions') or f['period_end']!=assets['period_end']):
            raise ValueError('Invalid proof observation')
    validate_fact(assets)
    denominator=Decimal(assets['lower_bound'])
    if denominator<=0 or Decimal(proof['denominator_lower'])!=denominator:raise ValueError('Invalid proof denominator')
    if proof['kind']=='all_recognized_liabilities':
        validate_fact(proof['liabilities'])
        if proof['liabilities']['concept']!='Liabilities':raise ValueError('Proof uses a partial liability')
        upper=Decimal(proof['liabilities']['upper_bound'])
    elif proof['kind']=='remaining_recognized_assets':
        categories=[g['category'] for g in proof['nonfinancial_groups']]
        if len(categories)!=len(set(categories)):raise ValueError('Overlapping proof categories')
        allowed={'property_and_equipment':{'PropertyPlantAndEquipmentNet',
            'PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization'},
            'inventory':{'InventoryNet'},'goodwill_and_other_intangibles':{'Goodwill',
            'IntangibleAssetsNetExcludingGoodwill','FiniteLivedIntangibleAssetsNet','GoodwillAndIntangibleAssetsNet'}}
        for group in proof['nonfinancial_groups']:
            tags=[f['concept'] for f in group['facts']]
            if (not tags or group['category'] not in allowed or not set(tags)<=allowed[group['category']]
                    or len(tags)!=len(set(tags))):raise ValueError('Invalid nonfinancial class')
            if group['category']!='goodwill_and_other_intangibles' and len(tags)!=1:
                raise ValueError('Overlapping proof alternatives')
            if len(tags)>1 and (len(tags)!=2 or 'Goodwill' not in tags
                    or 'GoodwillAndIntangibleAssetsNet' in tags):raise ValueError('Overlapping intangible alternatives')
            for f in group['facts']:validate_fact(f)
        removed=sum(Decimal(f['lower_bound']) for g in proof['nonfinancial_groups'] for f in g['facts'])
        upper=Decimal(assets['upper_bound'])-removed
    else:raise ValueError('Unknown accounting proof')
    if upper<0 or Decimal(proof['numerator_upper'])!=upper or Decimal(check['maximum_amount'])!=upper:
        raise ValueError('Upper-bound arithmetic mismatch')
    if Decimal(check['maximum_ratio'])!=upper/denominator:raise ValueError('Upper ratio mismatch')
    if check.get('minimum_amount') is not None and Decimal(check['minimum_amount'])>upper:
        raise ValueError('Lower amount exceeds upper amount')
    if check['status']=='passes_filter' and check['completeness']=='source_backed_upper_bound' and upper/denominator>=Decimal(limit):
        raise ValueError('Upper bound does not prove a pass')
    return True
