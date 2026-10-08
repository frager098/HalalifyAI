"""Reproduce preparation using the versioned saved-input catalog."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('configs/readiness.json'))
    p.add_argument('--train',action='store_true',help='Also rerun provisional model selection; never scores test')
    a=p.parse_args();c=json.loads(a.config.read_text(encoding='utf-8-sig'))
    for key in ['prices','raw_reference','actions','financial_facts']:
        if not Path(c[key]).exists():
            raise FileNotFoundError(f'Missing {key}: {c[key]}. Install the saved data bundle or collect matching inputs first.')
    commands=[['src.data.check_price_actions','--prices',c['prices'],'--raw',c['raw_reference'],'--actions',c['actions']],
              ['src.data.build_research_dataset','--prices','data/interim/readiness_v1/audited_prices.csv'],
              ['src.data.prepare_screening_handoff','--facts',c['financial_facts']]]
    if a.train:commands.append(['src.models.train_candidates','--dataset',c['dataset']])
    for command in commands:
        subprocess.run([sys.executable,'-m',*command],check=True)
    print('Preparation complete. Reports: reports/validation/readiness_v1/. Screening standard remains unselected.')


if __name__=='__main__':main()
