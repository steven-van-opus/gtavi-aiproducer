#!/usr/bin/env python3
"""Mount moment hosts into an AI Producer index.html: last inside the #stage root, after every other moment.

AI Producer's composition contract wants each editable moment as a host div inside the root
(<div id="stage" data-composition-id="finecut-root" ...>), and caption moments after every other moment on a
track no other moment uses. This edits a local copy of render-engine/index.html (fetched with
get_workspace_file) so you do not hand-edit HTML.

Usage:
  python3 -I aip_mount.py RENDER_ENGINE --list
  python3 -I aip_mount.py RENDER_ENGINE --hosts HOSTS.html [--replace] [--dry-run]
  python3 -I aip_mount.py RENDER_ENGINE --unmount PREFIX [--dry-run]

--list     root canvas and duration, every clip and host in the root, the tracks in use and the next free one
           (tracks 20 and 21 are speaker zoom/filter effects, 900-907 motion hosts: never handed out)
--hosts    insert the host divs from HOSTS.html (captions.py --hosts-out, countdown.py cards ...). A host whose
           data-composition-id is already mounted is refused unless --replace.
--unmount  remove every host whose data-composition-id starts with PREFIX, e.g. `captions-` before a recut
           (AI Producer refuses a cut change while caption moments are mounted)
"""
import argparse, json, os, re, sys
from html.parser import HTMLParser

