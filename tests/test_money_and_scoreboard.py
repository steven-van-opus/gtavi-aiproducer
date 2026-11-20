import csv, json, os, tempfile, unittest

import util

cm = util.load('campaign_math')
sb = util.load('scoreboard')


class CampaignMath(unittest.TestCase):
    def test_rate_card_reality_check(self):
        # 810 clips under $1/1K, $10 minimum, $500 cap, 10% fee (the reality check in our money notes)
        r = cm.cpm(1.0, [(3000, 770), (50000, 30), (1000000, 10)], minimum=10, cap=500, fee=0.10)
        self.assertEqual(r['clips'], 810)
        self.assertEqual(r['views'], 13810000)
        self.assertEqual(r['naive'], 13810.0)
        self.assertEqual(r['gross'], 6500.0)
        self.assertEqual(r['net'], 5850.0)
        self.assertEqual([row['why'] for row in r['rows']], ['below the minimum: $0', 'paid at the rate', 'capped'])

    def test_clip_pay_edges(self):
        self.assertEqual(cm.clip_pay(9999, 1.0, minimum=10), 0.0)
        self.assertEqual(cm.clip_pay(10000, 1.0, minimum=10), 10.0)
        self.assertEqual(cm.clip_pay(400000, 1.0, cap=400), 400.0)
        self.assertEqual(cm.clip_pay(2000000, 1.0, cap=400), 400.0)
        self.assertAlmostEqual(cm.clip_pay(100000, 0.35, minimum=35), 35.0)

    def test_pool_and_target(self):
        p = cm.pool(10000, 100_000_000, 1_000_000, fee=0.10)
        self.assertEqual((p['gross'], p['net'], p['effective_per_1k']), (100.0, 90.0, 0.1))
        t = cm.target(10000, 1.0, fee=0.10)
        self.assertEqual(t['paid_views_needed'], 11111111)
        self.assertEqual(t['per_day_30'], 370370)

    def test_cli_always_prints_the_disclaimer(self):
        for args in (['cpm', '--rate', '1', '--views', '50000x3'], ['pool', '--budget', '5000', '--pool-views', '1e6', '--views', '1e4'],
                     ['target', '--net', '1000', '--rate', '2']):
            r = util.run_script('campaign_math.py', *args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('Illustrative math, not a promise. Most clips earn $0.', r.stdout)
        self.assertEqual(util.run_script('campaign_math.py', 'cpm', '--rate', '1', '--views', 'lots').returncode, 2)
        self.assertEqual(util.run_script('campaign_math.py', 'cpm', '--rate', '1', '--fee', '10', '--views', '1x1').returncode, 2)


class Scoreboard(unittest.TestCase):
    def test_add_update_report_rules(self):
        with tempfile.TemporaryDirectory() as d:
            board = os.path.join(d, 'board.csv')
            self.assertEqual(util.run_script('scoreboard.py', 'init', board).returncode, 0)
            self.assertEqual(util.run_script('scoreboard.py', 'init', board).returncode, 2)
            data = [('m01', 'countdown', 'question', 100000), ('m02', 'countdown', 'question', 120000),
                    ('m03', 'countdown', 'stakes', 90000), ('m04', 'single', 'stakes', 5000), ('m05', 'single', 'stakes', 6000),
                    ('m06', 'single', 'question', 7000), ('m07', 'reaction', 'stakes', 30000)]
            for cid, fmt, hook, views in data:
                r = util.run_script('scoreboard.py', 'add', board, '--clip-id', cid, '--streamer', 'Kai Cenat', '--platform', 'tiktok',
                                    '--format', fmt, '--hook', hook, '--caption-look', 'pop', '--length', '31',
                                    '--campaign', 'Example pool')
                self.assertEqual(r.returncode, 0, r.stderr)
                r = util.run_script('scoreboard.py', 'update', board, cid, '--views-24h', str(views),
                                    '--approved', 'n' if cid in ('m04', 'm05') else 'y')
                self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(util.run_script('scoreboard.py', 'add', board, '--clip-id', 'm01', '--platform', 'tiktok').returncode, 2)
            self.assertEqual(util.run_script('scoreboard.py', 'update', board, 'nope', '--views-24h', '1').returncode, 2)
            self.assertEqual(util.run_script('scoreboard.py', 'update', board, 'm01', '--views-24h', 'many').returncode, 2)
            with open(board, newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 7)
            self.assertEqual(rows[0]['views_24h'], '100000')
            rep = util.run_script('scoreboard.py', 'report', board).stdout
            self.assertIn('Median views_24h: 30,000', rep)
            self.assertIn('Campaign approvals: 5/7', rep)
            out = os.path.join(d, 'LEARNED_RULES.md')
            r = util.run_script('scoreboard.py', 'rules', board, '--out', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            text = util.read(out)
            self.assertIn('format = **countdown**', text.split('## Do less')[0])
            self.assertIn('format = **single**', text.split('## Do less')[1])
            self.assertIn('(no campaign under 50% approval)', text)

    def test_rules_with_no_numbers(self):
        r, overall = sb.rules([{'clip_id': 'x'}])
        self.assertIsNone(overall)
        self.assertIn('No numbers yet.', sb.rules_md(r, overall, 'views_24h', 1, 3))
        self.assertEqual(sb.length_bucket({'length_s': '31'}), '20-35s')


if __name__ == '__main__':
    unittest.main()
