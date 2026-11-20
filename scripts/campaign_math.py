#!/usr/bin/env python3
"""Honest payout math for clipping campaigns: what a campaign's rate card actually pays.

"Views x CPM" is not what you get paid. Most campaigns pay nothing until a clip clears a minimum, stop
paying at a cap, and take a fee; pools split a fixed budget across everyone's views. This prints the whole
calculation, assumptions included. Illustrative math, not a promise: most clips earn $0.

Usage:
  python3 -I campaign_math.py cpm --rate 1.00 --min 10 --cap 500 --fee 0.10 --views 3000x770 --views 50000x30 --views 1000000x10
  python3 -I campaign_math.py pool --budget 10000 --pool-views 100000000 --views 1000000 [--fee 0.10]
  python3 -I campaign_math.py target --net 10000 --rate 1.00 [--fee 0.10]

cpm     --rate is $ per 1,000 views; --min / --cap are $ per clip (0 = none); --views VIEWSxCLIPS, repeatable
pool    your share of a pool: budget x your views / all qualifying views, minus the fee
target  paid views needed for a net amount at a rate (no minimums or caps: the best case)
Read every campaign's own brief for its real terms; they change often.
"""
import argparse, json, sys

DISCLAIMER = 'Illustrative math, not a promise. Most clips earn $0. Rates, minimums and caps are set by each campaign.'


def parse_views(items):
    out = []
    for it in items:
        v, _, n = str(it).lower().partition('x')
        try:
            views, clips = int(float(v)), int(n or 1)
        except ValueError:
            raise ValueError(f'bad --views {it!r}: use VIEWSxCLIPS, e.g. 50000x30')
        if views < 0 or clips < 1:
            raise ValueError(f'bad --views {it!r}')
        out.append((views, clips))
    return out


def clip_pay(views, rate, minimum=0.0, cap=0.0):
    """Gross pay for one clip under a CPM rate card."""
    raw = views / 1000.0 * rate
    if minimum and raw < minimum:
        return 0.0
    if cap and raw > cap:
        return float(cap)
    return raw


def cpm(rate, groups, minimum=0.0, cap=0.0, fee=0.0):
    rows, gross, naive, views_total, clips_total = [], 0.0, 0.0, 0, 0
    for views, clips in groups:
        each = clip_pay(views, rate, minimum, cap)
        rows.append({'views_per_clip': views, 'clips': clips, 'pay_per_clip': round(each, 2),
                     'subtotal': round(each * clips, 2),
                     'why': ('below the minimum: $0' if minimum and views / 1000.0 * rate < minimum else
                             'capped' if cap and views / 1000.0 * rate > cap else 'paid at the rate')})
        gross += each * clips
        naive += views / 1000.0 * rate * clips
        views_total += views * clips
        clips_total += clips
    return {'rate_per_1k': rate, 'minimum': minimum, 'cap': cap, 'fee': fee, 'rows': rows,
            'clips': clips_total, 'views': views_total, 'naive': round(naive, 2), 'gross': round(gross, 2),
            'net': round(gross * (1 - fee), 2),
            'share_of_naive': round(gross * (1 - fee) / naive, 3) if naive else None}


def pool(budget, pool_views, views, fee=0.0):
    if pool_views <= 0:
        raise ValueError('--pool-views must be > 0')
    share = budget * views / float(pool_views)
    return {'budget': budget, 'pool_views': pool_views, 'your_views': views, 'gross': round(share, 2),
            'net': round(share * (1 - fee), 2), 'effective_per_1k': round(budget / (pool_views / 1000.0), 4)}


def target(net, rate, fee=0.0):
    views = net / (1 - fee) / rate * 1000.0
    return {'net': net, 'rate_per_1k': rate, 'fee': fee, 'paid_views_needed': int(round(views)),
            'per_day_30': int(round(views / 30))}


def money(x):
    return f'${x:,.2f}'.replace('.00', '')


def render(kind, r):
    if kind == 'cpm':
        lines = [f"| views per clip | clips | pay per clip | subtotal | |", '|---:|---:|---:|---:|---|']
        for row in r['rows']:
            lines.append(f"| {row['views_per_clip']:,} | {row['clips']:,} | {money(row['pay_per_clip'])} | {money(row['subtotal'])} | {row['why']} |")
        lines += ['', f"Terms: {money(r['rate_per_1k'])} per 1,000 views, minimum {money(r['minimum'])} per clip, "
                      f"cap {money(r['cap']) if r['cap'] else 'none'} per clip, fee {r['fee'] * 100:g}%.",
                  f"{r['clips']:,} clips, {r['views']:,} views. Naive views x rate: {money(r['naive'])}. "
                  f"Rate card gross: {money(r['gross'])}. After the fee: {money(r['net'])}"
                  + (f" ({r['share_of_naive'] * 100:.0f}% of the naive figure)." if r['share_of_naive'] is not None else '.')]
    elif kind == 'pool':
        lines = [f"{money(r['budget'])} pool across {int(r['pool_views']):,} qualifying views = {money(r['effective_per_1k'])} per 1,000 views.",
                 f"Your {int(r['your_views']):,} views: {money(r['gross'])} before fees, {money(r['net'])} after."]
    else:
        lines = [f"Netting {money(r['net'])} at {money(r['rate_per_1k'])} per 1,000 views after a {r['fee'] * 100:g}% fee takes "
                 f"{r['paid_views_needed']:,} paid views (about {r['per_day_30']:,} a day for 30 days), "
                 'and that is before any minimum or cap.']
    return '\n'.join(lines + ['', DISCLAIMER])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('cpm'); s.add_argument('--rate', type=float, required=True)
    s.add_argument('--min', type=float, default=0.0); s.add_argument('--cap', type=float, default=0.0)
    s.add_argument('--fee', type=float, default=0.0); s.add_argument('--views', action='append', required=True)
    s.add_argument('--json', action='store_true')
    s = sub.add_parser('pool'); s.add_argument('--budget', type=float, required=True)
    s.add_argument('--pool-views', type=float, required=True); s.add_argument('--views', type=float, required=True)
    s.add_argument('--fee', type=float, default=0.0); s.add_argument('--json', action='store_true')
    s = sub.add_parser('target'); s.add_argument('--net', type=float, required=True)
    s.add_argument('--rate', type=float, required=True); s.add_argument('--fee', type=float, default=0.0)
    s.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    try:
        if not 0 <= a.fee < 1:
            raise ValueError('--fee is a share, e.g. 0.10 for 10%')
        if a.cmd == 'cpm':
            if a.rate <= 0:
                raise ValueError('--rate must be > 0')
            r = cpm(a.rate, parse_views(a.views), a.min, a.cap, a.fee)
        elif a.cmd == 'pool':
            r = pool(a.budget, a.pool_views, a.views, a.fee)
        else:
            if a.rate <= 0:
                raise ValueError('--rate must be > 0')
            r = target(a.net, a.rate, a.fee)
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    print(json.dumps(dict(r, disclaimer=DISCLAIMER), indent=1) if a.json else render(a.cmd, r))
    return 0


if __name__ == '__main__':
    sys.exit(main())
