"""Build a minimal, valid AI Producer render-engine workspace for offline tests.

It mirrors what a fresh project holds after transcription: index.html with the #stage root and one
speaker video/audio pair over public/source.mp4 / public/source.mp3, and compositions/editing-script.json
with an av track and a captions track holding word timings. Media files are not created; tests declare
them to the official preflight with --remote-file, exactly as the official workspace guide says.
"""
import glob, json, os

REMOTE = ['public/source.mp4', 'public/source.mp3', 'public/vendor/gsap.min.js']

INDEX = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="public/vendor/gsap.min.js"></script>
</head>
<body>
  <div id="stage" data-composition-id="finecut-root" data-start="0" data-duration="{dur}" data-width="1080" data-height="1920">
    <video id="speaker" class="clip speaker-clip" src="public/source.mp4" muted playsinline data-volume="0" preload="none" data-start="0" data-duration="{dur}" data-media-start="0" data-track-index="0" data-hf-id="pair-1"></video>
    <audio id="speaker-audio" class="clip speaker-clip" src="public/source.mp3" data-volume="1" preload="none" data-start="0" data-duration="{dur}" data-media-start="0" data-track-index="1" data-hf-id="pair-1"></audio>
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const rootTl = gsap.timeline({{ paused: true }});
    window.__timelines["finecut-root"] = rootTl;
  </script>
</body>
</html>
"""

# Invented speech, timed in milliseconds: (text, start, end). Three sentences with a pause between them.
WORDS = [
    ('Chat,', 0, 420), ('look', 480, 700), ('at', 700, 800), ('all', 800, 980), ('this', 980, 1200), ('money.', 1200, 1700),
    ('No', 2900, 3100), ('way', 3100, 3400), ('bro,', 3400, 3800), ('the', 3900, 4000), ('cops', 4000, 4400),
    ('are', 4400, 4500), ('right', 4500, 4700), ('there!', 4700, 5200),
    ('Run,', 6600, 7000), ('run,', 7050, 7400), ('RUN!', 7450, 8100),
]


def build(root, words=WORDS, duration_s=10.0):
    os.makedirs(os.path.join(root, 'compositions'), exist_ok=True)
    with open(os.path.join(root, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(INDEX.format(dur=('%g' % duration_s)))
    total = int(duration_s * 1000)
    words = [w for w in words if w[2] <= total]
    segs = []
    for n, (a, b) in enumerate([(0, 6), (6, 14), (14, len(words))], 1):
        chunk = words[a:b]
        if not chunk:
            continue
        segs.append({'id': f'seg-{n}', 'timelineIn': chunk[0][1], 'timelineOut': chunk[-1][2],
                     'words': [{'id': f'w-{a + i + 1}', 'text': t, 'srcStart': s, 'srcEnd': e,
                                'timelineIn': s, 'timelineOut': e} for i, (t, s, e) in enumerate(chunk)]})
    doc = {'schemaVersion': 1, 'rev': 1, 'source': {'path': 'public/source.mp4', 'duration': total},
           'tracks': [
               {'id': 't-av', 'type': 'av', 'speakerVolume': 1,
                'items': [{'id': 'pair-1', 'srcStart': 0, 'srcEnd': total, 'timelineIn': 0, 'timelineOut': total}]},
               {'id': 't-captions', 'type': 'captions', 'items': [{'id': 'section-1', 'segments': segs}]}]}
    with open(os.path.join(root, 'compositions', 'editing-script.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    return root


def official_scripts():
    """The installed official aip skill's scripts folder, or None. $AIP_SCRIPTS overrides the search."""
    env = os.environ.get('AIP_SCRIPTS')
    if env and os.path.exists(os.path.join(env, 'caption_cues.py')):
        return env
    pats = [os.path.expanduser('~/.claude/plugins/cache/ai-producer-plugins/aip/*/skills/aip/scripts'),
            os.path.expanduser('~/.claude/plugins/marketplaces/ai-producer-plugins/plugins/aip/skills/aip/scripts')]
    for pat in pats:
        found = sorted(glob.glob(pat))
        for d in reversed(found):
            if os.path.exists(os.path.join(d, 'caption_cues.py')) and os.path.exists(os.path.join(d, 'preflight.py')):
                return d
    return None
