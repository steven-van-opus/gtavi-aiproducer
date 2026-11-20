"""Repo consistency: manifests, skills, README, AI Producer tool names and the copy rules this plugin promises."""
import json, os, re, unittest

import util

AIP_TOOLS = {  # the AI Producer MCP tools as Claude Code lists them (mcp__plugin_aip_ai-producer__<name>)
    'add_music', 'add_sound_effects', 'build_captions', 'cancel_task', 'commit_workspace', 'enhance_voice', 'find_broll',
    'finish_project', 'frame_speaker', 'get_chat_history', 'get_editing_preset', 'get_export_url', 'get_motion_asset',
    'get_pricing', 'get_project', 'get_project_asset', 'get_reference_preset', 'get_task', 'get_transcript', 'get_view_url',
    'get_web_assignment', 'get_workspace_file', 'list_motion_assets', 'list_project_assets', 'list_projects',
    'list_reference_presets', 'list_sound_effects', 'list_versions', 'list_workspace', 'materialize_motion_asset',
    'place_sound_effects', 'present_choices', 'record_choices', 'resolve_selection', 'restore_version',
    'save_editing_preset', 'send_feedback', 'sign_upload', 'sign_workspace_upload', 'start_export', 'start_link_download',
    'start_project_from_attachment', 'start_transcribe_project', 'wait_task'}
NEVER_CALL = {'build_captions', 'add_sound_effects', 'save_editing_preset'}   # the official aip skill forbids these
BANNED_COPY = [r'up to \$\d', r'while you sleep', r'autopilot', r'get rich', r'passive income', r'guaranteed',
               r'millionaire', r'100% free', r'free forever']


def skills():
    return sorted(d for d in os.listdir(util.SKILLS) if os.path.isdir(os.path.join(util.SKILLS, d)))


def frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(':')
        fm[k.strip()] = v.strip().strip('"')
    return fm


