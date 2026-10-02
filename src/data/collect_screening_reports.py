"""Collect immutable dated SEC reports; never generate a Shariah verdict.

Annual reports are the default business-evidence corpus. CompanyFacts also
contains quarterly numbers, but that does not certify quarterly narrative coverage.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import requests
from .reconciliation import COMPANY_SYMBOLS, save_json, sha256


def filing_rows(payload):
    table=payload.get('filings',{}).get('recent',payload)
    lengths={len(v) for v in table.values() if isinstance(v,list)}
    if len(lengths)>1:
        raise ValueError('SEC submission columns have different lengths')
    return [{key:value[i] for key,value in table.items() if isinstance(value,list)}
            for i in range(len(table.get('accessionNumber',[])))]


class Collector:
    def __init__(self,folder,user_agent):
        self.folder=folder
        folder.mkdir(parents=True,exist_ok=True)
        self.metadata_path=folder/'metadata.json'
        self.metadata=(json.loads(self.metadata_path.read_text()) if self.metadata_path.exists()
                       else dict(started_at_utc=datetime.now(timezone.utc).isoformat(),files={},failures=[],companies={},status='collecting'))
        self.http=requests.Session()
        self.http.headers.update({'User-Agent':user_agent,'Accept-Encoding':'gzip, deflate'})
        self.last_request=0.

    def get(self,url,relative):
        path=self.folder/relative
        old=self.metadata['files'].get(relative)
        if old:
            if old['url']!=url or not path.exists() or sha256(path)!=old['sha256']:
                raise ValueError('Saved evidence changed: '+relative)
            return path
        if path.exists():
            raise ValueError('Unregistered existing evidence file: '+relative)
        for attempt in range(4):
            time.sleep(max(0,.35-(time.monotonic()-self.last_request)))
            response=self.http.get(url,timeout=(20,120));self.last_request=time.monotonic()
            if response.status_code not in [429,500,502,503,504]:break
            time.sleep(min(2**attempt,8))
        response.raise_for_status()
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(response.content)
        self.metadata['files'][relative]=dict(url=url,sha256=sha256(path),bytes=len(response.content),
            retrieved_at_utc=datetime.now(timezone.utc).isoformat())
        self.save()
        return path

    def save(self):
        save_json(self.metadata_path,self.metadata)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--companyfacts',type=Path,required=True)
    p.add_argument('--xom-companyfacts',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--user-agent',required=True)
    p.add_argument('--start',default='2015-01-01');p.add_argument('--end',default='2025-12-31')
    p.add_argument('--forms',nargs='+',default=['10-K','10-K/A'])
    p.add_argument('--symbols',nargs='+',default=COMPANY_SYMBOLS)
    p.add_argument('--issuer-role',default=None)
    p.add_argument('--issuer-reference',default=None)
    a=p.parse_args()
    if '@' not in a.user_agent:p.error('Use your project name and a real contact email')
    if a.start>a.end:p.error('Start must not follow end')
    c=Collector(a.output,a.user_agent)
    scope=dict(start=a.start,end=a.end,forms=a.forms,symbols=a.symbols,
               xom_study_cik='0000034088',standard_selected=False)
    if a.issuer_role:scope['issuer_role']=a.issuer_role
    if a.issuer_reference:scope['issuer_reference']=a.issuer_reference
    if c.metadata.get('scope',scope)!=scope:raise ValueError('Cannot change scope inside a saved run')
    c.metadata['scope']=scope;c.metadata['failures']=[];catalog=[]
    for ticker in a.symbols:
        try:
            source=a.xom_companyfacts if ticker=='XOM' else a.companyfacts/f'{ticker}_companyfacts.json'
            raw=json.loads(source.read_text(encoding='utf-8-sig'));cik=str(raw['cik']).zfill(10)
            if ticker=='XOM' and int(cik)!=34088:raise ValueError('Wrong XOM issuer for fixed study')
            copied=a.output/'companyfacts'/f'{ticker}.json';copied.parent.mkdir(parents=True,exist_ok=True)
            if copied.exists() and sha256(copied)!=sha256(source):raise ValueError('Input snapshot changed')
            if not copied.exists():copied.write_bytes(source.read_bytes())
            c.metadata['companies'][ticker]=dict(cik=cik,source_entity_name=raw.get('entityName'),
                companyfacts_file=copied.relative_to(a.output).as_posix(),companyfacts_sha256=sha256(copied))
            root=c.get(f'https://data.sec.gov/submissions/CIK{cik}.json',f'submissions/{ticker}/root.json')
            payload=json.loads(root.read_text())
            if int(payload['cik'])!=int(cik):raise ValueError('Submissions issuer CIK mismatch')
            c.metadata['companies'][ticker]['submissions_name']=payload.get('name')
            c.metadata['companies'][ticker]['sic_description']=payload.get('sicDescription')
            rows=filing_rows(payload)
            for item in payload.get('filings',{}).get('files',[]):
                if item['filingTo']<a.start or item['filingFrom']>a.end:continue
                name=item['name']
                if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):raise ValueError('Invalid SEC history filename')
                history=c.get('https://data.sec.gov/submissions/'+name,f'submissions/{ticker}/{name}')
                rows.extend(filing_rows(json.loads(history.read_text())))
            unique={}
            for row in rows:
                if row.get('form') not in a.forms or not a.start<=row.get('filingDate','')<=a.end:continue
                accn=row['accessionNumber']
                if accn in unique and unique[accn]!=row:raise ValueError('Conflicting filing metadata')
                unique[accn]=row
            print(ticker,len(unique),'dated reports',flush=True)
            for row in sorted(unique.values(),key=lambda x:(x['filingDate'],x['accessionNumber'])):
                accn=row['accessionNumber'];base=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace("-", "")}/'
                entry=dict(ticker=ticker,cik=cik,accession_number=accn,form=row['form'],
                    filing_date=row['filingDate'],report_date=row.get('reportDate'),
                    acceptance_datetime=row.get('acceptanceDateTime'),source_url=base+row['primaryDocument'],
                    primary_document=row['primaryDocument'],status='not_downloaded')
                try:
                    path=c.get(entry['source_url'],f'reports/{ticker}/{accn}/report.html')
                    entry.update(status='downloaded',file=path.relative_to(a.output).as_posix(),sha256=sha256(path))
                except (requests.RequestException,ValueError) as error:
                    entry['error']=str(error);c.metadata['failures'].append(dict(ticker=ticker,accession_number=accn,error=str(error)))
                catalog.append(entry)
            save_json(a.output/'filing_catalog.json',catalog);c.save()
        except (requests.RequestException,ValueError,KeyError,OSError) as error:
            c.metadata['failures'].append(dict(ticker=ticker,error=str(error)));c.save()
            print(ticker,'collection issue:',type(error).__name__,flush=True)
    c.metadata.update(status='downloaded' if not c.metadata['failures'] else 'incomplete',
        finished_at_utc=datetime.now(timezone.utc).isoformat(),reports=len(catalog),
        downloaded_reports=sum(x['status']=='downloaded' for x in catalog))
    save_json(a.output/'filing_catalog.json',catalog);c.save()
    print('Collection finished:',c.metadata['status'],c.metadata['downloaded_reports'],'reports',flush=True)
    if c.metadata['failures']:raise SystemExit('Some evidence is missing; inspect metadata rather than assuming zero')


if __name__=='__main__':main()
