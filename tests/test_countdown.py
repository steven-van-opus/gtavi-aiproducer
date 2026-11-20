import json, os, subprocess, sys, tempfile, unittest

import util
import aipfixture

cd = util.load('countdown')


def plan_file(d, items, title='5 craziest GTA 6 stream moments'):
    p = os.path.join(d, 'plan.json')
    with open(p, 'w') as f:
        json.dump({'title': title, 'items': items}, f)
    return p


class Layout(unittest.TestCase):
    def test_items_play_from_the_highest_rank_and_land_frame_exact(self):
        with tempfile.TemporaryDirectory() as d:
            items = [{'rank': r, 'clip': f'c{r}.mp4', 'in': 1.0, 'out': 1.0 + dur, 'label': f'item {r}'}
                     for r, dur in ((1, 12.0), (3, 11.5), (2, 12.017), (5, 10.0), (4, 13.0))]
            plan = cd.load_plan(plan_file(d, items))
            self.assertEqual([it['rank'] for it in plan['items']], [5, 4, 3, 2, 1])
            infos = [{'duration': 30.0, 'has_audio': True, 'width': 1080, 'height': 1920}] * 5
            laid, total = cd.layout(plan, infos, fps=30)
            self.assertEqual(laid[0]['start'], 0.0)
            for a, b in zip(laid, laid[1:]):
                self.assertEqual(a['end'], b['start'])
            for it in laid:
                self.assertLess(abs(it['start'] * 30 - round(it['start'] * 30)), 0.05)  # starts on a frame
            self.assertEqual(laid[3]['frames'], 361)                       # 12.017 s -> 361 frames
            self.assertEqual(total, laid[-1]['end'])
            self.assertAlmostEqual(total, 58.5, delta=0.05)

    def test_bad_plans(self):
        with tempfile.TemporaryDirectory() as d:
            for items in ([{'rank': 1, 'clip': 'a.mp4', 'label': 'x'}],
                          [{'rank': 1, 'clip': 'a.mp4', 'label': 'x'}, {'rank': 1, 'clip': 'b.mp4', 'label': 'y'}],
                          [{'rank': 1, 'clip': 'a.mp4'}, {'rank': 2, 'clip': 'b.mp4', 'label': 'y'}]):
                with self.assertRaises(ValueError):
                    cd.load_plan(plan_file(d, items))
            plan = cd.load_plan(plan_file(d, [{'rank': 1, 'clip': 'a.mp4', 'label': 'x', 'in': 5, 'out': 3},
                                              {'rank': 2, 'clip': 'b.mp4', 'label': 'y'}]))
            with self.assertRaises(ValueError):
                cd.layout(plan, [{'duration': 10.0}] * 2)

    def test_command_concats_video_and_audio(self):
        items = [{'clip': 'a.mp4', 'in': 1.0, 'frames': 300}, {'clip': 'b.mp4', 'in': 0.0, 'frames': 330}]
        infos = [{'has_audio': True}, {'has_audio': False}]
        cmd = cd.build_cmd(items, infos, 'out.mp4', 30)
        g = cmd[cmd.index('-filter_complex') + 1]
        self.assertIn('concat=n=2:v=1:a=1[v][a]', g)
        self.assertIn('trim=end_frame=300', g)
        self.assertIn('anullsrc', ' '.join(cmd))            # silent input for the clip without audio
        self.assertIn('[2:a]', g)


@unittest.skipUnless(util.have('ffmpeg', 'ffprobe'), 'ffmpeg not installed')
class Build(unittest.TestCase):
    def test_build_and_cards(self):
        with tempfile.TemporaryDirectory() as d:
            a = util.make_video(os.path.join(d, 'a.mp4'), 1080, 1920, 3.0)
            b = util.make_video(os.path.join(d, 'b.mp4'), 1080, 1920, 3.0, audio=False)
            c = util.make_video(os.path.join(d, 'c.mp4'), 720, 1280, 3.0)
            p = plan_file(d, [{'rank': 3, 'clip': a, 'in': 0.5, 'out': 2.5, 'label': 'Cops at the pumps',
                               'streamer': 'Kai Cenat', 'platform': 'twitch', 'credit': '@KaiCenat'},
                              {'rank': 2, 'clip': b, 'label': 'Silent one', 'streamer': 'IShowSpeed', 'platform': 'youtube'},
                              {'rank': 1, 'clip': c, 'in': 1, 'out': 2, 'label': 'Small source <&>'}])
            out = os.path.join(d, 'out')
            r = util.run_script('countdown.py', 'build', p, out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            res = json.loads(r.stdout)
            self.assertEqual(res['size'], [1080, 1920])
            self.assertAlmostEqual(res['duration'], 6.0, delta=0.08)
            self.assertTrue(any('not 1080x1920' in w for w in res['warnings']))
            tl = json.loads(util.read(os.path.join(out, 'timeline.json')))
            self.assertEqual([i['rank'] for i in tl['items']], [3, 2, 1])
            self.assertEqual([i['start'] for i in tl['items']], [0.0, 2.0, 5.0])

            re_dir = aipfixture.build(os.path.join(d, 'render-engine'), duration_s=6.0)
            hosts = os.path.join(d, 'hosts.html')
            r = util.run_script('countdown.py', 'cards', os.path.join(out, 'timeline.json'), re_dir, '--seam-y', '668',
                                '--hosts-out', hosts)
            self.assertEqual(r.returncode, 0, r.stdout)
            cards = json.loads(r.stdout)
            self.assertEqual(len(cards['files']), 4)
            self.assertEqual([s['at_ms'] for s in cards['sfx_instants']], [1500, 2000, 5000])  # title holds the first 1.5 s
            doc = util.read(os.path.join(re_dir, 'compositions', 'countdown-1.html'))
            self.assertIn('SMALL SOURCE &lt;&amp;&gt;', doc)
            self.assertIn('top: 694px;', doc)
            self.assertIn('window.__timelines["countdown-1"] = tl;', doc)
            three = util.read(os.path.join(re_dir, 'compositions', 'countdown-3.html'))
            self.assertIn('@KaiCenat · Twitch', three)
            r = util.run_script('aip_mount.py', re_dir, '--hosts', hosts)
            self.assertEqual(r.returncode, 0, r.stdout)
            off = aipfixture.official_scripts()
            if off:
                os.makedirs(os.path.join(re_dir, 'public', 'fonts'))
                open(os.path.join(re_dir, 'public', 'fonts', 'anton-latin-400-normal.woff2'), 'wb').close()
                cmd = [sys.executable, os.path.join(off, 'preflight.py'), re_dir, '--sync-editing-script']
                for f in aipfixture.REMOTE:
                    cmd += ['--remote-file', f]
                pf = subprocess.run(cmd, capture_output=True, text=True)
                self.assertTrue(json.loads(pf.stdout)['ok'], pf.stdout)


if __name__ == '__main__':
    unittest.main()
