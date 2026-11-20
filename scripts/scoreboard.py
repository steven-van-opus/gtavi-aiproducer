#!/usr/bin/env python3
"""Scoreboard + learning loop: log every posted clip, then turn the numbers into rules the other skills read.

One CSV row per post. You (or Claude) fill views as they come in; nothing here reads any platform for you.
`rules` writes LEARNED_RULES.md: which formats, hooks, caption looks, streamers and lengths beat your own
median, and which lag it. pick-moments and hooks read that file before choosing.

Usage:
  python3 -I scoreboard.py init BOARD.csv
  python3 -I scoreboard.py add BOARD.csv --clip-id m03 --streamer "Kai Cenat" --platform tiktok --format single
                                         --hook "question" --caption-look pop --length 31 [--url URL] [--campaign NAME]
  python3 -I scoreboard.py update BOARD.csv m03 --views-24h 48200 [--views-1h N] [--views-7d N] [--approved y|n]
                                                [--payout 12.50] [--notes "..."]
  python3 -I scoreboard.py report BOARD.csv [--metric views_24h]
  python3 -I scoreboard.py rules BOARD.csv [--out LEARNED_RULES.md] [--metric views_24h] [--min-clips 3]

Payouts are whatever the campaign actually paid you, entered by hand. Never put estimates in that column.
"""
import argparse, csv, datetime, os, statistics, sys

FIELDS = ['date', 'clip_id', 'streamer', 'platform', 'url', 'format', 'hook', 'caption_look', 'length_s', 'campaign',
          'views_1h', 'views_24h', 'views_7d', 'approved', 'payout_usd', 'notes']
DIMENSIONS = ['format', 'hook', 'caption_look', 'streamer', 'platform', 'length_bucket']
NUMERIC = ('views_1h', 'views_24h', 'views_7d', 'length_s', 'payout_usd')


def read(path):
    if not os.path.exists(path):
        raise ValueError(f'{path} does not exist: run `scoreboard.py init {path}` first')
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    return rows


def write(path, rows):
    tmp = path + '.part'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})
    os.replace(tmp, path)


def num(v):
    try:
        return float(str(v).replace(',', ''))
    except (TypeError, ValueError):
        return None


def length_bucket(row):
    n = num(row.get('length_s'))
    if n is None:
        return ''
    return '<20s' if n < 20 else '20-35s' if n < 35 else '35-60s' if n < 60 else '60s+'


def groups(rows, dim, metric):
    out = {}
    for r in rows:
        key = length_bucket(r) if dim == 'length_bucket' else (r.get(dim) or '').strip()
        v = num(r.get(metric))
        if key and v is not None:
            out.setdefault(key, []).append(v)
    return out


def report(rows, metric='views_24h'):
    vals = [num(r.get(metric)) for r in rows if num(r.get(metric)) is not None]
    lines = [f'# Scoreboard ({len(rows)} posts, {len(vals)} with {metric})', '']
    if not vals:
        return '\n'.join(lines + [f'No {metric} yet: fill it with `scoreboard.py update`.'])
    overall = statistics.median(vals)
    lines.append(f'Median {metric}: {overall:,.0f}. Sum: {sum(vals):,.0f}.')
    approved = [r for r in rows if (r.get('approved') or '').lower() in ('y', 'n')]
    if approved:
        ok = sum((r['approved'] or '').lower() == 'y' for r in approved)
        lines.append(f'Campaign approvals: {ok}/{len(approved)}.')
    paid = [num(r.get('payout_usd')) for r in rows if num(r.get('payout_usd'))]
    if paid:
        lines.append(f'Payouts entered: ${sum(paid):,.2f} over {len(paid)} posts (actual amounts you entered).')
    for dim in DIMENSIONS:
        g = groups(rows, dim, metric)
        if not g:
            continue
        lines += ['', f'## By {dim}', '', f'| {dim} | posts | median {metric} | vs overall |', '|---|---:|---:|---:|']
        for key, vs in sorted(g.items(), key=lambda kv: -statistics.median(kv[1])):
            med = statistics.median(vs)
            lines.append(f'| {key} | {len(vs)} | {med:,.0f} | {med / overall:.2f}x |' if overall else f'| {key} | {len(vs)} | {med:,.0f} | - |')
    top = sorted((r for r in rows if num(r.get(metric)) is not None), key=lambda r: -num(r.get(metric)))[:5]
    lines += ['', '## Top posts', '']
    for r in top:
        lines.append(f"- {r.get('clip_id')} ({r.get('streamer')}, {r.get('platform')}, {r.get('format')}, hook: {r.get('hook')}): "
                     f"{num(r.get(metric)):,.0f} {metric}")
    return '\n'.join(lines)