RESERVED = {20, 21} | set(range(900, 908))
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class _Scan(HTMLParser):
    """Records every element with its absolute start/end offsets in the source text."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.line_starts = [0]
        for m in re.finditer('\n', text):
            self.line_starts.append(m.end())
        self.elements, self.stack = [], []

    def _abs(self):
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self._abs()
        end_of_tag = start + len(self.get_starttag_text())
        el = {'tag': tag, 'attrs': dict(attrs), 'start': start, 'open_end': end_of_tag, 'end': None,
              'depth': len(self.stack), 'close_start': None}
        self.elements.append(el)
        if tag not in VOID:
            self.stack.append(el)
        else:
            el['end'] = end_of_tag

    def handle_startendtag(self, tag, attrs):
        start = self._abs()
        end = start + len(self.get_starttag_text())
        self.elements.append({'tag': tag, 'attrs': dict(attrs), 'start': start, 'open_end': end, 'end': end,
                              'depth': len(self.stack), 'close_start': end})

    def handle_endtag(self, tag):
        pos = self._abs()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                el = self.stack[i]
                el['close_start'] = pos
                el['end'] = self.text.index('>', pos) + 1
                del self.stack[i:]
                return


def scan(text):
    s = _Scan(text)
    s.feed(text)
    s.close()
    return s.elements


def find_stage(elements):
    stages = [e for e in elements if e['tag'] == 'div' and e['attrs'].get('id') == 'stage']
    if len(stages) != 1:
        raise ValueError('index.html needs exactly one <div id="stage">')
    st = stages[0]
    if st['attrs'].get('data-composition-id') != 'finecut-root':
        raise ValueError('the #stage root must carry data-composition-id="finecut-root"')
    if st['close_start'] is None:
        raise ValueError('the #stage root is never closed')
    return st


def inside(stage, elements):
    return [e for e in elements if e is not stage and stage['open_end'] <= e['start'] < stage['close_start']]


def summary(text):
    els = scan(text)
    st = find_stage(els)
    rows, used = [], set()
    for e in inside(st, els):
        cls = (e['attrs'].get('class') or '').split()
        if 'clip' not in cls:
            continue
        a = e['attrs']
        ti = a.get('data-track-index')
        if ti is not None and re.match(r'^-?\d+$', ti):
            used.add(int(ti))
        rows.append({'tag': e['tag'], 'id': a.get('id') or a.get('data-composition-id'),
                     'kind': ('speaker' if 'speaker-clip' in cls or a.get('id') in ('speaker', 'speaker-audio') else
                              'effect' if a.get('data-aip-effect') else 'moment' if 'visual-host' in cls else 'clip'),
                     'title': a.get('data-title'), 'start': a.get('data-start'), 'duration': a.get('data-duration'),
                     'track': int(ti) if ti and re.match(r'^-?\d+$', ti) else None})
    return {'canvas': [st['attrs'].get('data-width'), st['attrs'].get('data-height')],
            'duration': st['attrs'].get('data-duration'), 'clips': rows, 'tracks_used': sorted(used),
            'next_free_track': next_free_track(used)}


def next_free_track(used):
    n = max([t for t in used if t < 900] + [0]) + 1
    while n in RESERVED or n in used:
        n += 1
    return n


def parse_hosts(snippet):
    els = scan(snippet)
    hosts = [e for e in els if e['depth'] == 0]
    for e in hosts:
        a = e['attrs']
        if e['tag'] != 'div' or 'visual-host' not in (a.get('class') or '').split() or not a.get('data-composition-id'):
            raise ValueError('every top-level element in the hosts file must be <div class="visual-host clip" '
                             'data-composition-id=...>')
        if any(x['depth'] > 0 and 'data-composition-src' in x['attrs'] for x in els):
            raise ValueError('a host may not contain another host (nested_composition_host)')
    return [(e['attrs']['data-composition-id'], snippet[e['start']:e['end']]) for e in hosts]


def remove_hosts(text, predicate):
    els = scan(text)
    st = find_stage(els)
    doomed = [e for e in inside(st, els) if e['tag'] == 'div' and 'visual-host' in (e['attrs'].get('class') or '').split()
              and predicate(e['attrs'].get('data-composition-id') or '')]
    removed = []
    for e in sorted(doomed, key=lambda x: x['start'], reverse=True):
        a, b = e['start'], e['end']
        line_a = text.rfind('\n', 0, a) + 1
        if text[line_a:a].strip() == '' and text[b:text.find('\n', b) if text.find('\n', b) != -1 else len(text)].strip() == '':
            nl = text.find('\n', b)
            a, b = line_a, (nl + 1 if nl != -1 else len(text))
        text = text[:a] + text[b:]
        removed.append(e['attrs'].get('data-composition-id'))
    return text, sorted(removed)


def insert_hosts(text, snippet, replace=False):
    new = parse_hosts(snippet)
    els = scan(text)
    st = find_stage(els)
    mounted = {e['attrs'].get('data-composition-id') for e in inside(st, els)
               if 'visual-host' in (e['attrs'].get('class') or '').split()}
    clash = sorted(cid for cid, _ in new if cid in mounted)
    if clash and not replace:
        raise ValueError(f'already mounted: {", ".join(clash)} (pass --replace to swap them)')
    if clash:
        text, _ = remove_hosts(text, lambda cid: cid in set(clash))
        els = scan(text)
        st = find_stage(els)
    at = st['close_start']
    line_start = text.rfind('\n', 0, at) + 1
    indent_close = text[line_start:at] if text[line_start:at].strip() == '' else ''
    indent = indent_close + '  '
    block = ''.join(f'{indent}{html_}\n' for _, html_ in new)
    if indent_close or text[line_start:at] == '':
        text = text[:line_start] + block + text[line_start:]
    else:
        text = text[:at] + '\n' + block + text[at:]
    return text, [cid for cid, _ in new]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('render_engine')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--list', action='store_true')
    g.add_argument('--hosts', default=None, help='file holding the host divs to mount')
    g.add_argument('--unmount', default=None, metavar='PREFIX')
    ap.add_argument('--replace', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    index = os.path.join(a.render_engine, 'index.html')
    try:
        with open(index, encoding='utf-8') as f:
            text = f.read()
        if a.list:
            print(json.dumps(summary(text), indent=1))
            return 0
        if a.hosts:
            with open(a.hosts, encoding='utf-8') as f:
                snippet = f.read()
            out, ids = insert_hosts(text, snippet, a.replace)
            action = {'mounted': ids}
        else:
            if not a.unmount:
                raise ValueError('--unmount needs a non-empty prefix')
            out, ids = remove_hosts(text, lambda cid: cid.startswith(a.unmount))
            action = {'unmounted': ids}
    except (ValueError, OSError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}))
        return 2
    if not a.dry_run:
        with open(index + '.part', 'w', encoding='utf-8') as f:
            f.write(out)
        os.replace(index + '.part', index)
    action.update({'ok': True, 'dry_run': a.dry_run, 'next_free_track': summary(out)['next_free_track']})
    print(json.dumps(action, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
