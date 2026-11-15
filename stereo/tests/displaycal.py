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
import types
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
    """The reason of a failure never comes from apt's own wording, which follows the session's language: a lock is found by
    trying it, a failed download-only step is the network, anything later is apt's exit status."""

    def popen(self, lines, code):
        class Process:
            returncode = code
            stdout = io.StringIO(lines)

            def wait(self):
                return code
        return Process()

    def install(self, steps, language='en_US.UTF-8'):
        """apt_change for DisplayCAL with each step's (output, exit status); returns the commands run and the sentence raised."""
        ran = []

        def popen(command, **kwargs):
            ran.append(command)
            return self.popen(*steps[len(ran) - 1])
        apt = types.SimpleNamespace(Cache=lambda: {'displaycal': types.SimpleNamespace(candidate=types.SimpleNamespace(
            version='3.9.19-3', origins=[types.SimpleNamespace(origin='Debian', trusted=True)]))})
        saved = {key: os.environ.get(key) for key in ('LANG', 'LANGUAGE', 'LC_ALL')}
        os.environ.update(LANG=language, LANGUAGE=language.split('.')[0])
        os.environ.pop('LC_ALL', None)
        try:
            with patch.dict(sys.modules, apt=apt), patch.object(action, 'only_ours', return_value=set()), \
                    patch.object(action, 'held'), patch.object(action.subprocess, 'Popen', side_effect=popen), \
                    contextlib.redirect_stdout(io.StringIO()):
                try:
                    action.apt_change(ROW, 'install')
                    raised = None
                except RuntimeError as error:
                    raised = str(error)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return ran, raised

    def test_a_held_lock_is_busy_in_every_language(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'lock')
            holder = subprocess.Popen([sys.executable, '-c', 'import fcntl,sys,time;f=open(sys.argv[1],"a+");fcntl.lockf(f,fcntl.LOCK_EX);print("held",flush=True);time.sleep(30)', path],
                                      stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(holder.stdout.readline().strip(), 'held')
                for language, words in (('en_US.UTF-8', 'another program is using apt'), ('pt_BR.UTF-8', 'outro programa est'),
                                        ('de_DE.UTF-8', 'Ein anderes Programm verwendet apt')):
                    os.environ.update(LANG=language, LANGUAGE=language.split('.')[0])
                    with self.assertRaises(RuntimeError) as caught:
                        action.held(ROW, [str(Path(tmp) / 'absent'), path])
                    self.assertIn(words, str(caught.exception))
            finally:
                holder.kill()
                holder.wait()
                os.environ.update(LANG='en_US.UTF-8', LANGUAGE='en_US')
            action.held(ROW, [path])   # let go: the same lock is free now

    def test_a_free_lock_and_a_missing_file_raise_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            action.held(ROW, [str(Path(tmp) / 'absent'), str(Path(tmp) / 'free')])

    def test_the_download_comes_first_and_its_failure_is_the_network_in_any_language(self):
        portuguese = 'E: Falha ao buscar https://deb.debian.org/x  Falha temporária na resolução de nomes\n'
        for language, words in (('pt_BR.UTF-8', 'não foi possível baixar os pacotes'), ('de_DE.UTF-8', 'konnten nicht heruntergeladen werden'),
                                ('en_US.UTF-8', 'could not be downloaded')):
            ran, raised = self.install([(portuguese, 100)], language)
            self.assertEqual(len(ran), 1, 'the install step must not run after a failed download')
            self.assertIn('--download-only', ran[0])
            self.assertIn(words, raised)

    def test_an_install_failure_has_apts_exit_status_not_a_guess(self):
        ran, raised = self.install([('', 0), ('E: dpkg wurde unterbrochen\n', 100)], 'de_DE.UTF-8')
        self.assertEqual(len(ran), 2)
        self.assertNotIn('--download-only', ran[1])
        self.assertIn('apt-Exitcode 100', raised)

    def test_success_runs_both_steps_and_prints_apts_lines(self):
        ran, raised = self.install([('Fetched\n', 0), ('Setting up displaycal\n', 0)])
        self.assertEqual((len(ran), raised), (2, None))


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
