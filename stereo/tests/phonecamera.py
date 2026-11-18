#!/usr/bin/python3
"""Phone as a camera, a package entry of the Graphics, Others page (ORDER 25): the page says what the entry brings before the button
(apt's sizes), a refusal and a failed installation are said, the entry sits in Paweł's page in both trees, the app center depends on
nothing for it, and every required language has the sentence that names both programs and what the phone needs.
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
ROW = catalogue.entry('phonecamera')


def done(code=0, out='', err=''):
    return subprocess.CompletedProcess([], code, out, err)


class Row(unittest.TestCase):
    def test_the_row_is_a_package_entry_on_the_others_page_of_graphics(self):
        self.assertEqual((ROW['kind'], ROW['package'], ROW['section'], ROW['page'], ROW['key']),
                         ('apt', 'sparky-stereo-phone-camera', 'main', 'graphics-others.html', 'graoth'))
        self.assertTrue(ROW['sizes'])
        self.assertEqual(tools.declared(ROW), [])

    def test_the_protocol_key_reaches_the_row(self):
        self.assertEqual(mainpages.request('aptus://graoth_phonecamera'), (ROW, None))
        self.assertEqual(mainpages.request('aptus://debinst_phonecamera'), (ROW, 'install'))
        self.assertEqual(mainpages.request('aptus://debremo_phonecamera'), (ROW, 'remove'))

    def test_the_link_is_in_pawels_page_of_both_trees_once_and_the_page_is_one_line_to_change(self):
        for tree in ('8', '9'):
            page = (Path(__file__).resolve().parents[2] / tree / 'lib/sparky-aptus-appcenter/graphics-others.html').read_bytes().decode()
            self.assertEqual(page.count('aptus://graoth_phonecamera'), 1, tree)
            self.assertIn('Phone as a camera', page)
            self.assertIn('\r\n', page, 'the page keeps its line endings')

    def test_every_required_language_names_both_programs_and_what_the_phone_needs(self):
        for code in REQUIRED:
            texts = json.loads((SOURCE / 'lang' / (code + '.json')).read_text())
            note = texts.get('phonecamera_note')
            self.assertTrue(note, code)
            for word in ('DroidCam', 'scrcpy', 'Dev47Apps', 'Android 12', 'SHA-256', 'KDE Connect', 'Phone camera'):
                self.assertIn(word, note, (code, word))
        english = json.loads((SOURCE / 'lang/en.json').read_text())['phonecamera_note']
        for code in REQUIRED[1:]:
            self.assertNotEqual(json.loads((SOURCE / 'lang' / (code + '.json')).read_text())['phonecamera_note'], english, code)

    def test_the_app_center_depends_on_nothing_for_it(self):
        self.assertNotIn('tools', ROW)
        control = Path(__file__).resolve().parents[2] / 'debian/control'
        if control.exists():
            self.assertNotIn('v4l2loopback', control.read_text())
            self.assertNotIn('scrcpy', control.read_text())


class Page(unittest.TestCase):
    def page(self, state, problems=('', '')):
        with patch.object(mainpages, 'apt_state', return_value=state), patch.object(mainpages, 'problem_text', side_effect=lambda owner, key: problems[0] if key else problems[1]):
            return mainpages.render(ROW)

    def test_before_the_button_it_says_what_it_brings(self):
        sizes = ['Packages apt installs for this: 3, from Debian. Download: 4.1 MiB. Disk space added: 12.0 MiB.']
        html = self.page({'installed': False, 'visible': True, 'tools': {'text': sizes}, 'download': None, 'declared': []})
        self.assertIn(sizes[0], html)
        self.assertIn('href="aptus://debinst_phonecamera"', html)
        self.assertIn('Not installed', html)
        self.assertIn('DroidCam', html)
        self.assertIn('scrcpy', html)
        self.assertLess(html.index('Download: 4.1 MiB'), html.index('debinst_phonecamera'), 'the size is said before the button')

    def test_a_refusal_is_said_on_the_page(self):
        html = self.page({'installed': False, 'visible': True, 'tools': {'error': 'Phone as a camera cannot be installed. apt says: Unable to locate package scrcpy.'},
                          'download': None, 'declared': []})
        self.assertIn('Unable to locate package scrcpy', html)

    def test_an_installed_entry_offers_the_removal_and_no_sizes(self):
        html = self.page({'installed': True, 'visible': True, 'tools': None, 'download': None, 'declared': []})
        self.assertIn('href="aptus://debremo_phonecamera"', html)
        self.assertNotIn('debinst_', html)


if __name__ == '__main__':
    unittest.main()
