#!/usr/bin/env python3
"""Write the README badges as local SVG files (no third-party badge service, nothing fetched at view time).

  python3 -I docs/src/make_badges.py            # writes docs/badges/*.svg

Edit BADGES below; the skills count is read from the skills/ folder so the badge never drifts.
"""
import html, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'docs', 'badges')
LABEL_BG, VALUE_BG = '#2E3445', '#0E9F8A'

# Verdana 11px advance widths (approximate, px); unknown characters count as 7
WIDE = {'m': 10.7, 'w': 8.9, 'M': 9.9, 'W': 11.2, ' ': 3.9, '.': 4.0, ':': 4.6, '|': 4.6, 'i': 3.1, 'l': 3.1, 'I': 4.3,
        'j': 3.4, 'f': 3.9, 't': 4.3, 'r': 4.7, '1': 7.0, 'x': 6.5, 'k': 6.5, 'c': 5.7, 's': 5.7, 'z': 5.8}


def text_width(s):
    w = 0.0
    for ch in s:
        if ch in WIDE:
            w += WIDE[ch]
        elif ch.isdigit():
            w += 7.0
        elif ch.isupper():
            w += 7.5
        else:
            w += 6.6
    return w


def badge(label, value, value_bg=VALUE_BG):
    lw, vw = round(text_width(label) + 12), round(text_width(value) + 12)
    total = lw + vw
    l, v = html.escape(label), html.escape(value)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" aria-label="{l}: {v}">
  <title>{l}: {v}</title>
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#fff" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
  <clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{lw}" height="20" fill="{LABEL_BG}"/>
    <rect x="{lw}" width="{vw}" height="20" fill="{value_bg}"/>
    <rect width="{total}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{lw / 2:.1f}" y="15" fill="#010101" fill-opacity=".3" textLength="{lw - 12}">{l}</text>
    <text x="{lw / 2:.1f}" y="14" textLength="{lw - 12}">{l}</text>
    <text x="{lw + vw / 2:.1f}" y="15" fill="#010101" fill-opacity=".3" textLength="{vw - 12}">{v}</text>
    <text x="{lw + vw / 2:.1f}" y="14" textLength="{vw - 12}">{v}</text>
  </g>
</svg>
"""


def main():
    skills = len([d for d in os.listdir(os.path.join(ROOT, 'skills'))
                  if os.path.exists(os.path.join(ROOT, 'skills', d, 'SKILL.md'))])
    badges = {
        'claude-code.svg': ('Claude Code', 'plugin'),
        'skills.svg': ('skills', str(skills)),
        'harness.svg': ('harness', 'AI Producer'),
        'clips.svg': ('clips', '1080x1920'),
        'gta6.svg': ('GTA 6', 'Nov 19'),
        'license.svg': ('license', 'MIT'),
    }
    os.makedirs(OUT, exist_ok=True)
    for name, (label, value) in badges.items():
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write(badge(label, value, '#C97A00' if name == 'gta6.svg' else VALUE_BG))
    print(f'wrote {len(badges)} badges to {OUT} (skills: {skills})')


if __name__ == '__main__':
    main()
