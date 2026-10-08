"""Recover separate XBRL instances for reports predating inline XBRL."""
import argparse
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from .collect_screening_reports import Collector
from .reconciliation import save_json,sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--user-agent',required=True)
    a=p.parse_args();c=Collector(a.input,a.user_agent)
    entries=json.loads((a.input/'filing_catalog.json').read_text());issues=[];notes=[]
    for number,entry in enumerate(entries):
        if entry['status']!='downloaded':continue
        content=(a.input/entry['file']).read_bytes()
        if b':nonfraction' in content.lower():continue
        if entry.get('instance_file'):
            if sha256(a.input/entry['instance_file'])!=entry['instance_sha256']:raise ValueError('Instance checksum changed')
            continue
        base=entry['source_url'].rsplit('/',1)[0]+'/'
        prefix=entry['file'].rsplit('/',1)[0]
        try:
            index=c.get(base+'index.json',prefix+'/index.json')
            names=[item['name'] for item in json.loads(index.read_text())['directory']['item']
                if item['name'].endswith('.xml') and not re.search(r'_(cal|def|lab|pre)\.xml$',item['name'])
                and item['name']!='FilingSummary.xml']
            for index,name in enumerate(names):
                if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):raise ValueError('Invalid SEC filename')
                file=c.get(base+name,prefix+f'/instance_candidate_{index}.xml')
                if ET.fromstring(file.read_bytes()).tag.rsplit('}',1)[-1].lower()=='xbrl':
                    entry.update(instance_file=file.relative_to(a.input).as_posix(),instance_sha256=sha256(file),instance_url=base+name)
                    break
            if not entry.get('instance_file'):
                record=dict(accession_number=entry['accession_number'],reason='No separate XBRL instance listed in original filing directory')
                if entry['form'].endswith('/A'):
                    entry['structured_data_status']='no_instance_supplied_in_amendment';notes.append(record)
                else:issues.append(record)
        except Exception as error:
            issues.append(dict(accession_number=entry['accession_number'],reason=str(error)))
        if number%10==0:
            save_json(a.input/'filing_catalog.json',entries)
            print('Legacy instance progress',number+1,'/',len(entries),flush=True)
    save_json(a.input/'filing_catalog.json',entries)
    c.metadata['legacy_instances']=dict(recovered=sum(bool(x.get('instance_file')) for x in entries),issues=issues,amendment_notes=notes)
    c.save();print(c.metadata['legacy_instances']['recovered'],'legacy instances;',len(issues),'issues',flush=True)
    if issues:raise SystemExit('Legacy instance coverage incomplete')


if __name__=='__main__':main()
