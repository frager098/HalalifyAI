"""Source-specific business revenue findings; no keyword-only classifications."""
from copy import deepcopy
from decimal import Decimal
import hashlib
from lxml import etree
from src.data.screening_disclosures import visible_report_text
from .accounting_bounds import standard
from .field_recovery import reconcile_amount
from .source_facts import read_facts


def reviewed_revenue_failure(business, report, content, review, limit):
    """Confirm a reviewed category exceeds the ceiling using a conservative floor.

    Classification is an explicit research assessment in the versioned registry.
    The original source, issuer, annual dates, values and explanatory markers
    must all match. A category below the ceiling cannot clear other categories.
    """
    for key in ['cik', 'accession_number', 'source_url']:
        if report.get(key) != review.get(key):
            raise ValueError('Business revenue review belongs to another source')
    if (report['sha256'] != review['source_sha256']
            or hashlib.sha256(content).hexdigest() != review['source_sha256']):
        raise ValueError('Business revenue original source changed')
    if report['report_date'] != review['period_end']:
        raise ValueError('Business revenue period mismatch')
    text = visible_report_text(etree.fromstring(content,
        etree.HTMLParser(huge_tree=True, no_network=True)))
    normalized = ' '.join(text.split()).casefold()
    if any(' '.join(marker.split()).casefold() not in normalized
           for marker in review['required_source_markers']):
        raise ValueError('Reviewed business description is absent')
    facts = [f for f in standard(read_facts(content, report['cik']))
             if f['period_start'] == review['period_start']
             and f['period_end'] == review['period_end'] and not f['dimensions']]
    # Reuse declared-precision reconciliation, restricted to this annual period.
    instants = [dict(f, period_start=None) for f in facts]
    amounts = {}
    for key in ['numerator', 'denominator']:
        mapping = review[key]
        amount = reconcile_amount(instants, mapping['concept'], review['period_end'])
        if not amount or Decimal(amount['value']) != Decimal(mapping['expected_value']):
            raise ValueError('Reviewed annual business amount is missing or different')
        amount['period_start'] = review['period_start']
        amounts[key] = amount
    numerator, denominator = amounts['numerator'], amounts['denominator']
    if Decimal(denominator['lower_bound']) <= 0:
        raise ValueError('Invalid business revenue denominator')
    floor = Decimal(numerator['lower_bound']) / Decimal(denominator['upper_bound'])
    if floor <= Decimal(limit):
        raise ValueError('Reviewed category does not prove a business failure')
    result = deepcopy(business)
    result.update(status='fails_initial_filter', reason=review['reason'],
        source_url=report['source_url'], source_sha256=report['sha256'],
        accession_number=report['accession_number'], filing_date=report['filing_date'],
        category=review['category'], prohibited_revenue_percentage=None,
        prohibited_revenue_minimum_ratio=str(floor),
        reported_category_ratio=str(Decimal(numerator['value']) / Decimal(denominator['value'])),
        numerator=numerator, denominator=denominator,
        assessment='source_specific_research_not_domain_approved',
        limitation='An evidenced category alone exceeds the ceiling; not a complete prohibited-revenue inventory or official Yasaar decision')
    return result


def validate_business_revenue(business, limit):
    """Independently check the saved conservative business-share calculation."""
    numerator, denominator = business['numerator'], business['denominator']
    if (numerator['period_start'] != denominator['period_start']
            or numerator['period_end'] != denominator['period_end']):
        raise ValueError('Business numerator and denominator periods differ')
    floor = Decimal(numerator['lower_bound']) / Decimal(denominator['upper_bound'])
    reported = Decimal(numerator['value']) / Decimal(denominator['value'])
    if (floor <= Decimal(limit) or floor != Decimal(business['prohibited_revenue_minimum_ratio'])
            or reported != Decimal(business['reported_category_ratio'])
            or business['status'] != 'fails_initial_filter'):
        raise ValueError('Business revenue finding is not supported by its arithmetic')
    return True
