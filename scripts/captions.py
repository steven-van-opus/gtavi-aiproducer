#!/usr/bin/env python3
"""Write word-by-word, GTA-style caption moments into an AI Producer workspace.

Input: the JSON that AI Producer's own caption_cues.py prints for the final cut:
  python3 <aip skill dir>/scripts/caption_cues.py <render-engine> --max-words 3 > cues.json
Output: one composition per caption moment, <render-engine>/compositions/captions-NN.html, written the way
the aip-dynamic-caption skill asks for them:
  - every word is static text in the HTML, so the editor can select, retype and restyle it
  - each cue and each word carries its own data-in / data-out, taken from caption_cues.py, never invented
  - one cue on screen at a time; one paused GSAP timeline registered as window.__timelines["captions-NN"]
  - each file repeats its @font-face and rules, and stays under the 64 KiB per-file limit
plus the host divs to mount last inside the #stage root, on one track no other moment uses (aip_mount.py
inserts them). It never touches the service caption layer (narrator-captions) and never calls build_captions.

Usage:
  python3 -I captions.py CUES.json RENDER_ENGINE [--look pop|karaoke|single|plain] [--track 60]
        [--y 0.70 | --seam-y PX] [--size PX] [--font-family NAME] [--font-file public/fonts/FILE.woff2]
        [--font-weight N] [--accent "#FFD23F"] [--base "#FFFFFF"] [--alt "#6FD3FF"]
        [--alt-cues captions-03:1,captions-05:2] [--emphasis "no way,busted"] [--no-uppercase] [--hosts-out FILE]

Looks:
  pop      words land one by one with a small punch; the word being said is accent-coloured (default)
  karaoke  the whole cue shows; the word being said lights up
  single   one big word at a time (run caption_cues.py with --max-words 1)
  plain    AI Producer's default look: Inter Bold, white, soft shadow, 64 px, band centred at 70%
Positions: --seam-y puts the band on the seam between the facecam and the gameplay (frame.py plan prints
seam_y); otherwise --y is the band's centre as a share of the height (default 0.70, the official default).
Colours: --alt recolours the cues you list in --alt-cues (moment id : cue number), e.g. another voice.
Font: stage the file under render-engine/public/fonts/ in the same commit (commit_workspace can fetch it by
source_url from Fontsource or fonts.gstatic). A font that is not staged renders as another face at export.
"""
import argparse, html, json, os, re, sys

W, H = 1080, 1920
MAX_FILE = 64 * 1024
LOOKS = {
    'pop': {'family': 'Anton', 'file': 'public/fonts/anton-latin-400-normal.woff2', 'weight': 400, 'size': 84, 'upper': True,
            'source': 'https://cdn.jsdelivr.net/fontsource/fonts/anton@latest/latin-400-normal.woff2'},
    'karaoke': {'family': 'Anton', 'file': 'public/fonts/anton-latin-400-normal.woff2', 'weight': 400, 'size': 80, 'upper': True,
                'source': 'https://cdn.jsdelivr.net/fontsource/fonts/anton@latest/latin-400-normal.woff2'},
    'single': {'family': 'Anton', 'file': 'public/fonts/anton-latin-400-normal.woff2', 'weight': 400, 'size': 128, 'upper': True,
               'source': 'https://cdn.jsdelivr.net/fontsource/fonts/anton@latest/latin-400-normal.woff2'},
    'plain': {'family': 'Inter', 'file': 'public/fonts/Inter-700.woff2', 'weight': 700, 'size': 64, 'upper': False,
              'source': 'https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-700-normal.woff2'},
}
HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
NON_LATIN = re.compile(r'[^\u0000-ɏ -⁯₠-⃏]')


def fmt(t):
    return ('%.3f' % float(t)).rstrip('0').rstrip('.') or '0'


def norm_word(w):
    return re.sub(r"[^\w']+", '', w).lower()


