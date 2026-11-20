import json, os, re, subprocess, sys, tempfile, unittest

import util
import aipfixture

cap = util.load('captions')

MOMENTS = {'ok': True, 'synced': False, 'moments': [
    {'id': 'captions-01', 'src': 'compositions/captions-01.html', 'start': 0.0, 'duration': 1.9, 'src_anchor': 12.5,
     'cues': [{'in': 0.0, 'out': 0.48, 'words': [['Chat,', 0.0, 0.42]]},
              {'in': 0.48, 'out': 1.9, 'words': [['look', 0.48, 0.7], ['at', 0.7, 0.8], ['<this>', 0.8, 1.7]]}]},
    {'id': 'captions-02', 'src': 'compositions/captions-02.html', 'start': 2.9, 'duration': 2.5, 'src_anchor': 15.4,
     'cues': [{'in': 0.0, 'out': 1.0, 'words': [['No', 0.0, 0.2], ['way', 0.2, 0.5], ['bro,', 0.5, 0.9]]},
              {'in': 1.0, 'out': 2.5, 'words': [['the', 1.0, 1.1], ['cops', 1.1, 1.5], ['&', 1.5, 1.6], ['run!', 1.6, 2.3]]}]}]}


def run(cues, render_engine, *args):
    path = os.path.join(os.path.dirname(render_engine), 'cues.json')
    with open(path, 'w') as f:
        json.dump(cues, f)
    return util.run_script('captions.py', path, render_engine, *args)


class Captions(unittest.TestCase):
    def test_every_look_follows_the_caption_contract(self):
        for look in ('pop', 'karaoke', 'single', 'plain'):
            with tempfile.TemporaryDirectory() as d:
                re_dir = os.path.join(d, 'render-engine')
                r = run(MOMENTS, re_dir, '--look', look)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                out = json.loads(r.stdout)
                self.assertEqual(out['files'], ['compositions/captions-01.html', 'compositions/captions-02.html'])
                for m in MOMENTS['moments']:
                    doc = util.read(os.path.join(re_dir, 'compositions', m['id'] + '.html'))
                    self.assertTrue(doc.startswith('<template>') and doc.rstrip().endswith('</template>'))
                    self.assertLess(len(doc.encode()), 64 * 1024)
                    # the root is bound exactly as the composition contract says
                    self.assertIn(f'document.querySelector(\'[data-composition-id="{m["id"]}"]\')', doc)
                    self.assertIn(f'window.__timelines["{m["id"]}"] = tl;', doc)
                    self.assertIn('gsap.timeline({ paused: true })', doc)
                    self.assertIn('@font-face', doc)
                    # every word is static text in the HTML, escaped
                    for c in m['cues']:
                        self.assertIn(f'data-in="{cap.fmt(c["in"])}" data-out="{cap.fmt(c["out"])}"', doc)
                    self.assertIn('&lt;this&gt;', doc) if m['id'] == 'captions-01' else self.assertIn('&amp;', doc)
                    for banned in ('build_captions', 'narrator', 'Math.random', 'Date.now', 'setTimeout', 'requestAnimationFrame'):
                        self.assertNotIn(banned, doc)
                    self.assertEqual(doc.count('<template>'), 1)
                    self.assertNotIn('<script', doc.split('</template>')[1])
                hosts = out['hosts_html'].splitlines()
                self.assertEqual(len(hosts), 2)
                self.assertIn('data-composition-src="compositions/captions-02.html"', hosts[1])
                self.assertIn('data-start="2.9" data-duration="2.5" data-src-anchor="15.4" data-track-index="60"', hosts[1])
                self.assertIn('data-width="1080" data-height="1920"', hosts[0])

    def test_words_carry_their_own_times_in_word_looks(self):
        with tempfile.TemporaryDirectory() as d:
            re_dir = os.path.join(d, 'render-engine')
            run(MOMENTS, re_dir, '--look', 'pop', '--emphasis', 'cops', '--alt-cues', 'captions-02:1')
            doc = util.read(os.path.join(re_dir, 'compositions', 'captions-02.html'))
            self.assertIn('<span class="w em" data-in="1.1" data-out="1.5">cops</span>', doc)
            self.assertIn('<div class="cue alt" data-in="0" data-out="1">', doc)
            self.assertEqual(len(re.findall(r'<span class="w', doc)), 7)
            self.assertIn('text-transform: uppercase', doc)

    def test_position_options(self):
        with tempfile.TemporaryDirectory() as d:
            re_dir = os.path.join(d, 'render-engine')
            run(MOMENTS, re_dir, '--seam-y', '668')
            self.assertIn('top: 668px;', util.read(os.path.join(re_dir, 'compositions', 'captions-01.html')))
            run(MOMENTS, re_dir, '--y', '0.7', '--look', 'plain')
            doc = util.read(os.path.join(re_dir, 'compositions', 'captions-01.html'))
            self.assertIn('top: 70.0%;', doc)
            self.assertIn('font: 700 64px/1.15 "Inter"', doc)

    def test_bad_input_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            re_dir = os.path.join(d, 'render-engine')
            self.assertEqual(run({'ok': False, 'code': 'editing_script_unreadable_workspace'}, re_dir).returncode, 2)
            bad = {'moments': [dict(MOMENTS['moments'][0], id='narrator-captions')]}
            self.assertEqual(run(bad, re_dir).returncode, 2)
            self.assertEqual(run(MOMENTS, re_dir, '--accent', 'gold').returncode, 2)
            self.assertEqual(run(MOMENTS, re_dir, '--alt-cues', 'captions-01').returncode, 2)

    def test_long_cues_and_ui_zones_warn(self):
        long = {'moments': [{'id': 'captions-01', 'start': 0, 'duration': 3, 'src_anchor': 0, 'cues': [
            {'in': 0, 'out': 3, 'words': [[w, i * 0.2, i * 0.2 + 0.2] for i, w in enumerate(
                'this is a very long caption line that keeps going and going past two lines'.split())]}]}]}
        with tempfile.TemporaryDirectory() as d:
            out = json.loads(run(long, os.path.join(d, 'render-engine'), '--y', '0.85').stdout)
            text = ' '.join(out['warnings'])
            self.assertIn('third line', text)
            self.assertIn('platform UI', text)


