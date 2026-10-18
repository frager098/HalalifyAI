"""Repeatable, offline cleaning of this HalalifyAI downloader's snapshots.

Run: python clean_data.py --root .
Raw inputs are immutable. Every execution writes a new versioned output directory.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import numpy as np
import pandas as pd

PRICE_NUMERIC = ['open', 'high', 'low', 'close', 'volume', 'adjusted_close']
PRICE_KEYS = ['ticker', 'session_date']
FACT_COLUMNS = ['ticker', 'cik', 'entity_name', 'taxonomy', 'concept', 'label',
                'unit', 'start', 'end', 'val', 'accn', 'fy', 'fp', 'form', 'filed',
                'frame', 'source_file', 'source_row']
FACT_KEY = ['cik', 'taxonomy', 'concept', 'unit', 'start', 'end', 'accn', 'filed']

@dataclass
class Config:
    root: str = '.'
    price_version: str | None = None
    sec_version: str | None = None
    start: str | None = None
    end: str | None = None
    max_passes: int = 6
    return_review_threshold: float = 0.25
    allow_spy_calendar_proxy: bool = False


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def fingerprint(df):
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False, default=str), encoding='utf-8')


def choose(base, version):
    if version:
        p = base / version
        if not (p / 'metadata.json').is_file():
            raise FileNotFoundError(p / 'metadata.json')
        return p
    paths = sorted(p.parent for p in base.glob('*/metadata.json'))
    if not paths:
        raise FileNotFoundError(f'No snapshot under {base}')
    # Choose latest explicitly, then validate it. Never silently fall back after failure.
    return paths[-1]


def checked_date(series):
    # Downloader and SEC schemas use ISO calendar dates, not locale-dependent dates.
    s = series.astype('string')
    parsed = pd.to_datetime(s, format='%Y-%m-%d', errors='coerce')
    valid = s.str.fullmatch(r'\d{4}-\d{2}-\d{2}').fillna(False) & parsed.notna()
    return parsed.where(valid)


def clean_loop(frame, transform, label, history, max_passes):
    if max_passes < 2:
        raise ValueError('max_passes must be at least 2 to prove stability.')
    work = frame.copy()
    rejected = []
    for pass_number in range(1, max_passes + 1):
        before = fingerprint(work)
        n = len(work)
        work, bad = transform(work)
        work = work.reset_index(drop=True)
        if not bad.empty:
            bad = bad.copy()
            bad['cleaning_pass'] = pass_number
            rejected.append(bad)
        after = fingerprint(work)
        history.append(dict(table=label, pass_number=pass_number, rows_before=n,
                            rows_after=len(work), removed=len(bad), stable=before == after))
        if before == after:
            return work, pd.concat(rejected, ignore_index=True) if rejected else pd.DataFrame()
    raise RuntimeError(f'{label} did not converge after {max_passes} passes. Review rules.')


def remove_bad(df, reasons):
    bad_mask = reasons.ne('')
    bad = df.loc[bad_mask].copy()
    bad['rejection_reason'] = reasons.loc[bad_mask]
    return df.loc[~bad_mask].copy(), bad


def add_reason(reasons, mask, reason):
    mask = pd.Series(mask, index=reasons.index).fillna(False)
    reasons.loc[mask] = reasons.loc[mask].map(lambda x: x + ';' if x else '') + reason


def price_pass(df, start, end):
    df = df.copy()
    df['ticker'] = df.ticker.astype('string').str.strip().str.upper()
    for col in PRICE_NUMERIC:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
    dates = checked_date(df.session_date)
    df['session_date'] = dates.dt.strftime('%Y-%m-%d').astype('string')
    reasons = pd.Series('', index=df.index, dtype='string')
    add_reason(reasons, df.ticker.isna() | df.ticker.eq(''), 'missing_ticker')
    add_reason(reasons, dates.isna(), 'invalid_session_date')
    add_reason(reasons, dates.lt(pd.Timestamp(start)) | dates.gt(pd.Timestamp(end)), 'outside_requested_window')
    add_reason(reasons, ~np.isfinite(df[PRICE_NUMERIC]).all(axis=1), 'missing_or_nonfinite_numeric')
    add_reason(reasons, df[['open','high','low','close','adjusted_close']].le(0).any(axis=1), 'nonpositive_price')
    add_reason(reasons, df.volume.lt(0) | df.volume.mod(1).ne(0), 'invalid_volume')
    add_reason(reasons, df.high.lt(df[['open','low','close']].max(axis=1)) |
               df.low.gt(df[['open','high','close']].min(axis=1)), 'invalid_ohlc')
    # Remove byte-equivalent observations first; conflicting keys are all quarantined.
    compare = [c for c in df.columns if c != 'source_row']
    exact = df.duplicated(compare, keep='first')
    add_reason(reasons, exact, 'exact_duplicate')
    survivors = df.loc[~exact]
    conflicts = survivors.duplicated(PRICE_KEYS, keep=False)
    add_reason(reasons, df.index.isin(survivors.index[conflicts]), 'conflicting_ticker_date')
    good, bad = remove_bad(df, reasons)
    return good.sort_values(PRICE_KEYS, kind='stable'), bad


def fact_pass(df):
    df = df.copy()
    df['val'] = pd.to_numeric(df.val, errors='coerce').astype('float64')
    reasons = pd.Series('', index=df.index, dtype='string')
    for col in ['end', 'filed']:
        parsed = checked_date(df[col])
        add_reason(reasons, parsed.isna(), f'invalid_{col}')
        df[col] = parsed.dt.strftime('%Y-%m-%d').astype('string')
    starts = checked_date(df.start)
    add_reason(reasons, df.start.notna() & starts.isna(), 'invalid_start')
    df['start'] = starts.dt.strftime('%Y-%m-%d').astype('string')
    add_reason(reasons, starts.gt(checked_date(df.end)), 'reversed_period')
    add_reason(reasons, ~np.isfinite(df.val), 'missing_or_nonfinite_value')
    for col in ['accn','concept','unit','cik']:
        add_reason(reasons, df[col].isna() | df[col].astype('string').str.strip().eq(''), f'missing_{col}')
    compare = [c for c in FACT_COLUMNS if c not in ['source_file','source_row']]
    exact = df.duplicated(compare, keep='first')
    add_reason(reasons, exact, 'exact_duplicate')
    # Preserve repeated periods in different filings and distinct units/taxonomies.
    survivors = df.loc[~exact]
    conflicts = survivors.groupby(FACT_KEY, dropna=False).val.transform('nunique').gt(1)
    add_reason(reasons, df.index.isin(survivors.index[conflicts]), 'conflicting_fact_same_filing')
    good, bad = remove_bad(df, reasons)
    return good.sort_values(FACT_KEY + ['source_row'], kind='stable', na_position='first'), bad


def append_csv(df, path):
    if df.empty:
        return
    df.to_csv(path, mode='a', header=not path.exists(), index=False)


def verify_inputs(price_dir, sec_dir, pmeta, smeta, price_csv):
    checks = []
    def check(p, expected):
        if not p.is_file():
            raise FileNotFoundError(p)
        actual = digest(p)
        checks.append(dict(file=str(p), expected_sha256=expected, actual_sha256=actual))
        if not expected or actual != expected:
            raise ValueError(f'Missing/mismatched checksum: {p}')
    check(price_csv, pmeta.get('normalized_sha256'))
    for item in pmeta.get('pages', []):
        check(price_dir / item['file'], item.get('sha256'))
    if not pmeta.get('pages'):
        raise ValueError('Price metadata has no raw pages.')
    check(sec_dir / 'company_tickers.json', smeta.get('ticker_mapping_sha256'))
    for item in smeta.get('files', []):
        check(sec_dir / item['file'], item.get('sha256'))
    for p in [price_dir/'metadata.json', sec_dir/'metadata.json']:
        checks.append(dict(file=str(p), expected_sha256=None, actual_sha256=digest(p)))
    return checks


def reconcile_raw(prices, price_dir, pmeta):
    from zoneinfo import ZoneInfo
    for basis in ['split', 'all']:
        rows = []
        for item in pmeta['pages']:
            if not item['file'].startswith(basis + '_'):
                continue
            payload = read_json(price_dir / item['file'])
            for ticker, bars in (payload.get('bars') or {}).items():
                for bar in bars:
                    ts = pd.Timestamp(bar['t'])
                    if ts.tzinfo is None:
                        raise ValueError('Raw timestamp lacks timezone.')
                    rows.append(dict(ticker=ticker, session_date=ts.tz_convert(ZoneInfo('America/New_York')).strftime('%Y-%m-%d'),
                                     open=bar['o'], high=bar['h'], low=bar['l'], close=bar['c'], volume=bar['v']))
        raw = pd.DataFrame(rows)
        if raw.empty or raw.duplicated(PRICE_KEYS).any():
            raise ValueError(f'{basis} raw pages empty or duplicated; inspect raw evidence.')
        merged = prices.merge(raw, on=PRICE_KEYS, how='outer', suffixes=('', '_raw'), indicator=True, validate='one_to_one')
        if not merged['_merge'].eq('both').all():
            raise ValueError(f'{basis} raw and interim session keys differ.')
        pairs = [('adjusted_close', 'close_raw')] if basis == 'all' else [(c, c+'_raw') for c in ['open','high','low','close','volume']]
        for left, right in pairs:
            if not np.isclose(merged[left], merged[right], rtol=1e-12, atol=1e-10, equal_nan=False).all():
                raise ValueError(f'Interim column {left} disagrees with raw {basis} bars.')


def calendar_sessions(start, end, prices, allow_proxy):
    try:
        import exchange_calendars as xc
    except ImportError:
        if not allow_proxy:
            raise RuntimeError('Install requirements-cleaning.txt. Calendar verification is required by default.')
        spy = prices.loc[prices.ticker.eq('SPY'), 'session_date']
        if spy.empty:
            raise ValueError('No SPY data for explicitly requested calendar proxy.')
        return pd.DatetimeIndex(pd.to_datetime(spy.unique())).sort_values(), 'SPY_proxy_unverified'
    cal = xc.get_calendar('XNYS', start=pd.Timestamp(start)-pd.Timedelta(days=10), end=pd.Timestamp(end)+pd.Timedelta(days=10))
    dates = cal.sessions_in_range(start, end)
    return dates.tz_localize(None).normalize(), 'XNYS_exchange_calendars'


def coverage_report(prices, sessions, symbols):
    records, gaps = [], []
    for ticker in symbols:
        d = pd.DatetimeIndex(pd.to_datetime(prices.loc[prices.ticker.eq(ticker),'session_date']))
        missing = sessions.difference(d)
        extra = d.difference(sessions)
        records.append(dict(ticker=ticker, rows=len(d), first_date=str(d.min().date()) if len(d) else None,
                            last_date=str(d.max().date()) if len(d) else None,
                            missing_requested_sessions=len(missing), unexpected_sessions=len(extra)))
        for date in missing:
            region = 'entire_series_missing' if not len(d) else ('before_first_observation' if date < d.min() else ('after_last_observation' if date > d.max() else 'internal_gap'))
            gaps.append(dict(ticker=ticker, session_date=date.strftime('%Y-%m-%d'), reason=region))
    return pd.DataFrame(records), pd.DataFrame(gaps, columns=['ticker','session_date','reason'])


def run(config: Config):
    root = Path(config.root).expanduser().resolve()
    price_dir = choose(root/'data/raw/alpaca', config.price_version)
    sec_dir = choose(root/'data/raw/sec_snapshots', config.sec_version)
    pmeta, smeta = read_json(price_dir/'metadata.json'), read_json(sec_dir/'metadata.json')
    if pmeta.get('status') != 'collected_requires_action_and_calendar_review':
        raise ValueError(f'Price download incomplete: {pmeta.get("status")}')
    if smeta.get('failed') or smeta.get('status') != 'downloaded_requires_identity_review':
        raise ValueError('SEC snapshot incomplete. Inspect its metadata or choose an explicit complete version.')
    price_csv = root/'data/interim/prices'/price_dir.name/'daily_prices.csv'
    start, end = config.start or pmeta['requested_start'], config.end or pmeta['requested_end']
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError('start must precede end')
    if start < pmeta['requested_start'] or end > pmeta['requested_end']:
        raise ValueError('Cleaning window must be inside the downloaded price window.')
    version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = root/'data/cleaned'/version
    out.mkdir(parents=True, exist_ok=False)
    history = []
    try:
        inputs = verify_inputs(price_dir, sec_dir, pmeta, smeta, price_csv)
        write_json(out/'input_manifest.json', inputs)
        raw_prices = pd.read_csv(price_csv, dtype={'ticker':'string','session_date':'string'})
        required = set(PRICE_KEYS + PRICE_NUMERIC + ['adjustment_verified','data_quality_flags'])
        if not required.issubset(raw_prices.columns):
            raise ValueError(f'Missing price columns: {required-set(raw_prices.columns)}')
        reconcile_raw(raw_prices, price_dir, pmeta)
        symbols = sorted(pmeta['requested_symbols'])
        if set(raw_prices.ticker) != set(symbols):
            raise ValueError('Requested and returned symbol sets differ.')
        raw_prices['source_row'] = np.arange(2, len(raw_prices)+2)
        prices, rejected = clean_loop(raw_prices, lambda d: price_pass(d, start, end), 'prices', history, config.max_passes)
        rejected.reindex(columns=list(raw_prices.columns)+['rejection_reason','cleaning_pass']).to_csv(out/'prices_quarantine.csv', index=False)
        if prices.empty:
            raise ValueError('No prices survived validation.')
        sessions, calendar = calendar_sessions(start, end, prices, config.allow_spy_calendar_proxy)
        unexpected = ~pd.to_datetime(prices.session_date).isin(sessions)
        if unexpected.any():
            bad = prices.loc[unexpected].copy()
            bad['rejection_reason'] = 'not_exchange_session'
            bad['cleaning_pass'] = 'calendar'
            append_csv(bad.reindex(columns=list(raw_prices.columns)+['rejection_reason','cleaning_pass']), out/'prices_quarantine.csv')
            prices = prices.loc[~unexpected].copy()
        coverage, gaps = coverage_report(prices, sessions, symbols)
        coverage.to_csv(out/'price_coverage.csv', index=False)
        gaps.to_csv(out/'missing_sessions.csv', index=False)
        # Returns only across consecutive exchange sessions; no bridging removed/missing bars.
        session_number = pd.Series(np.arange(len(sessions)), index=sessions.strftime('%Y-%m-%d'))
        prices['session_number'] = prices.session_date.map(session_number)
        consecutive = prices.groupby('ticker').session_number.diff().eq(1)
        prices['split_close_return'] = prices.groupby('ticker').close.pct_change(fill_method=None).where(consecutive)
        prices['provider_all_adjusted_return'] = prices.groupby('ticker').adjusted_close.pct_change(fill_method=None).where(consecutive)
        prices['adjustment_factor'] = prices.adjusted_close / prices.close
        prices['large_return_review'] = prices.provider_all_adjusted_return.abs().gt(config.return_review_threshold)
        prices['zero_volume_review'] = prices.volume.eq(0)
        prices['identity_history_verified'] = False
        prices['adjustment_verified'] = False
        prices['core_ready'] = False
        prices['data_quality_flags'] = prices.data_quality_flags.fillna('') + ';identity_history_unverified;bar_availability_unverified'
        prices.loc[prices.large_return_review, 'data_quality_flags'] += ';large_return_review'
        prices.loc[prices.zero_volume_review, 'data_quality_flags'] += ';zero_volume_review'
        prices.drop(columns='session_number', inplace=True)
        prices.to_csv(out/'prices_clean.csv', index=False)
        prices[prices.ticker.eq('SPY')].to_csv(out/'spy_clean.csv', index=False)
        prices[prices.large_return_review | prices.zero_volume_review].to_csv(out/'price_review.csv', index=False)
        del raw_prices
        current_mapping = {x['ticker']: str(x['cik_str']).zfill(10) for x in read_json(sec_dir/'company_tickers.json').values()}
        groups = {}
        for item in smeta['files']:
            groups.setdefault(item['ticker'], {})[item['kind']] = item
        expected_companies = set(symbols)-{'SPY'}
        identities, counts, older_files = [], [], []
        fact_total = fact_study = fact_bad = fact_future = 0
        for ticker, files in sorted(groups.items()):
            if not {'companyfacts','submissions'}.issubset(files):
                raise ValueError(f'{ticker}: missing companyfacts/submissions pair')
            print(f'Cleaning SEC {ticker}...', flush=True)
            facts_item, sub_item = files['companyfacts'], files['submissions']
            facts = read_json(sec_dir/facts_item['file'])
            sub = read_json(sec_dir/sub_item['file'])
            cik = str(facts['cik']).zfill(10)
            if cik != str(sub['cik']).zfill(10) or cik != facts_item['cik'] or cik != sub_item['cik']:
                raise ValueError(f'{ticker}: SEC issuer CIK mismatch')
            identities.append(dict(ticker=ticker,cik=cik,entity_name=facts.get('entityName'),
                current_mapping_cik=current_mapping.get(ticker),current_mapping_matches=current_mapping.get(ticker)==cik,
                ticker_in_current_submissions=ticker in sub.get('tickers',[]),
                former_names=json.dumps(sub.get('formerNames',[])),identity_history_verified=False,
                review_reason='historical_mapping_requires_evidence' + (';fixed_XOM_predecessor_mapping' if ticker=='XOM' else '')))
            recent = sub.get('filings',{}).get('recent',{})
            lengths = {len(v) for v in recent.values()}
            if len(lengths)>1:
                raise ValueError(f'{ticker}: ragged submissions arrays')
            filings = pd.DataFrame(recent)
            if 'accessionNumber' not in filings or 'acceptanceDateTime' not in filings:
                raise ValueError(f'{ticker}: missing submission keys')
            if filings.accessionNumber.duplicated().any():
                raise ValueError(f'{ticker}: duplicate submission accession')
            filings.insert(0,'ticker',ticker)
            filings.insert(1,'cik',cik)
            submission_columns = ['ticker','cik','accessionNumber','filingDate','reportDate',
                                  'acceptanceDateTime','act','form','fileNumber','filmNumber',
                                  'items','core_type','size','isXBRL','isInlineXBRL',
                                  'isXBRLNumeric','primaryDocument','primaryDocDescription']
            extra_columns = sorted(set(filings.columns)-set(submission_columns))
            filings['extra_fields_json'] = filings[extra_columns].apply(lambda row: json.dumps(row.to_dict()),axis=1) if extra_columns else '{}'
            append_csv(filings.reindex(columns=submission_columns+['extra_fields_json']), out/'sec_submissions.csv')
            for old in sub.get('filings',{}).get('files',[]):
                older_files.append(dict(ticker=ticker,cik=cik,**old))
            acceptance = pd.to_datetime(filings.acceptanceDateTime, errors='coerce', utc=True, format='mixed')
            acc_map = dict(zip(filings.accessionNumber, acceptance))
            rows = []
            row_id = 0
            for taxonomy, concepts in facts.get('facts',{}).items():
                for concept, content in concepts.items():
                    for unit, observations in content.get('units',{}).items():
                        for obs in observations:
                            row_id += 1
                            rows.append(dict(ticker=ticker,cik=cik,entity_name=facts.get('entityName'),taxonomy=taxonomy,
                                concept=concept,label=content.get('label'),unit=unit,
                                **{k:obs.get(k) for k in ['start','end','val','accn','fy','fp','form','filed','frame']},
                                source_file=facts_item['file'],source_row=row_id))
            frame = pd.DataFrame(rows, columns=FACT_COLUMNS)
            cleaned, bad = clean_loop(frame, fact_pass, 'sec_facts_'+ticker, history, config.max_passes)
            append_csv(bad.reindex(columns=FACT_COLUMNS+['rejection_reason','cleaning_pass']), out/'sec_facts_quarantine.csv')
            cleaned['period_days'] = (checked_date(cleaned.end)-checked_date(cleaned.start)).dt.days + 1
            cleaned['acceptance_at_utc'] = pd.to_datetime(cleaned.accn.map(acc_map), errors='coerce', utc=True)
            # A date-only filed value does not justify assuming availability at midnight.
            fallback = (checked_date(cleaned.filed)+pd.Timedelta(days=1)).dt.tz_localize('America/New_York').dt.tz_convert('UTC')
            cleaned['available_at_utc'] = cleaned.acceptance_at_utc.fillna(fallback)
            cleaned['availability_basis'] = np.where(cleaned.acceptance_at_utc.notna(), 'SEC_acceptance_timestamp', 'conservative_next_calendar_day_EST_EDT')
            cleaned['identity_history_verified'] = False
            cleaned['future_period_review'] = checked_date(cleaned.end).gt(checked_date(cleaned.filed))
            cleaned['data_quality_flags'] = 'historical_identity_unverified;current_snapshot_historical_values_may_be_revised'
            cleaned.loc[cleaned.future_period_review, 'data_quality_flags'] += ';period_after_filing_may_be_prospective_disclosure'
            append_csv(cleaned, out/'sec_facts_clean_long.csv')
            # Study cutoffs exclude future filings even if they report older periods.
            cutoff = (pd.Timestamp(end)+pd.Timedelta(days=1)).tz_localize('America/New_York').tz_convert('UTC')
            study = cleaned[cleaned.end.between(start,end) & cleaned.available_at_utc.lt(cutoff) & ~cleaned.future_period_review]
            append_csv(study, out/'sec_facts_study_asof.csv')
            fact_total += len(cleaned)
            fact_study += len(study)
            fact_bad += len(bad)
            fact_future += int(cleaned.future_period_review.sum())
            counts.append(dict(ticker=ticker,raw_facts=len(frame),clean_facts=len(cleaned),study_asof_facts=len(study),quarantined=len(bad),future_period_reviews=int(cleaned.future_period_review.sum()),
                               missing_acceptance_timestamp=int(cleaned.acceptance_at_utc.isna().sum())))
        for filename, cols in [('sec_facts_quarantine.csv',FACT_COLUMNS+['rejection_reason','cleaning_pass']),
                               ('sec_facts_clean_long.csv',FACT_COLUMNS+['period_days','acceptance_at_utc','available_at_utc','availability_basis','identity_history_verified','future_period_review','data_quality_flags']),
                               ('sec_facts_study_asof.csv',FACT_COLUMNS+['period_days','acceptance_at_utc','available_at_utc','availability_basis','identity_history_verified','future_period_review','data_quality_flags'])]:
            if not (out/filename).exists():
                pd.DataFrame(columns=cols).to_csv(out/filename,index=False)
        pd.DataFrame(identities).to_csv(out/'issuer_identity_review.csv',index=False)
        pd.DataFrame(counts).to_csv(out/'sec_coverage.csv',index=False)
        pd.DataFrame(older_files,columns=['ticker','cik','name','filingCount','filingFrom','filingTo']).to_csv(out/'sec_older_submission_files_not_downloaded.csv',index=False)
        pd.DataFrame(history).to_csv(out/'cleaning_passes.csv',index=False)
        missing_sec = sorted(expected_companies-set(groups))
        extra_sec = sorted(set(groups)-expected_companies)
        report = dict(status='completed_with_review_required',core_ready=False,output_dir=str(out),
            config=asdict(config),price_snapshot=price_dir.name,sec_snapshot=sec_dir.name,start=start,end=end,
            calendar=calendar,input_checksums_verified=True,raw_price_reconciliation=True,
            clean_price_rows=len(prices),price_rows_quarantined=int(sum(x['removed'] for x in history if x['table']=='prices')+unexpected.sum()),
            price_symbols=int(prices.ticker.nunique()),missing_requested_sessions=int(len(gaps)),
            large_return_reviews=int(prices.large_return_review.sum()),zero_volume_reviews=int(prices.zero_volume_review.sum()),
            sec_companies=len(groups),missing_sec_symbols=missing_sec,extra_sec_symbols=extra_sec,
            clean_sec_facts=fact_total,study_asof_sec_facts=fact_study,quarantined_sec_facts=fact_bad,sec_future_period_reviews=fact_future,
            older_submission_files_not_downloaded=len(older_files),all_tables_converged=True,
            unresolved=['Corporate actions need independent evidence.', 'Historical ticker/issuer links need dated identity evidence.',
                        'Bar availability timestamps were not collected.', 'Missing sessions need listing-history or provider evidence.',
                        'Older SEC submission chunks were referenced but not downloaded.',
                        'SEC snapshots are current extracts, not archived point-in-time vintages.'],
            environment=dict(python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,
                             exchange_calendars=importlib.metadata.version('exchange-calendars') if calendar.startswith('XNYS') else None))
        # Verify invariants independently after the loop.
        assert not prices.duplicated(PRICE_KEYS).any()
        assert np.isfinite(prices[PRICE_NUMERIC]).all().all()
        assert prices.session_date.between(start,end).all()
        write_json(out/'report.json', report)
        outputs = {p.name:dict(sha256=digest(p),bytes=p.stat().st_size) for p in out.iterdir() if p.is_file()}
        write_json(out/'output_manifest.json', outputs)
        print(json.dumps(report,indent=2),flush=True)
        return report
    except Exception as exc:
        write_json(out/'FAILED.json', dict(error=str(exc),type=type(exc).__name__,config=asdict(config)))
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='.')
    p.add_argument('--price-version')
    p.add_argument('--sec-version')
    p.add_argument('--start')
    p.add_argument('--end')
    p.add_argument('--max-passes',type=int,default=6)
    p.add_argument('--return-review-threshold',type=float,default=0.25)
    p.add_argument('--allow-spy-calendar-proxy',action='store_true')
    args = p.parse_args()
    if args.return_review_threshold <= 0:
        p.error('return-review-threshold must be positive')
    run(Config(**vars(args)))

if __name__ == '__main__':
    main()
