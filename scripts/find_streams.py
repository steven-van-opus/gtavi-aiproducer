#!/usr/bin/env python3
"""Find GTA 6 streams and VODs worth clipping, with yt-dlp (read-only: nothing is downloaded).

Usage:
  python3 -I find_streams.py search "gta 6 kai cenat" [--n 15] [--newest] [--min-hours 1] [--json]
  python3 -I find_streams.py channel URL [--n 20] [--min-hours 1] [--json]
  python3 -I find_streams.py vod URL [--json]

search   YouTube search (flat listing). --newest sorts by upload date. --min-hours keeps long streams only.
channel  the latest videos of a channel page you name, e.g.
           https://www.youtube.com/@IShowSpeed/streams
           https://www.twitch.tv/kaicenat/videos?filter=archives
           https://kick.com/<channel>/videos
vod      title, uploader, length, live status and views of one VOD, without dumping its format list
         (never run `yt-dlp -J` on a day-long VOD: the JSON can be hundreds of MB).

Output: a table (or --json) with the id/URL you hand to vodcut.py / ytfrag.py. Live and post-live YouTube VODs
are what ytfrag.py downloads window by window; Twitch and Kick VODs go through yt-dlp itself.
"""
import argparse, json, shutil, subprocess, sys

SEP = '\x1f'
FIELDS = ['id', 'title', 'channel', 'duration', 'view_count', 'live_status', 'url', 'upload_date']
TEMPLATE = SEP.join(['%(id)s', '%(title)s', '%(channel,uploader)s', '%(duration)s', '%(view_count)s',
                     '%(live_status)s', '%(webpage_url,url)s', '%(upload_date)s'])


def parse_lines(text):
    rows = []
    for line in text.splitlines():
        parts = line.split(SEP)
        if len(parts) != len(FIELDS):
            continue
        r = dict(zip(FIELDS, parts))
        for k in ('duration', 'view_count'):
            v = r.get(k)
            try:
                r[k] = float(v) if k == 'duration' else int(float(v))
            except (TypeError, ValueError):
                r[k] = None
        for k, v in list(r.items()):
            if v in ('NA', 'None', ''):
                r[k] = None
        r['hours'] = round(r['duration'] / 3600, 2) if r.get('duration') else None
        rows.append(r)
    return rows


def keep(rows, min_hours=None):
    if not min_hours:
        return rows
    return [r for r in rows if (r.get('hours') or 0) >= min_hours or r.get('live_status') == 'is_live']


def run_ytdlp(args):
    if not shutil.which('yt-dlp'):
        raise RuntimeError('yt-dlp is required (brew install yt-dlp)')
    out = subprocess.run(['yt-dlp', '--no-warnings', '--ignore-errors', '--print', TEMPLATE] + args,
                         capture_output=True, text=True)
    if out.returncode not in (0, 1) and not out.stdout:
        raise RuntimeError(out.stderr.strip()[:400] or f'yt-dlp exited {out.returncode}')
    return parse_lines(out.stdout)


def search_args(query, n=15, newest=False):
    return ['--flat-playlist', f'{"ytsearchdate" if newest else "ytsearch"}{int(n)}:{query}']


def channel_args(url, n=20):
    return ['--flat-playlist', '--playlist-end', str(int(n)), url]


def vod_args(url):
    return ['--skip-download', url]


def hms(sec):
    if not sec:
        return '-'
    s = int(sec)
    return f'{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}'


def table(rows):
    lines = ['| # | length | views | status | channel | title | url |', '|---:|---:|---:|---|---|---|---|']
    for i, r in enumerate(rows, 1):
        title = (r.get('title') or '').replace('|', '/')[:70]
        views = f"{r['view_count']:,}" if r.get('view_count') is not None else '-'
        lines.append(f"| {i} | {hms(r.get('duration'))} | {views} | {r.get('live_status') or '-'} | "
                     f"{r.get('channel') or '-'} | {title} | {r.get('url') or r.get('id')} |")
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search'); s.add_argument('query'); s.add_argument('--n', type=int, default=15)
    s.add_argument('--newest', action='store_true'); s.add_argument('--min-hours', type=float, default=None)
    s.add_argument('--json', action='store_true')
    s = sub.add_parser('channel'); s.add_argument('url'); s.add_argument('--n', type=int, default=20)
    s.add_argument('--min-hours', type=float, default=None); s.add_argument('--json', action='store_true')
    s = sub.add_parser('vod'); s.add_argument('url'); s.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'search':
            rows = keep(run_ytdlp(search_args(a.query, a.n, a.newest)), a.min_hours)
        elif a.cmd == 'channel':
            rows = keep(run_ytdlp(channel_args(a.url, a.n)), a.min_hours)
        else:
            rows = run_ytdlp(vod_args(a.url))
    except RuntimeError as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    print(json.dumps(rows, indent=1, ensure_ascii=False) if a.json else table(rows))
    return 0 if rows else 1


if __name__ == '__main__':
    sys.exit(main())