def all_markdown():
    out = {}
    for root, dirs, files in os.walk(util.ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__')]
        for f in files:
            if f.endswith('.md'):
                p = os.path.join(root, f)
                out[os.path.relpath(p, util.ROOT)] = util.read(p)
    return out


class Manifests(unittest.TestCase):
    def test_plugin_and_marketplace_agree(self):
        plugin = json.loads(util.read(os.path.join(util.ROOT, '.claude-plugin', 'plugin.json')))
        market = json.loads(util.read(os.path.join(util.ROOT, '.claude-plugin', 'marketplace.json')))
        self.assertEqual(plugin['name'], 'gtavi-aiproducer')
        self.assertEqual(market['name'], 'gtavi-aiproducer')
        entry = market['plugins'][0]
        self.assertEqual(len(market['plugins']), 1)
        self.assertEqual(entry['name'], plugin['name'])
        self.assertEqual(entry['version'], plugin['version'])
        self.assertEqual(entry['source'], './')
        self.assertIn('aip@ai-producer-plugins', plugin['dependencies'])
        self.assertIn('ai-producer-plugins', market['allowCrossMarketplaceDependenciesOn'])
        self.assertTrue(os.path.exists(os.path.join(util.ROOT, plugin['icon'])))
        self.assertIn(str(len(skills())), entry['description'])


class Skills(unittest.TestCase):
    def test_count_is_in_range_and_advertised_everywhere(self):
        n = len(skills())
        self.assertTrue(12 <= n <= 16, n)
        readme = util.read(os.path.join(util.ROOT, 'README.md'))
        self.assertIn(f'skills: {n}', readme)
        self.assertIn(f'{n} skills in one install', readme)
        self.assertIn(f'>{n}</text>', util.read(os.path.join(util.ROOT, 'docs', 'badges', 'skills.svg')))
        self.assertIn(f'>{n}</b> Skills In One Install', util.read(os.path.join(util.ROOT, 'docs', 'skills-banner.html')))

    def test_frontmatter(self):
        for name in skills():
            text = util.read(os.path.join(util.SKILLS, name, 'SKILL.md'))
            fm = frontmatter(text)
            self.assertIsNotNone(fm, name)
            self.assertEqual(fm.get('name'), name)
            self.assertRegex(name, r'^[a-z0-9]+(-[a-z0-9]+)*$')
            self.assertTrue(40 <= len(fm.get('description', '')) <= 1024, f'{name}: description length')
            self.assertGreater(len(text), 800, f'{name} is too thin')

    def test_readme_lists_every_skill(self):
        readme = util.read(os.path.join(util.ROOT, 'README.md'))
        for name in skills():
            self.assertIn(f'(skills/{name}/SKILL.md)', readme, name)

    def test_referenced_scripts_exist(self):
        for name in skills():
            text = util.read(os.path.join(util.SKILLS, name, 'SKILL.md'))
            for script in re.findall(r'\.\./\.\./scripts/([\w.]+)', text):
                self.assertTrue(os.path.exists(os.path.join(util.SCRIPTS, script)), f'{name} -> {script}')
            for script in re.findall(r'\b([a-z_]+\.py)\b', text):
                official = {'caption_cues.py', 'preflight.py', 'upload_batch.py', 'editing_script_sync.py'}
                self.assertTrue(script in official or os.path.exists(os.path.join(util.SCRIPTS, script)), f'{name} -> {script}')

    def test_skill_cross_references_exist(self):
        names = set(skills())
        for name in names:
            text = util.read(os.path.join(util.SKILLS, name, 'SKILL.md'))
            for ref in re.findall(r'`([a-z]+(?:-[a-z]+)*)`', text):
                if ref in ('pick', 'cut', 'find', 'scan', 'verify', 'prep', 'report', 'add', 'update', 'rules', 'init'):
                    continue
                if re.fullmatch(r'(aip|aip-[a-z-]+)', ref) and ref.startswith('aip-') and ref not in names:
                    self.fail(f'{name} names a skill `{ref}` that does not exist here (official ones are aip:aip-...)')


class AIPToolNames(unittest.TestCase):
    def test_every_tool_reference_is_real_and_forbidden_ones_are_only_forbidden(self):
        md = all_markdown()
        backticked = re.compile(r'`(' + '|'.join(sorted(AIP_TOOLS, key=len, reverse=True)) + r')`')
        for path, text in md.items():
            for tool in re.findall(r'mcp__plugin_aip_ai-producer__(\w+)', text):
                if tool == 'tool':
                    continue
                self.assertIn(tool, AIP_TOOLS, f'{path}: unknown AI Producer tool {tool}')
            for line in text.splitlines():
                for tool in NEVER_CALL:
                    if tool in line:
                        self.assertRegex(line.lower(), r'never|not|refus|forbid', f'{path}: {tool} outside a "never" line: {line}')
            self.assertTrue(set(backticked.findall(text)) <= AIP_TOOLS)

    def test_scripts_name_the_right_tools(self):
        vc = util.read(os.path.join(util.SCRIPTS, 'vodcut.py'))
        for tool in re.findall(r'mcp__plugin_aip_ai-producer__(\w+)', vc):
            self.assertIn(tool, AIP_TOOLS)


class Copy(unittest.TestCase):
    def test_no_banned_money_language(self):
        for path, text in all_markdown().items():
            for pat in BANNED_COPY:
                for m in re.finditer(pat, text, re.I):
                    start = text.rfind('\n\n', 0, m.start())
                    end = text.find('\n\n', m.end())
                    para = text[start + 1 if start >= 0 else 0:end if end >= 0 else len(text)]
                    self.assertRegex(para.lower(), r'never|not |no |don.t|instead', f'{path}: "{m.group(0)}" in: {para}')

    def test_readme_shape(self):
        readme = util.read(os.path.join(util.ROOT, 'README.md'))
        for anchor in ('#quick-start', '#make-money', '#skills', '#clip-rules', '#scripts'):
            self.assertIn(f']({anchor})', readme)
        for heading in ('## Quick start', '## How it works', '## Skills', '## Make money', '## Clip rules', '## Scripts',
                        '## FAQ', '## Disclaimer'):
            self.assertIn(heading, readme)
        for cmd in ('claude plugin install aip@ai-producer-plugins', '/plugin marketplace add [OWNER]/gtavi-aiproducer',
                    '/plugin install gtavi-aiproducer@gtavi-aiproducer'):
            self.assertIn(cmd, readme)
        self.assertIn('Illustrative math, not a promise. Most clips earn $0.', readme)
        self.assertIn('Not affiliated with or endorsed by Rockstar Games', readme)
        for img in re.findall(r'src="(docs/[^"]+)"', readme):
            self.assertTrue(os.path.exists(os.path.join(util.ROOT, img)), img)

    def test_no_secrets_in_the_repo(self):
        # assembled from parts so this file never matches itself
        pat = re.compile('(' + '|'.join(['sk-[A-Za-z0-9]{20,}', 'AKIA[0-9A-Z]{16}', 'ghp_[A-Za-z0-9]{30,}',
                                          'xox[bp]-[A-Za-z0-9-]{20,}', '-----BEGIN [A-Z ]*PRIVATE ' + 'KEY-----',
                                          'X-Amz-' + 'Signature=', 'Goog' + '-Signature=']) + ')')
        for root, dirs, files in os.walk(util.ROOT):
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__')]
            for f in files:
                if f.endswith(('.png', '.jpg')):
                    continue
                self.assertIsNone(pat.search(util.read(os.path.join(root, f))), os.path.join(root, f))


if __name__ == '__main__':
    unittest.main()
