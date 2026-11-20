"""Smoke test: every script answers --help with exit 0 and its usage, under python3 -I (stdlib only)."""
import os, shutil, subprocess, unittest

import util

PY_SCRIPTS = {
    'ytfrag.py': [[]], 'scan_vod.py': [[]], 'scan_frags.py': [[]], 'rank_windows.py': [[]], 'framesheet.py': [[]],
    'frame.py': [[], ['probe'], ['grid'], ['plan'], ['still'], ['compose']],
    'vodcut.py': [[], ['scan'], ['find'], ['verify'], ['cut'], ['prep'], ['report']],
    'aip_prep.py': [[], ['check'], ['sign-args'], ['record']],
    'captions.py': [[]], 'aip_mount.py': [[]],
    'countdown.py': [[], ['build'], ['cards']],
    'campaign_math.py': [[], ['cpm'], ['pool'], ['target']],
    'scoreboard.py': [[], ['init'], ['add'], ['update'], ['report'], ['rules']],
    'find_streams.py': [[], ['search'], ['channel'], ['vod']],
    'bleep.py': [[], ['words'], ['find'], ['apply']],
}


class Help(unittest.TestCase):
    def test_every_python_script_has_help(self):
        listed = sorted(f for f in os.listdir(util.SCRIPTS) if f.endswith('.py'))
        self.assertEqual(listed, sorted(PY_SCRIPTS), 'add new scripts to this smoke test')
        for name, variants in PY_SCRIPTS.items():
            for sub in variants:
                r = util.run_script(name, *(sub + ['--help']), timeout=60)
                self.assertEqual(r.returncode, 0, f'{name} {sub}: {r.stderr[:300]}')
                self.assertTrue(('usage' in r.stdout.lower()) or ('Usage' in r.stdout), f'{name} {sub} printed no usage')

    def test_every_python_script_is_stdlib_only(self):
        allowed_local = {'rank_windows', 'scan_vod'}
        import ast, sys
        std = set(sys.stdlib_module_names)
        for name in PY_SCRIPTS:
            tree = ast.parse(util.read(os.path.join(util.SCRIPTS, name)))
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                       [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
                for m in mods:
                    top = m.split('.')[0]
                    self.assertTrue(top in std or top in allowed_local, f'{name} imports {m}')

    @unittest.skipUnless(shutil.which('node'), 'node not installed')
    def test_render_mjs_help(self):
        r = subprocess.run(['node', os.path.join(util.SCRIPTS, 'render.mjs'), '--help'], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('render.mjs still', r.stdout)


if __name__ == '__main__':
    unittest.main()
