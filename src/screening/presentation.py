"""Render calculated results; never infer a pass from an absent failure."""
import html


LABELS = {'passes_research_filters': 'Passes research filters',
          'fails_initial_filters': 'Fails a filter', 'needs_review': 'Needs review'}


def write_html(target, records):
    counts = {name: sum(r['research_status'] == name for r in records) for name in LABELS}
    rows = []
    for record in records:
        ratio = record['checks']['debt'].get('ratio')
        debt = 'Unknown' if ratio is None else f'{float(ratio)*100:.2f}% minimum'
        sources = []
        for label, url in [('Financial source', record['source_url']),
                           ('Business source', record['business'].get('source_url'))]:
            if url:
                sources.append(f'<a href="{html.escape(url, quote=True)}">{label}</a>')
        values = [record['ticker'], LABELS[record['research_status']],
                  ', '.join(record['failed_checks']) or 'Evidence incomplete',
                  debt, record['reporting_date']]
        rows.append('<tr>' + ''.join('<td>'+html.escape(v)+'</td>' for v in values)
                    + '<td>'+' | '.join(sources)+'</td></tr>')
    content = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Halalify screening results</title><style>
body{font:16px/1.5 system-ui;margin:30px auto;max-width:1200px;padding:0 20px;color:#183249}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;border:1px solid #cbd5df;text-align:left}
th{background:#183249;color:white}tr:nth-child(even){background:#eef4f8}a{color:#075a9c}
</style><h1>FTSE Yasaar research screening</h1>
<p>Run on 20 October 2026 using evidence available by <strong>31 December 2025</strong>.
FTSE Yasaar v4.6 (February 2026) is applied retrospectively. These are not current-market results.</p>'''
    content += '<p>' + '; '.join(f'<strong>{counts[key]}</strong> {label.lower()}'
                                 for key, label in LABELS.items()) + '.</p>'
    content += '''<p>Needs review means we cannot decide from the available evidence.
It does not mean halal or haram. A minimum debt ratio below the limit cannot prove a pass.
Official Yasaar approval, continuing-member monitoring and purification are outside this run.</p>
<table><thead><tr><th>Stock</th><th>Research result</th><th>Reason</th><th>Debt / assets</th>
<th>Financial date</th><th>Original SEC evidence</th></tr></thead><tbody>'''
    content += ''.join(rows) + '</tbody></table></html>'
    (target/'results.html').write_text(content, encoding='utf8')
