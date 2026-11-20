#!/usr/bin/env python3
"""Build a "5 craziest moments" countdown: one 9:16 source for AI Producer plus its number-header moments.

AI Producer edits one source per project here, so the countdown is assembled locally first: the items are
trimmed, normalised to 1080x1920 / 30 fps / 48 kHz stereo and joined in countdown order (#5 first, #1 last)
with ffmpeg. The joined file is what you upload. timeline.json says where each item lands on that file, so
the number headers, the title and the sound effects can be placed in the AI Producer workspace without guessing.

Usage:
  python3 -I countdown.py build PLAN.json OUT_DIR [--fps 30] [--dry-run]
  python3 -I countdown.py cards OUT_DIR/timeline.json RENDER_ENGINE [--seam-y PX] [--track 40] [--title-seconds 2.4]
                                [--accent "#FFD23F"] [--font-family Anton] [--font-file public/fonts/...]
                                [--hosts-out FILE]

PLAN.json:
  {"title": "5 craziest GTA 6 stream moments",
   "items": [{"rank": 5, "clip": "clips/m03_9x16.mp4", "in": 1.5, "out": 12.0,
              "label": "Cops at the gas station", "streamer": "Kai Cenat", "platform": "twitch", "credit": "@KaiCenat"},
             ...]}
  in/out are seconds inside each clip (default: the whole clip). Items play from the highest rank to #1.

build  writes OUT_DIR/countdown.mp4 and OUT_DIR/timeline.json (frame-exact item starts on the joined file).
cards  writes compositions/countdown-title.html and compositions/countdown-<rank>.html into RENDER_ENGINE:
       a title that builds word by word, then a number header per item ("#5" + label + a small credit line),
       static text the editor can retype, each on a paused GSAP timeline. It prints the host divs to mount
       (aip_mount.py --hosts) and sound-effect instants to fill from list_sound_effects.
"""
import argparse, html, json, os, re, shutil, subprocess, sys

W, H = 1080, 1920
HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')


def fmt(t):
    return ('%.3f' % float(t)).rstrip('0').rstrip('.') or '0'


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration',
                          '-of', 'json', path], capture_output=True, text=True)
    if out.returncode != 0:
        raise ValueError(f'ffprobe could not read {path}')
    d = json.loads(out.stdout or '{}')
    v = next((s for s in d.get('streams', []) if s.get('codec_type') == 'video'), {})
    a = any(s.get('codec_type') == 'audio' for s in d.get('streams', []))
    return {'width': v.get('width'), 'height': v.get('height'), 'has_audio': a,
            'duration': float(d.get('format', {}).get('duration') or 0)}


def load_plan(path, base=None):
    with open(path, encoding='utf-8') as f:
        plan = json.load(f)
    items = plan.get('items') or []
    if len(items) < 2:
        raise ValueError('a countdown needs at least 2 items')
    ranks = [it.get('rank') for it in items]
    if any(not isinstance(r, int) or r < 1 for r in ranks) or len(set(ranks)) != len(ranks):
        raise ValueError('every item needs a unique integer rank >= 1')
    base = base or os.path.dirname(os.path.abspath(path))
    for it in items:
        if not it.get('clip'):
            raise ValueError(f"item #{it['rank']} has no clip")
        if not os.path.isabs(it['clip']):
            it['clip'] = os.path.join(base, it['clip'])
        if not it.get('label'):
            raise ValueError(f"item #{it['rank']} needs a label for its header")
    plan['items'] = sorted(items, key=lambda it: -it['rank'])
    return plan


def layout(plan, infos, fps=30):
    """Frame-exact placement of every item on the joined timeline."""
    out, frames = [], 0
    for it, info in zip(plan['items'], infos):
        a = float(it.get('in') or 0)
        b = float(it['out']) if it.get('out') is not None else info['duration']
        if b <= a:
            raise ValueError(f"item #{it['rank']}: out ({b}) must be after in ({a})")
        if info['duration'] and b > info['duration'] + 0.05:
            raise ValueError(f"item #{it['rank']}: out ({b}) is past the end of {os.path.basename(it['clip'])} ({info['duration']:.2f} s)")
        n = int(round((b - a) * fps))
        out.append({'rank': it['rank'], 'label': it['label'], 'streamer': it.get('streamer'),
                    'platform': it.get('platform'), 'credit': it.get('credit'),
                    'clip': it['clip'], 'in': a, 'out': round(a + n / float(fps), 3), 'frames': n,
                    'start': round(frames / float(fps), 3), 'end': round((frames + n) / float(fps), 3)})
        frames += n
    return out, round(frames / float(fps), 3)