def load_moments(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        if data.get('ok') is False:
            raise ValueError(f"caption_cues.py reported an error: {data.get('code')}")
        data = data.get('moments', [])
    if not isinstance(data, list):
        raise ValueError('expected caption_cues.py output: {"ok":true,"moments":[...]}')
    for m in data:
        for key in ('id', 'start', 'duration', 'src_anchor', 'cues'):
            if key not in m:
                raise ValueError(f'moment is missing {key!r}: {str(m)[:120]}')
        if not re.match(r'^captions-\d+$', str(m['id'])):
            raise ValueError(f"moment id {m['id']!r} is not captions-<n>")
    return data


def style_block(cid, look, o):
    fam, size, upper = o['family'], o['size'], o['upper']
    face = (f'@font-face {{ font-family: "{fam}"; font-weight: {o["weight"]}; '
            f'src: url("{o["file"]}") format("{"woff2" if o["file"].endswith(".woff2") else "woff"}"); }}')
    sel = f'[data-composition-id="{cid}"]'
    pos = f'top: {o["top"]}; transform: translateY(-50%);'
    if look == 'plain':
        return (f'{face}\n      {sel} .cue {{ position: absolute; left: 8%; right: 8%; {pos} text-align: center; '
                f'font: {o["weight"]} {size}px/1.15 "{fam}"; color: {o["base"]}; '
                f'text-shadow: 0 3px 12px rgba(0, 0, 0, 0.6); visibility: hidden; }}')
    s = max(3, round(size * 0.055))
    outline = ', '.join(f'{dx}px {dy}px 0 #000' for dx, dy in
                        [(-s, -s), (s, -s), (-s, s), (s, s), (0, -s - 1), (0, s + 1), (-s - 1, 0), (s + 1, 0)])
    return (f'{face}\n'
            f'      {sel} .cue {{ position: absolute; left: 8%; right: 8%; {pos} text-align: center; '
            f'font: {o["weight"]} {size}px/1.08 "{fam}", sans-serif; color: {o["base"]}; '
            f'{"text-transform: uppercase; " if upper else ""}letter-spacing: 0.01em; '
            f'text-shadow: {outline}, 0 {s + 4}px 18px rgba(0, 0, 0, 0.55); visibility: hidden; }}\n'
            f'      {sel} .w {{ display: inline-block; margin: 0 0.1em; transform-origin: 50% 70%;'
            f'{" opacity: 0;" if look in ("pop", "single") else ""} }}\n'
            f'      {sel} .cue.alt .w {{ color: {o["alt"]}; }}\n'
            f'      {sel} .w.em {{ color: {o["accent"]}; }}')


def script_block(cid, look, o):
    head = (f'      const root = document.querySelector(\'[data-composition-id="{cid}"]\');\n'
            '      const tl = gsap.timeline({ paused: true });\n')
    cues = ('      root.querySelectorAll(".cue").forEach((cue) => {\n'
            '        tl.set(cue, { visibility: "visible" }, Number(cue.dataset.in));\n'
            '        tl.set(cue, { visibility: "hidden" }, Number(cue.dataset.out));\n')
    if look == 'plain':
        body = ''
    else:
        acc, base, alt = o['accent'], o['base'], o['alt']
        body = (f'        const rest = cue.classList.contains("alt") ? "{alt}" : "{base}";\n'
                '        cue.querySelectorAll(".w").forEach((w) => {\n'
                '          const t = Number(w.dataset.in), u = Number(w.dataset.out);\n'
                '          const after = w.classList.contains("em") ? "' + acc + '" : rest;\n')
        if look in ('pop', 'single'):
            punch = '1.35' if look == 'pop' else '1.6'
            body += (f'          tl.fromTo(w, {{ opacity: 0, scale: {punch} }}, {{ opacity: 1, scale: 1, duration: 0.12, '
                     'ease: "back.out(3)", immediateRender: false }, t);\n'
                     f'          tl.set(w, {{ color: "{acc}" }}, t);\n'
                     '          tl.set(w, { color: after }, Math.max(t + 0.06, u));\n')
        else:  # karaoke
            body += (f'          tl.set(w, {{ color: "{acc}", scale: 1.08 }}, t);\n'
                     '          tl.set(w, { color: after, scale: 1 }, Math.max(t + 0.06, u));\n')
        body += '        });\n'
    tail = ('      });\n'
            f'      window.__timelines["{cid}"] = tl;\n')
    return head + cues + body + tail


def cue_html(m, ci, cue, look, o):
    cls = 'cue'
    if ci in o['alt_cues'].get(m['id'], set()):
        cls += ' alt'
    words = cue.get('words') or []
    if look == 'plain' or not words:
        text = ' '.join(html.escape(str(w[0]), quote=False) for w in words) if words else html.escape(str(cue.get('text', '')), quote=False)
        return f'    <div class="{cls}" data-in="{fmt(cue["in"])}" data-out="{fmt(cue["out"])}">{text}</div>'
    spans = []
    for w in words:
        text, t_in, t_out = str(w[0]), w[1], w[2]
        wc = 'w em' if norm_word(text) in o['emphasis'] else 'w'
        spans.append(f'<span class="{wc}" data-in="{fmt(t_in)}" data-out="{fmt(t_out)}">{html.escape(text, quote=False)}</span>')
    return f'    <div class="{cls}" data-in="{fmt(cue["in"])}" data-out="{fmt(cue["out"])}">{" ".join(spans)}</div>'


def composition(m, look, o):
    cid = m['id']
    cues = '\n'.join(cue_html(m, i, c, look, o) for i, c in enumerate(m['cues'], 1))
    return ('<template>\n'
            f'  <div data-composition-id="{cid}" data-width="{W}" data-height="{H}">\n'
            '    <style>\n'
            f'      {style_block(cid, look, o)}\n'
            '    </style>\n'
            f'{cues}\n'
            '    <script>\n'
            f'{script_block(cid, look, o)}'
            '    </script>\n'
            '  </div>\n'
            '</template>\n')


def host(m, track):
    n = int(str(m['id']).split('-')[1])
    return (f'<div class="visual-host clip" data-composition-id="{m["id"]}" data-title="Captions {n}" '
            f'data-composition-src="compositions/{m["id"]}.html" data-start="{fmt(m["start"])}" '
            f'data-duration="{fmt(m["duration"])}" data-src-anchor="{fmt(m["src_anchor"])}" '
            f'data-track-index="{track}" data-width="{W}" data-height="{H}"></div>')


def parse_alt_cues(text):
    out = {}
    for item in filter(None, (text or '').split(',')):
        mid, _, num = item.strip().partition(':')
        if not num.isdigit():
            raise ValueError(f'--alt-cues item {item!r} is not <moment id>:<cue number>')
        out.setdefault(mid, set()).add(int(num))
    return out


def options(a):
    look = LOOKS[a.look]
    for name in ('accent', 'base', 'alt'):
        if not HEX.match(getattr(a, name)):
            raise ValueError(f'--{name} must be a #RRGGBB colour')
    if a.seam_y is not None:
        if not 0 < a.seam_y < H:
            raise ValueError('--seam-y must be inside the 1920 px canvas')
        top = f'{int(a.seam_y)}px'
        centre = a.seam_y / H
    else:
        if not 0.1 <= a.y <= 0.9:
            raise ValueError('--y must be between 0.1 and 0.9')
        top = f'{round(a.y * 100, 2)}%'
        centre = a.y
    return {'family': a.font_family or look['family'], 'file': a.font_file or look['file'],
            'weight': a.font_weight or look['weight'], 'size': a.size or look['size'],
            'upper': look['upper'] and not a.no_uppercase, 'top': top, 'centre': centre,
            'accent': a.accent, 'base': a.base, 'alt': a.alt,
            'alt_cues': parse_alt_cues(a.alt_cues),
            'emphasis': {norm_word(w) for w in (a.emphasis or '').split(',') if norm_word(w)},
            'source': None if a.font_file else look['source']}


def warnings_for(moments, look, o):
    out = []
    chars_per_line = max(8, int((W * 0.84) / (o['size'] * (0.48 if o['upper'] else 0.52))))
    limit = chars_per_line * (1 if look == 'single' else 2)
    for m in moments:
        for i, c in enumerate(m['cues'], 1):
            text = ' '.join(str(w[0]) for w in c.get('words', []))
            if len(text) > limit:
                out.append(f"{m['id']} cue {i} ({len(text)} chars) may need a third line at {o['size']} px: split it at a word boundary")
            if NON_LATIN.search(text) and o['family'] in ('Anton', 'Inter'):
                out.append(f"{m['id']} cue {i} has characters outside Latin: stage a Noto Sans face for that script")
    half = (o['size'] * 1.1 * (1 if look == 'single' else 2)) / 2 / H
    if o['centre'] - half < 0.06 or o['centre'] + half > 0.86:
        out.append('caption band reaches the top 6% or the bottom 14% of the frame, where platform UI sits')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cues_json', help='output of caption_cues.py (or its "moments" list)')
    ap.add_argument('render_engine', help='local render-engine directory (compositions/ is written inside it)')
    ap.add_argument('--look', default='pop', choices=sorted(LOOKS))
    ap.add_argument('--track', type=int, default=60, help='data-track-index for every caption host (default 60)')
    ap.add_argument('--y', type=float, default=0.70, help='band centre as a share of the height (default 0.70)')
    ap.add_argument('--seam-y', type=float, default=None, help='band centre in px, e.g. the seam_y frame.py printed')
    ap.add_argument('--size', type=int, default=None, help='font size in px (default: the look\'s)')
    ap.add_argument('--font-family', default=None); ap.add_argument('--font-file', default=None)
    ap.add_argument('--font-weight', type=int, default=None)
    ap.add_argument('--accent', default='#FFD23F'); ap.add_argument('--base', default='#FFFFFF')
    ap.add_argument('--alt', default='#6FD3FF')
    ap.add_argument('--alt-cues', default='', help='cues in the --alt colour: captions-03:1,captions-05:2')
    ap.add_argument('--emphasis', default='', help='comma-separated words that stay in the accent colour')
    ap.add_argument('--no-uppercase', action='store_true')
    ap.add_argument('--hosts-out', default=None, help='also write the host divs to this file')
    a = ap.parse_args(argv)
    try:
        moments = load_moments(a.cues_json)
        o = options(a)
    except (ValueError, OSError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}))
        return 2
    comp_dir = os.path.join(a.render_engine, 'compositions')
    os.makedirs(comp_dir, exist_ok=True)
    files, hosts = [], []
    for m in moments:
        doc = composition(m, a.look, o)
        size = len(doc.encode('utf-8'))
        if size > MAX_FILE:
            print(json.dumps({'ok': False, 'error': f"{m['id']} is {size} bytes, over the 64 KiB limit: use fewer words per cue"}))
            return 2
        path = os.path.join(comp_dir, f"{m['id']}.html")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(doc)
        files.append(f"compositions/{m['id']}.html")
        hosts.append(host(m, a.track))
    hosts_html = '\n'.join(hosts)
    if a.hosts_out:
        with open(a.hosts_out, 'w', encoding='utf-8') as f:
            f.write(hosts_html + '\n')
    print(json.dumps({'ok': True, 'look': a.look, 'moments': len(moments), 'files': files, 'track': a.track,
                      'font': {'family': o['family'], 'path': o['file'], 'source_url_hint': o['source']},
                      'warnings': warnings_for(moments, a.look, o), 'hosts_html': hosts_html},
                     indent=1, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
