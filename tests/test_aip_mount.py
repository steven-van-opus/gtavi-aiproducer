import json, os, tempfile, unittest

import util
import aipfixture

mount = util.load('aip_mount')

HOST = ('<div class="visual-host clip" data-composition-id="captions-{n:02d}" data-title="Captions {n}" '
        'data-composition-src="compositions/captions-{n:02d}.html" data-start="{s}" data-duration="1" '
        'data-src-anchor="{s}" data-track-index="60" data-width="1080" data-height="1920"></div>')


class Mount(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.re = aipfixture.build(os.path.join(self.tmp.name, 'render-engine'))
        self.index = os.path.join(self.re, 'index.html')

    def tearDown(self):
        self.tmp.cleanup()

    def text(self):
        return util.read(self.index)

    def test_summary_lists_the_speaker_and_the_next_free_track(self):
        s = mount.summary(self.text())
        self.assertEqual(s['canvas'], ['1080', '1920'])
        self.assertEqual([c['kind'] for c in s['clips']], ['speaker', 'speaker'])
        self.assertEqual(s['tracks_used'], [0, 1])
        self.assertEqual(s['next_free_track'], 2)
        self.assertEqual(mount.next_free_track({0, 1, 19}), 22)      # 20, 21 are speaker zoom/filter tracks
        self.assertEqual(mount.next_free_track({0, 60, 900, 905}), 61)  # 900-907 are motion hosts

    def test_hosts_go_last_inside_the_stage(self):
        out, ids = mount.insert_hosts(self.text(), HOST.format(n=1, s=0) + '\n' + HOST.format(n=2, s=2))
        self.assertEqual(ids, ['captions-01', 'captions-02'])
        els = mount.scan(out)
        stage = mount.find_stage(els)
        inner = [e for e in mount.inside(stage, els) if e['depth'] == stage['depth'] + 1]
        self.assertEqual([e['attrs'].get('id') or e['attrs'].get('data-composition-id') for e in inner],
                         ['speaker', 'speaker-audio', 'captions-01', 'captions-02'])
        self.assertLess(out.index('captions-02'), out.index('<script>\n    window.__timelines'))
        # mounting the same id twice is refused, unless replaced
        with self.assertRaises(ValueError):
            mount.insert_hosts(out, HOST.format(n=2, s=3))
        out2, _ = mount.insert_hosts(out, HOST.format(n=2, s=3), replace=True)
        self.assertEqual(out2.count('data-composition-id="captions-02"'), 1)
        self.assertIn('data-start="3"', out2)

    def test_unmount_by_prefix(self):
        out, _ = mount.insert_hosts(self.text(), HOST.format(n=1, s=0) + HOST.format(n=2, s=2))
        back, removed = mount.remove_hosts(out, lambda cid: cid.startswith('captions-'))
        self.assertEqual(removed, ['captions-01', 'captions-02'])
        self.assertEqual(back, self.text())

    def test_bad_snippets_are_refused(self):
        with self.assertRaises(ValueError):
            mount.insert_hosts(self.text(), '<div class="caption">hi</div>')
        nested = ('<div class="visual-host clip" data-composition-id="a" data-composition-src="compositions/a.html">'
                  '<div class="visual-host clip" data-composition-id="b" data-composition-src="compositions/b.html"></div></div>')
        with self.assertRaises(ValueError):
            mount.insert_hosts(self.text(), nested)
        with self.assertRaises(ValueError):
            mount.insert_hosts('<html><body><div id="stage"></div></body></html>', HOST.format(n=1, s=0))

    def test_cli(self):
        hosts = os.path.join(self.tmp.name, 'hosts.html')
        with open(hosts, 'w') as f:
            f.write(HOST.format(n=1, s=0) + '\n')
        r = util.run_script('aip_mount.py', self.re, '--hosts', hosts, '--dry-run')
        self.assertEqual(json.loads(r.stdout)['mounted'], ['captions-01'])
        self.assertNotIn('captions-01', self.text())
        r = util.run_script('aip_mount.py', self.re, '--hosts', hosts)
        self.assertEqual(r.returncode, 0)
        self.assertIn('captions-01', self.text())
        self.assertEqual(json.loads(util.run_script('aip_mount.py', self.re, '--list').stdout)['next_free_track'], 61)
        r = util.run_script('aip_mount.py', self.re, '--unmount', 'captions-')
        self.assertEqual(json.loads(r.stdout)['unmounted'], ['captions-01'])


if __name__ == '__main__':
    unittest.main()
