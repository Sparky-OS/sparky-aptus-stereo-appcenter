#!/usr/bin/python3
"""DisplayCAL, an entry that is offered and not installed (ORDER 575): the sizes of its own program said first with the
requirement beside them, apt's refusals and failures said in sentences, the single-entry status the Info Centre asks.
No package manager and no network: every command is a recorded stand-in."""
import importlib.machinery
import importlib.util
import io
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SOURCE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
READER = Path(os.environ.get('SPARKY_INSTALL_DOWNLOADS_LIB') or SOURCE.parents[1] / 'packages/sparky-stereo-apt/install-downloads')
os.environ['SPARKY_INSTALL_DOWNLOADS_LIB'] = str(READER)
if (READER / 'lang').is_dir():
    os.environ['SPARKY_INSTALL_DOWNLOADS_LANG'] = str(READER / 'lang')
os.environ['LANG'] = 'en_US.UTF-8'
os.environ.pop('LANGUAGE', None)
os.environ.pop('LC_ALL', None)
import common
common.BASE = SOURCE
common.LANGDIR = SOURCE / 'lang'
import catalogue
import tools
spec = importlib.util.spec_from_loader('entry_action', importlib.machinery.SourceFileLoader('entry_action', str(SOURCE / 'actions/entry')))
action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(action)

SIMULATION = '''NOTE: This is only a simulation!
Inst argyll-ref (3.5.0+repack-1 Debian:testing [all])
Inst argyll (3.5.0+repack-1 Debian:testing [amd64])
Inst displaycal (3.9.19-3 Debian:testing [all])
Conf displaycal (3.9.19-3 Debian:testing [all])
'''
REQUIRED = ('en', 'pl', 'pt_BR', 'fr', 'de', 'es', 'ja', 'ko', 'zh_CN', 'zh_TW')
NEW = ('displaycal_note', 'program_unavailable', 'apt_busy', 'apt_network', 'apt_failed')
ROW = catalogue.entry('displaycal')


def done(code=0, out='', err=''):
    return subprocess.CompletedProcess([], code, out, err)


class Entry(unittest.TestCase):
    def test_the_row_is_offered_not_depended_on(self):
        self.assertEqual((ROW['kind'], ROW['package'], ROW['section']), ('apt', 'displaycal', 'tools'))
        self.assertEqual(tools.declared(ROW), [])
        self.assertEqual(tools.announced(ROW), ['displaycal'])

    def test_every_required_language_has_every_new_sentence(self):
        for code in REQUIRED:
            texts = json.loads((SOURCE / 'lang' / (code + '.json')).read_text())
            for key in NEW:
                self.assertIn(key, texts, (code, key))
            self.assertIn('DisplayCAL', texts['displaycal_note'])

    def test_sizes_are_simulated_as_the_action_installs(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return done(0, SIMULATION)
        with patch.object(tools, 'present', return_value=False), patch.object(tools.subprocess, 'run', side_effect=run), \
                patch.object(tools, 'sizes', return_value=(14701896, 29338 * 1024)):
            found = tools.plan(ROW)
        self.assertEqual(calls[0][:3], [tools.APT, '-s', '--no-remove'])
        self.assertNotIn('--no-install-recommends', calls[0])
        self.assertEqual(found['sources'], ['Debian'])
        self.assertEqual(len(found['packages']), 3)
        said = tools.lines(ROW, found)
        self.assertEqual(len(said), 1)
        self.assertIn('Packages apt installs for this: 3, from Debian.', said[0])
        self.assertNotIn('tools', said[0].lower().replace('tools_', ''))

    def test_a_tool_row_still_says_its_tools(self):
        vinci = catalogue.entry('vinci')
        found = {'tools': ['podman'], 'packages': [('podman', '1')], 'download': 1, 'disk': 1, 'sources': ['Debian']}
        self.assertEqual(len(tools.lines(vinci, found)), 3)

    def test_an_installed_program_is_not_simulated(self):
        with patch.object(tools, 'present', return_value=True), patch.object(tools.subprocess, 'run') as run:
            self.assertIsNone(tools.plan(ROW))
        run.assert_not_called()

    def test_a_package_the_sources_lack_is_refused_with_apts_reason(self):
        with patch.object(tools, 'present', return_value=False), \
                patch.object(tools.subprocess, 'run', return_value=done(100, '', "E: Unable to locate package displaycal\n")):
            with self.assertRaisesRegex(tools.Refused, r'DisplayCAL cannot be installed\. apt says: Unable to locate package displaycal\. Update the package lists'):
                tools.plan(ROW)


class Failures(unittest.TestCase):
    def failing(self, lines, code=100):
        class Process:
            returncode = code
            stdout = io.StringIO(lines)

            def wait(self):
                return code
        return Process()

    def say(self, lines, code=100):
        with patch.object(action.subprocess, 'Popen', return_value=self.failing(lines, code)), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError) as caught:
                action.run_said(ROW, ['apt-get'])
        return str(caught.exception)

    def test_busy(self):
        self.assertIn('another program is using apt', self.say('E: Could not get lock /var/lib/dpkg/lock-frontend. It is held by process 42\n'))

    def test_no_network(self):
        self.assertIn('could not be downloaded', self.say('E: Failed to fetch https://deb.debian.org/x  Temporary failure resolving\n'))

    def test_anything_else_has_a_code(self):
        self.assertIn('apt exit 100', self.say('E: dpkg was interrupted\n'))

    def test_success_prints_apts_lines_and_raises_nothing(self):
        class Good:
            returncode = 0
            stdout = io.StringIO('Setting up displaycal\n')

            def wait(self):
                return 0
        out = io.StringIO()
        with patch.object(action.subprocess, 'Popen', return_value=Good()), contextlib.redirect_stdout(out):
            action.run_said(ROW, ['apt-get'])
        self.assertIn('Setting up displaycal', out.getvalue())


class Status(unittest.TestCase):
    def test_one_entry_answers_with_its_sizes(self):
        found = {'tools': ['displaycal'], 'packages': [('displaycal', '1')], 'download': 14701896, 'disk': 1 << 20, 'sources': ['Debian']}
        apt = type(sys)('apt')
        apt.Cache = lambda: {'displaycal': type('P', (), {'candidate': type('V', (), {'downloadable': True})()})()}
        with patch.dict(sys.modules, apt=apt), patch.object(action, 'only_ours', return_value=set()), \
                patch.object(action, 'installed', return_value=False), patch.object(tools, 'missing', return_value=['displaycal']), \
                patch.object(tools, 'plan', return_value=found):
            state = action.status_one('displaycal')
        self.assertFalse(state['installed'])
        self.assertTrue(state['visible'])
        self.assertIn('Download: 14.0 MiB', state['tools']['text'][0])

    def test_a_package_no_source_offers_is_not_visible(self):
        apt = type(sys)('apt')
        apt.Cache = lambda: {}
        with patch.dict(sys.modules, apt=apt), patch.object(action, 'only_ours', return_value=set()), patch.object(action, 'installed', return_value=False):
            state = action.status_one('displaycal')
        self.assertFalse(state['visible'])
        self.assertIsNone(state['tools'])


if __name__ == '__main__':
    unittest.main()
