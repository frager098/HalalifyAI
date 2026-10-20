"""Read original, non-dimensional issuer facts without guessing totals."""
from copy import deepcopy
from decimal import Decimal
import hashlib
from lxml import etree
from src.data.screening_disclosures import resources,local_name,numeric_value,table_row_label

def read_facts(content,cik,xml=False, include_custom=False):
    parser=etree.XMLParser(huge_tree=True,no_network=True,resolve_entities=False) if xml else etree.HTMLParser(huge_tree=True,no_network=True)
    root=etree.fromstring(content,parser)
    contexts,units=resources(root); out=[]
    for node in root.iter():
        inline=local_name(node)=='nonfraction'
        context_id=node.get('contextRef') if xml else node.get('contextref')
        if not context_id or (not xml and not inline):continue
        ctx=contexts.get(context_id,{})
        identifier=ctx.get('entity_identifier')
        if not identifier or not identifier.isdigit() or int(identifier)!=int(cik) or ctx.get('dimensions'):continue
        unit=units.get(node.get('unitRef') if xml else node.get('unitref'))
        if unit!='USD':continue
        if inline:
            name=node.get('name',''); namespace=name.split(':')[0]
            # Only standard US-GAAP tags are mapped by this extraction.
            if namespace!='us-gaap' and not include_custom:continue
            concept=name.split(':')[-1]
            copied=deepcopy(node)
            for exc in [e for e in copied.iter() if local_name(e)=='exclude']:
                parent=exc.getparent();prev=exc.getprevious()
                if exc.tail:
                    if prev is None:parent.text=(parent.text or '')+exc.tail
                    else:prev.tail=(prev.tail or '')+exc.tail
                parent.remove(exc)
            value,status=numeric_value(''.join(copied.itertext()),node.get('scale','0'),node.get('sign'),node.get('format',''))
        else:
            namespace=etree.QName(node).namespace or ''
            if 'us-gaap' not in namespace and not include_custom:continue
            concept=etree.QName(node).localname
            value,status=numeric_value(node.text or '')
        if status!='parsed' or value is None:continue
        amount=Decimal(value)
        if not amount.is_finite():continue
        out.append(dict(namespace=namespace,concept=concept,value=str(amount),period_start=ctx.get('period_start'),period_end=ctx.get('period_end'),context_id=context_id,unit=unit,row_label=table_row_label(node) if inline else None))
    return out

def unique_amount(facts,concept,end):
    rows=[r for r in facts if r['concept']==concept and not r['period_start'] and r['period_end']==end]
    vals={Decimal(r['value']) for r in rows}
    if len(vals)!=1:return None
    value=next(iter(vals))
    if value<0:return None
    return dict(value=str(value),concept=concept,source_concepts=sorted({r.get('source_concept',r['concept']) for r in rows}),namespaces=sorted({r.get('namespace','us-gaap') for r in rows}),mapping_basis=sorted({r['mapping_basis'] for r in rows if r.get('mapping_basis')}),context_ids=sorted({r['context_id'] for r in rows}),period_end=end,row_labels=sorted({r.get('row_label') for r in rows if r.get('row_label')}))


def mapped_research_facts(standard, candidates, ticker, cik, mappings):
    result=list(standard)
    for mapping in mappings:
        if mapping['ticker']!=ticker or mapping['cik']!=cik:
            continue
        for fact in candidates:
            if fact['namespace']==mapping['namespace'] and fact['concept']==mapping['concept']:
                result.append(dict(fact,concept=mapping['maps_to'],source_concept=fact['concept'],mapping_basis=mapping['basis']))
    return result