@unittest.skipUnless(aipfixture.official_scripts(), 'official AI Producer plugin (aip) not installed')
class OfficialHandoff(unittest.TestCase):
    """caption_cues.py (official) -> captions.py -> aip_mount.py -> preflight.py (official) must pass."""

    def test_round_trip_through_the_official_helpers(self):
        off = aipfixture.official_scripts()
        with tempfile.TemporaryDirectory() as d:
            re_dir = aipfixture.build(os.path.join(d, 'render-engine'))
            cues = subprocess.run([sys.executable, os.path.join(off, 'caption_cues.py'), re_dir, '--max-words', '3'],
                                  capture_output=True, text=True)
            self.assertEqual(cues.returncode, 0, cues.stdout + cues.stderr)
            data = json.loads(cues.stdout)
            self.assertTrue(data['ok'])
            self.assertGreaterEqual(len(data['moments']), 3)
            with open(os.path.join(d, 'cues.json'), 'w') as f:
                f.write(cues.stdout)
            hosts = os.path.join(d, 'hosts.html')
            r = util.run_script('captions.py', os.path.join(d, 'cues.json'), re_dir, '--seam-y', '668', '--hosts-out', hosts)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = util.run_script('aip_mount.py', re_dir, '--hosts', hosts)
            self.assertEqual(r.returncode, 0, r.stdout)
            os.makedirs(os.path.join(re_dir, 'public', 'fonts'))
            open(os.path.join(re_dir, 'public', 'fonts', 'anton-latin-400-normal.woff2'), 'wb').close()
            cmd = [sys.executable, os.path.join(off, 'preflight.py'), re_dir, '--sync-editing-script']
            for f in aipfixture.REMOTE:
                cmd += ['--remote-file', f]
            pf = subprocess.run(cmd, capture_output=True, text=True)
            verdict = json.loads(pf.stdout)
            self.assertTrue(verdict['ok'], pf.stdout)
            self.assertEqual(verdict['errors'], [])


if __name__ == '__main__':
    unittest.main()