def build_cmd(items, infos, out_mp4, fps=30):
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
    parts, inputs = [], 0
    for i, (it, info) in enumerate(zip(items, infos)):
        dur = it['frames'] / float(fps)
        cmd += ['-ss', f"{it['in']:.3f}", '-t', f'{dur + 0.5:.3f}', '-i', it['clip']]
        vi = inputs
        inputs += 1
        if info['has_audio']:
            ai = f'{vi}:a'
        else:
            cmd += ['-f', 'lavfi', '-t', f'{dur + 0.5:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
            ai = f'{inputs}:a'
            inputs += 1
        parts.append(f'[{vi}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,'
                     f'fps={fps},trim=end_frame={it["frames"]},setpts=PTS-STARTPTS,format=yuv420p[v{i}]')
        fade = min(0.03, dur / 4)
        parts.append(f'[{ai}]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=end={dur:.6f},'
                     f'asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fade:.3f},afade=t=out:st={dur - fade:.6f}:d={fade:.3f}[a{i}]')
    pairs = ''.join(f'[v{i}][a{i}]' for i in range(len(items)))
    graph = ';'.join(parts) + f';{pairs}concat=n={len(items)}:v=1:a=1[v][a]'
    cmd += ['-filter_complex', graph, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out_mp4]
    return cmd


def cmd_build(a):
    plan = load_plan(a.plan)
    missing = [it['clip'] for it in plan['items'] if not os.path.exists(it['clip'])]
    if missing and not a.dry_run:
        raise ValueError('missing clip(s): ' + ', '.join(missing))
    infos = [probe(it['clip']) if os.path.exists(it['clip']) else {'width': W, 'height': H, 'has_audio': True, 'duration': 0}
             for it in plan['items']]
    warnings = [f"#{it['rank']}: {os.path.basename(it['clip'])} is {info['width']}x{info['height']}, not 1080x1920; "
                'it will be centre-cropped (compose it with frame.py first)'
                for it, info in zip(plan['items'], infos) if (info['width'], info['height']) != (W, H)]
    items, total = layout(plan, infos, a.fps)
    if not 45 <= total <= 75:
        warnings.append(f'total {total:.1f} s: the format runs about 60 s (45-75)')
    os.makedirs(a.out_dir, exist_ok=True)
    out_mp4 = os.path.join(a.out_dir, 'countdown.mp4')
    cmd = build_cmd(items, infos, out_mp4, a.fps)
    timeline = {'title': plan.get('title') or f'{len(items)} craziest GTA 6 stream moments', 'fps': a.fps,
                'total': total, 'file': out_mp4, 'items': items}
    if a.dry_run:
        print(json.dumps({'cmd': cmd, 'timeline': timeline, 'warnings': warnings}, indent=1))
        return 0
    if not shutil.which('ffmpeg'):
        raise ValueError('ffmpeg is required (brew install ffmpeg)')
    subprocess.run(cmd, check=True)
    with open(os.path.join(a.out_dir, 'timeline.json'), 'w', encoding='utf-8') as f:
        json.dump(timeline, f, indent=1, ensure_ascii=False)
    got = probe(out_mp4)
    print(json.dumps({'ok': True, 'countdown': out_mp4, 'duration': round(got['duration'], 3), 'expected': total,
                      'size': [got['width'], got['height']], 'items': [(i['rank'], i['start'], i['end']) for i in items],
                      'warnings': warnings}, indent=1))
    return 0


def _face(o):
    return (f'@font-face {{ font-family: "{o["family"]}"; font-weight: 400; '
            f'src: url("{o["file"]}") format("woff2"); }}')


def _outline(px):
    return ', '.join(f'{dx}px {dy}px 0 #000' for dx, dy in [(-px, -px), (px, -px), (-px, px), (px, px), (0, -px - 1),
                                                            (0, px + 1), (-px - 1, 0), (px + 1, 0)])


def title_card(cid, title, o, dur):
    words = title.split()
    step = min(0.22, max(0.08, (dur * 0.5) / max(1, len(words))))
    spans = ' '.join(f'<span class="w" data-in="{fmt(i * step)}">{html.escape(w.upper(), quote=False)}</span>'
                     for i, w in enumerate(words))
    sel = f'[data-composition-id="{cid}"]'
    return f"""<template>
  <div data-composition-id="{cid}" data-width="{W}" data-height="{H}">
    <style>
      {_face(o)}
      {sel} .title {{ position: absolute; left: 8%; right: 8%; top: {o['top']}; text-align: center; font: 400 92px/1.04 "{o['family']}", sans-serif; color: #FFFFFF; text-shadow: {_outline(5)}, 0 10px 22px rgba(0, 0, 0, 0.5); }}
      {sel} .w {{ display: inline-block; margin: 0 0.08em; opacity: 0; }}
      {sel} .w:first-child {{ color: {o['accent']}; }}
    </style>
    <div class="title">{spans}</div>
    <script>
      const root = document.querySelector('[data-composition-id="{cid}"]');
      const tl = gsap.timeline({{ paused: true }});
      root.querySelectorAll(".w").forEach((w) => {{
        tl.fromTo(w, {{ opacity: 0, y: 40, scale: 1.3 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.16, ease: "back.out(2.5)", immediateRender: false }}, Number(w.dataset.in));
      }});
      tl.to(root.querySelector(".title"), {{ opacity: 0, duration: 0.2 }}, {fmt(max(0.2, dur - 0.2))});
      window.__timelines["{cid}"] = tl;
    </script>
  </div>
</template>
"""


def header_card(cid, item, o):
    label = html.escape(item['label'].upper(), quote=False)
    credit = item.get('credit') or item.get('streamer') or ''
    plat = {'youtube': 'YouTube', 'twitch': 'Twitch', 'kick': 'Kick'}.get((item.get('platform') or '').lower(), item.get('platform') or '')
    credit_line = html.escape(f"{credit} · {plat}" if credit and plat else credit, quote=False)
    sel = f'[data-composition-id="{cid}"]'
    return f"""<template>
  <div data-composition-id="{cid}" data-width="{W}" data-height="{H}">
    <style>
      {_face(o)}
      {sel} .head {{ position: absolute; left: 8%; right: 8%; top: {o['top']}; text-align: center; }}
      {sel} .row {{ display: flex; align-items: center; justify-content: center; gap: 22px; }}
      {sel} .num {{ flex: none; font: 400 120px/1 "{o['family']}", sans-serif; color: {o['accent']}; text-shadow: {_outline(6)}, 0 12px 26px rgba(0, 0, 0, 0.5); }}
      {sel} .label {{ font: 400 60px/1.02 "{o['family']}", sans-serif; color: #FFFFFF; text-align: left; text-shadow: {_outline(4)}, 0 8px 18px rgba(0, 0, 0, 0.5); }}
      {sel} .credit {{ margin-top: 10px; font: 400 30px/1.2 "{o['family']}", sans-serif; letter-spacing: 0.04em; color: rgba(255, 255, 255, 0.88); text-shadow: {_outline(2)}; }}
    </style>
    <div class="head">
      <div class="row"><div class="num">#{item['rank']}</div><div class="label">{label}</div></div>
      <div class="credit">{credit_line}</div>
    </div>
    <script>
      const root = document.querySelector('[data-composition-id="{cid}"]');
      const tl = gsap.timeline({{ paused: true }});
      tl.fromTo(root.querySelector(".num"), {{ scale: 1.8, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.18, ease: "back.out(3)", immediateRender: false }}, 0);
      tl.fromTo(root.querySelector(".label"), {{ x: -60, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.2, ease: "power3.out", immediateRender: false }}, 0.1);
      tl.fromTo(root.querySelector(".credit"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2, immediateRender: false }}, 0.25);
      window.__timelines["{cid}"] = tl;
    </script>
  </div>
</template>
"""


def host(cid, title, start, dur, track):
    return (f'<div class="visual-host clip" data-composition-id="{cid}" data-title="{html.escape(title)}" '
            f'data-composition-src="compositions/{cid}.html" data-start="{fmt(start)}" data-duration="{fmt(dur)}" '
            f'data-track-index="{track}" data-width="{W}" data-height="{H}"></div>')


def cmd_cards(a):
    with open(a.timeline, encoding='utf-8') as f:
        tl = json.load(f)
    if not HEX.match(a.accent):
        raise ValueError('--accent must be #RRGGBB')
    if a.seam_y is not None and not 0 < a.seam_y < H - 400:
        raise ValueError('--seam-y must leave room for the header below it')
    top = f'{int(a.seam_y) + 26}px' if a.seam_y is not None else '5.5%'
    o = {'family': a.font_family, 'file': a.font_file, 'accent': a.accent, 'top': top}
    comp = os.path.join(a.render_engine, 'compositions')
    os.makedirs(comp, exist_ok=True)
    files, hosts, sfx = [], [], []
    t_title = min(a.title_seconds, max(0.5, tl['items'][0]['end'] - 0.5)) if a.title_seconds > 0 else 0
    if t_title:
        doc = title_card('countdown-title', tl['title'], o, t_title)
        with open(os.path.join(comp, 'countdown-title.html'), 'w', encoding='utf-8') as f:
            f.write(doc)
        files.append('compositions/countdown-title.html')
        hosts.append(host('countdown-title', 'Countdown title', 0, t_title, a.track + 1))
    for it in tl['items']:
        cid = f"countdown-{it['rank']}"
        start = max(it['start'], t_title) if it is tl['items'][0] else it['start']
        dur = round(it['end'] - start, 3)
        if dur <= 0.3:
            raise ValueError(f"item #{it['rank']} is too short for a header after the title")
        doc = header_card(cid, it, o)
        if len(doc.encode('utf-8')) > 64 * 1024:
            raise ValueError(f'{cid} is over 64 KiB')
        with open(os.path.join(comp, f'{cid}.html'), 'w', encoding='utf-8') as f:
            f.write(doc)
        files.append(f'compositions/{cid}.html')
        hosts.append(host(cid, f"Header #{it['rank']}", start, dur, a.track))
        sfx.append({'at_ms': int(round(start * 1000)), 'what': f"#{it['rank']} header lands", 'anchor': 'first_hit',
                    'family': 'Impacts & Emphasis'})
    hosts_html = '\n'.join(hosts)
    if a.hosts_out:
        with open(a.hosts_out, 'w', encoding='utf-8') as f:
            f.write(hosts_html + '\n')
    print(json.dumps({'ok': True, 'files': files, 'hosts_html': hosts_html, 'sfx_instants': sfx,
                      'font': {'family': o['family'], 'path': o['file']},
                      'note': 'pick each sound_id from list_sound_effects; place all hits in one place_sound_effects '
                              'call with replace:true, as the aip skill says'}, indent=1, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('build', help='join the items into one 1080x1920 source + timeline.json')
    s.add_argument('plan'); s.add_argument('out_dir')
    s.add_argument('--fps', type=int, default=30); s.add_argument('--dry-run', action='store_true')
    s = sub.add_parser('cards', help='write the title + number-header compositions for the AI Producer workspace')
    s.add_argument('timeline'); s.add_argument('render_engine')
    s.add_argument('--track', type=int, default=40, help='track for the headers; the title uses track+1')
    s.add_argument('--title-seconds', type=float, default=2.4, help='0 = no title card')
    s.add_argument('--seam-y', type=float, default=None,
                   help='stacked items: put the title and headers just below the facecam band (frame.py seam_y), '
                        'so they never cover the face; default: top of the frame')
    s.add_argument('--accent', default='#FFD23F')
    s.add_argument('--font-family', default='Anton')
    s.add_argument('--font-file', default='public/fonts/anton-latin-400-normal.woff2')
    s.add_argument('--hosts-out', default=None)
    a = ap.parse_args(argv)
    try:
        return cmd_build(a) if a.cmd == 'build' else cmd_cards(a)
    except (ValueError, OSError, KeyError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}))
        return 2
    except subprocess.CalledProcessError as e:
        print(json.dumps({'ok': False, 'error': f'ffmpeg failed (exit {e.returncode})'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
