"""List unusual recorded delivery intervals and unmatched request IDs.
Manuscript: Methods 2.1; Tables S3-S4 and source documentation.
Keep the original intervals; do not invent delivery dates or request links."""
from pathlib import Path
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    """Read inputs, run this script and save its outputs."""
    requests = pd.read_csv(ROOT / 'data/source/requests.csv', keep_default_na=False)
    original = pd.read_csv(ROOT / 'data/source/deliveries.csv', keep_default_na=False)
    rounds = original.copy()
    rounds['source_csv_line'] = rounds.index + 2  # Header is line 1.
    rounds['numeric_round'] = pd.to_numeric(rounds.round_number, errors='coerce')
    rounds['numeric_interval_days'] = pd.to_numeric(rounds.days_since_decision, errors='coerce')
    rounds['numeric_doses'] = pd.to_numeric(rounds.doses_delivered, errors='coerce')
    rounds = rounds.loc[rounds.numeric_round.notna()].copy()
    rounds['unmatched_request_id'] = ~rounds.request_id.isin(requests.request_id)
    rounds['negative_recorded_interval'] = rounds.numeric_interval_days.lt(0)
    eligible = rounds.loc[rounds.numeric_interval_days.notna()]
    first = eligible.loc[eligible.numeric_round.eq(1)]
    last = eligible.sort_values('numeric_round').groupby('request_id').tail(1)
    result = {
        'numeric_round_records': len(rounds),
        'numeric_interval_records': len(eligible),
        'missing_numeric_interval_records': int(rounds.numeric_interval_days.isna().sum()),
        'negative_numeric_intervals_retained': int(rounds.negative_recorded_interval.sum()),
        'unmatched_delivery_request_ids': sorted(rounds.loc[rounds.unmatched_request_id, 'request_id'].unique().tolist()),
        'first_round_n': len(first), 'last_numeric_interval_round_n': len(last),
        'mean_first_round_days': float(first.numeric_interval_days.mean()),
        'mean_last_numeric_interval_round_days': float(last.numeric_interval_days.mean()),
        'mean_all_eligible_round_days': float(eligible.numeric_interval_days.mean()),
        'date_policy': 'Retained numeric intervals; no delivery date reconstruction or imputation.',
        'negative_policy': 'Retained as recorded; chronological accuracy not established.',
        'unmatched_policy': 'Retained in round/dose totals; missing interval excluded from timing; no request row added or merged.',
        'last_policy': 'Largest recorded round number among rows with a numeric interval for each request ID.',
    }
    out = ROOT / 'analysis/main/outputs/delivery_provenance'
    out.mkdir(parents=True, exist_ok=True)
    exceptions = rounds.loc[rounds.unmatched_request_id | rounds.negative_recorded_interval,
                            ['source_csv_line', 'Country', 'request_id', 'round_number',
                             'doses_delivered', 'days_since_decision', 'Note',
                             'unmatched_request_id', 'negative_recorded_interval']]
    exceptions.to_csv(out / 'delivery_exceptions.csv', index=False)
    (out / 'interval_summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