def rules(rows, metric='views_24h', min_clips=3, hi=1.5, lo=0.67):
    vals = [num(r.get(metric)) for r in rows if num(r.get(metric)) is not None]
    out = {'more': [], 'less': [], 'fix': []}
    if not vals:
        return out, None
    overall = statistics.median(vals)
    for dim in DIMENSIONS:
        for key, vs in groups(rows, dim, metric).items():
            if len(vs) < min_clips or not overall:
                continue
            ratio = statistics.median(vs) / overall
            item = (dim, key, len(vs), statistics.median(vs), ratio)
            if ratio >= hi:
                out['more'].append(item)
            elif ratio <= lo:
                out['less'].append(item)
    by_campaign = {}
    for r in rows:
        if (r.get('approved') or '').lower() in ('y', 'n') and r.get('campaign'):
            by_campaign.setdefault(r['campaign'], []).append(r['approved'].lower() == 'y')
    for camp, oks in by_campaign.items():
        if len(oks) >= 2 and sum(oks) / len(oks) < 0.5:
            out['fix'].append((camp, sum(oks), len(oks)))
    for k in ('more', 'less'):
        out[k].sort(key=lambda it: -it[4] if k == 'more' else it[4])
    return out, overall


def rules_md(r, overall, metric, n_rows, min_clips):
    today = datetime.date.today().isoformat()
    lines = ['# LEARNED_RULES', '', f'Written {today} by scoreboard.py from {n_rows} posts. Median {metric}: '
             + (f'{overall:,.0f}.' if overall is not None else 'n/a.'),
             f'A rule needs at least {min_clips} posts behind it. Re-run after every batch; delete rules that stop holding.', '']
    if overall is None:
        return '\n'.join(lines + ['No numbers yet.'])
    lines += ['## Do more', '']
    lines += [f'- {dim} = **{key}**: median {med:,.0f} over {n} posts ({ratio:.1f}x your median)' for dim, key, n, med, ratio in r['more']] or ['- (nothing clears 1.5x yet)']
    lines += ['', '## Do less', '']
    lines += [f'- {dim} = **{key}**: median {med:,.0f} over {n} posts ({ratio:.2f}x your median)' for dim, key, n, med, ratio in r['less']] or ['- (nothing under 0.67x yet)']
    lines += ['', '## Fix before submitting again', '']
    lines += [f'- campaign **{c}**: {ok}/{n} approved. Re-read its brief (credit, hashtags, logos, length, deadline).' for c, ok, n in r['fix']] or ['- (no campaign under 50% approval)']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('init'); s.add_argument('board')
    s = sub.add_parser('add'); s.add_argument('board')
    for f in ('clip-id', 'streamer', 'platform', 'url', 'format', 'hook', 'caption-look', 'campaign', 'notes', 'date'):
        s.add_argument('--' + f, default='')
    s.add_argument('--length', default='')
    s = sub.add_parser('update'); s.add_argument('board'); s.add_argument('clip_id')
    for f in ('views-1h', 'views-24h', 'views-7d', 'approved', 'payout', 'notes', 'url', 'campaign'):
        s.add_argument('--' + f, default=None)
    s = sub.add_parser('report'); s.add_argument('board'); s.add_argument('--metric', default='views_24h')
    s = sub.add_parser('rules'); s.add_argument('board'); s.add_argument('--metric', default='views_24h')
    s.add_argument('--out', default='LEARNED_RULES.md'); s.add_argument('--min-clips', type=int, default=3)
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'init':
            if os.path.exists(a.board):
                raise ValueError(f'{a.board} already exists')
            write(a.board, [])
            print(f'created {a.board}')
            return 0
        rows = read(a.board)
        if a.cmd == 'add':
            if not a.clip_id:
                raise ValueError('--clip-id is required')
            if any(r['clip_id'] == a.clip_id and r['platform'] == a.platform for r in rows):
                raise ValueError(f'{a.clip_id} on {a.platform} is already on the board: use update')
            rows.append({'date': a.date or datetime.date.today().isoformat(), 'clip_id': a.clip_id, 'streamer': a.streamer,
                         'platform': a.platform, 'url': a.url, 'format': a.format, 'hook': a.hook,
                         'caption_look': a.caption_look, 'length_s': a.length, 'campaign': a.campaign, 'notes': a.notes})
            write(a.board, rows)
            print(f'added {a.clip_id}')
            return 0
        if a.cmd == 'update':
            hits = [r for r in rows if r['clip_id'] == a.clip_id]
            if not hits:
                raise ValueError(f'{a.clip_id} is not on the board')
            if a.approved is not None and a.approved.lower() not in ('y', 'n', ''):
                raise ValueError('--approved is y or n')
            for r in hits:
                for src, dst in (('views_1h', 'views_1h'), ('views_24h', 'views_24h'), ('views_7d', 'views_7d'),
                                 ('approved', 'approved'), ('payout', 'payout_usd'), ('notes', 'notes'), ('url', 'url'),
                                 ('campaign', 'campaign')):
                    v = getattr(a, src)
                    if v is not None:
                        if dst in NUMERIC and v != '' and num(v) is None:
                            raise ValueError(f'--{src.replace("_", "-")} must be a number')
                        r[dst] = v
            write(a.board, rows)
            print(f'updated {a.clip_id} ({len(hits)} row(s))')
            return 0
        if a.cmd == 'report':
            print(report(rows, a.metric))
            return 0
        r, overall = rules(rows, a.metric, a.min_clips)
        text = rules_md(r, overall, a.metric, len(rows), a.min_clips)
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(text)
        print(text)
        return 0
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
