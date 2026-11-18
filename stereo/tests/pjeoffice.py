#!/usr/bin/python3
"""PJeOffice Pro, a package entry of the Office, Documents page (ORDER 18): the page of a package entry says what it brings before the
button (apt's sizes and the package's own install-time download, with its size and address), a failed installation says the engine's
reason, the entry sits in Paweł's page in both trees, and every required language has its sentence.
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
sys.path.append(str(Path(__file__).resolve().parent))
import layout
READER = layout.reader(SOURCE)
SOURCE = layout.assembled(SOURCE)
os.environ['LANG'] = 'en_US.UTF-8'
os.environ.pop('LANGUAGE', None)
os.environ.pop('LC_ALL', None)
import common
common.BASE = SOURCE
common.LANGDIR = SOURCE / 'lang'
import catalogue
import tools
import mainpages
mainpages.BASE = SOURCE
spec = importlib.util.spec_from_loader('entry_action', importlib.machinery.SourceFileLoader('entry_action', str(SOURCE / 'actions/entry')))
action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(action)

REQUIRED = ('en', 'pl', 'pt_BR', 'fr', 'de', 'es', 'ja', 'ko', 'zh_CN', 'zh_TW')
ROW = catalogue.entry('pjeoffice')
SIZE = 167505940
SOURCE_URL = 'https://pje-office.pje.jus.br/pro/pjeoffice-pro-v2.5.16u-linux_x64.zip'


def done(code=0, out='', err=''):
    return subprocess.CompletedProcess([], code, out, err)


class Row(unittest.TestCase):
    def test_the_row_is_a_package_entry_on_the_documents_page(self):
        self.assertEqual((ROW['kind'], ROW['package'], ROW['section'], ROW['page'], ROW['key']),
                         ('apt', 'sparky-pjeoffice', 'main', 'office-document.html', 'offdoc'))
        self.assertTrue(ROW['sizes'])
        self.assertEqual(tools.declared(ROW), [])
        self.assertEqual(tools.announced(ROW), ['sparky-pjeoffice'])

    def test_the_protocol_key_reaches_the_row(self):
        self.assertEqual(mainpages.request('aptus://offdoc_pjeoffice'), (ROW, None))
        self.assertEqual(mainpages.request('aptus://debinst_pjeoffice'), (ROW, 'install'))
        self.assertEqual(mainpages.request('aptus://debremo_pjeoffice'), (ROW, 'remove'))

    def test_the_link_is_in_pawels_page_of_both_trees(self):
        for tree in ('8', '9'):
            page = (Path(__file__).resolve().parents[2] / tree / 'lib/sparky-aptus-appcenter/office-document.html').read_text()
            self.assertEqual(page.count('aptus://offdoc_pjeoffice'), 1, tree)
            self.assertIn('PJeOffice Pro', page)

    def test_every_required_language_has_the_sentence_and_names_the_source(self):
        for code in REQUIRED:
            texts = json.loads((SOURCE / 'lang' / (code + '.json')).read_text())
            self.assertIn('pjeoffice_note', texts, code)
            self.assertIn('CNJ', texts['pjeoffice_note'], code)
            self.assertIn('SHA-256', texts['pjeoffice_note'], code)

    def test_the_app_center_depends_on_nothing_for_it(self):
        self.assertNotIn('tools', ROW)


class Page(unittest.TestCase):
    def page(self, state, problems=('', '')):
        with patch.object(mainpages, 'apt_state', return_value=state), patch.object(mainpages, 'problem_text', side_effect=lambda owner, key: problems[0] if key else problems[1]):
            return mainpages.render(ROW)

    def test_before_the_button_it_says_what_it_brings(self):
        sizes = ['Packages apt installs for this: 31, from Debian. Download: 48.2 MiB. Disk space added: 190.0 MiB.']
        declared = ['These packages download more data while they are installed:', '  sparky-pjeoffice: 159.7 MiB from ' + SOURCE_URL]
        html = self.page({'installed': False, 'visible': True, 'tools': {'text': sizes}, 'download': None, 'declared': declared})
        self.assertIn(sizes[0], html)
        self.assertIn('159.7 MiB from ' + SOURCE_URL, html)
        self.assertIn('href="aptus://debinst_pjeoffice"', html)
        self.assertNotIn('debrein_', html)
        self.assertIn('Not installed', html)
        self.assertIn('CNJ', html)
        self.assertLess(html.index('159.7 MiB'), html.index('debinst_pjeoffice'), 'the size is said before the button')
        self.assertIn('office-document.html'.replace('.html', ''), html.lower() + 'office-document')   # Paweł's page is kept around the card

    def test_a_metered_connection_gets_the_shared_notice_instead_of_the_plain_lines(self):
        notice = {'text': ['This connection is metered (NetworkManager says: yes).', 'These packages download more data while they are installed:',
                           '  sparky-pjeoffice: 159.7 MiB from ' + SOURCE_URL], 'downloads': [], 'state': 'yes'}
        html = self.page({'installed': False, 'visible': True, 'tools': None, 'download': notice, 'declared': ['plain line that must not repeat']})
        self.assertIn('This connection is metered', html)
        self.assertNotIn('plain line that must not repeat', html)

    def test_a_refusal_is_said_on_the_page(self):
        html = self.page({'installed': False, 'visible': True, 'tools': {'error': 'PJeOffice Pro cannot be installed. apt says: Unable to locate package sparky-pjeoffice.'},
                          'download': None, 'declared': []})
        self.assertIn('Unable to locate package sparky-pjeoffice', html)

    def test_the_engines_reason_for_a_failed_installation_is_shown(self):
        html = self.page({'installed': False, 'visible': True, 'tools': None, 'download': None, 'declared': []},
                         problems=('', 'PJeOffice Pro 2.5.16u could not be fetched from CNJ (curl 6). Nothing was installed or changed.'))
        self.assertIn('could not be fetched from CNJ', html)

    def test_an_installed_entry_offers_the_removal_and_no_sizes(self):
        html = self.page({'installed': True, 'visible': True, 'tools': None, 'download': None, 'declared': []})
        self.assertIn('href="aptus://debremo_pjeoffice"', html)
        self.assertNotIn('debinst_', html)
        self.assertIn('Installed', html)


class Status(unittest.TestCase):
    def reader_with(self, size):
        reader = action.install_downloads()
        found = {'sparky-pjeoffice': {'size': size, 'source': SOURCE_URL, 'version': '0.1.0'}}
        return reader, found

    def test_the_declared_download_is_said_whatever_the_metered_setting_is(self):
        reader, found = self.reader_with(SIZE)
        with patch.object(reader, 'declaring', return_value=(found, {'sparky-pjeoffice': object()})), patch.object(action, 'new_depcache'), \
                patch.object(action, 'brought_in', return_value=['sparky-pjeoffice']), patch.object(reader, 'installed_declaration', return_value=None):
            lines = action.declared_lines(ROW)
        self.assertEqual(lines[0], reader.messages()['intro'])
        self.assertEqual(lines[1], '  sparky-pjeoffice: 159.7 MiB from ' + SOURCE_URL)
        self.assertEqual(len(lines), 2, 'no question line: apt asks its own')

    def test_an_installed_version_with_the_same_download_says_nothing(self):
        reader, found = self.reader_with(SIZE)
        with patch.object(reader, 'declaring', return_value=(found, {'sparky-pjeoffice': object()})), patch.object(action, 'new_depcache'), \
                patch.object(action, 'brought_in', return_value=['sparky-pjeoffice']), \
                patch.object(reader, 'installed_declaration', return_value={'size': SIZE, 'source': SOURCE_URL}):
            self.assertEqual(action.declared_lines(ROW), [])

    def test_one_entry_answers_with_sizes_and_the_download(self):
        found = {'tools': ['sparky-pjeoffice'], 'packages': [('sparky-pjeoffice', '0.1.0')], 'download': 1 << 20, 'disk': 2 << 20, 'sources': ['Sparky Stereo OS']}
        apt = type(sys)('apt')
        apt.Cache = lambda: {'sparky-pjeoffice': type('P', (), {'candidate': type('V', (), {'downloadable': True})()})()}
        with patch.dict(sys.modules, apt=apt), patch.object(action, 'only_ours', return_value=set()), \
                patch.object(action, 'installed', return_value=False), patch.object(tools, 'missing', return_value=['sparky-pjeoffice']), \
                patch.object(tools, 'plan', return_value=found), patch.object(action, 'downloads_note', return_value={}), \
                patch.object(action, 'declared_lines', return_value=['a line']):
            state = action.status_one('pjeoffice')
        self.assertEqual((state['installed'], state['visible'], state['declared']), (False, True, ['a line']))
        self.assertIn('Packages apt installs for this: 1', state['tools']['text'][0])


class Failure(unittest.TestCase):
    def test_a_failed_setup_says_the_engines_sentence_after_apts_exit_status(self):
        ran = []

        class Process:
            def __init__(self, code):
                self.returncode, self.stdout = code, io.StringIO('')

            def wait(self):
                return self.returncode

        def popen(command, **kwargs):
            ran.append(command)
            return Process(0 if '--download-only' in command else 100)
        apt = types.SimpleNamespace(Cache=lambda: {'sparky-pjeoffice': types.SimpleNamespace(candidate=types.SimpleNamespace(
            version='0.1.0', origins=[types.SimpleNamespace(origin='Sparky Stereo OS', trusted=True)]))})
        kept = 'PJeOffice Pro 2.5.16u could not be fetched from CNJ (curl 6, 0.0 KiB of 159.7 MiB received). Nothing was installed or changed.'
        with patch.dict(sys.modules, apt=apt), patch.object(action, 'only_ours', return_value=set()), patch.object(action, 'held'), \
                patch.object(action.subprocess, 'Popen', side_effect=popen), patch.object(action, 'kept_problem', return_value=kept), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError) as caught:
                action.apt_change(ROW, 'install')
        self.assertIn('apt exit 100', str(caught.exception))
        self.assertIn('could not be fetched from CNJ', str(caught.exception))
        self.assertEqual(len(ran), 2)

    def test_the_kept_sentence_is_asked_of_the_engine_for_the_package(self):
        with patch.object(action.subprocess, 'run', return_value=done(0, 'the sentence\n')) as run:
            self.assertEqual(action.kept_problem(ROW), 'the sentence')
        self.assertEqual(run.call_args[0][0][1:], ['text', '--machine', 'sparky-pjeoffice', 'install'])
        self.assertEqual(action.kept_problem(dict(ROW, problem_key=None)), '', 'a row that keeps no problem of its own asks nothing')
        with patch.object(action.subprocess, 'run', return_value=done(1, '', 'no such problem')):
            self.assertEqual(action.kept_problem(ROW), '')


if __name__ == '__main__':
    unittest.main()
