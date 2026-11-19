#!/usr/bin/python3
"""A maker's program fetched from the maker (kind "tree"): the pinned file list, the checks, the failures said, removal.

No network: curl is replaced by a function that writes the bytes a fixture holds for the address it was given.
The control of each failure case is the green case beside it."""
import hashlib
import json
from pathlib import Path
import string
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
sys.path.append(str(Path(__file__).resolve().parent))
import layout
layout.reader(SOURCE)
import common
SOURCE = layout.assembled(SOURCE)
sys.path.insert(0, str(SOURCE))
common.BASE = SOURCE
common.LANGDIR = SOURCE / 'lang'
import catalogue
import vendortree

REQUIRED = ('en', 'pl', 'pt_BR', 'fr', 'de', 'es', 'ja', 'ko', 'zh_CN', 'zh_TW')
KEYS = ('tree_facts', 'tree_checksum_failed', 'tree_manifest_failed', 'tree_licence_title', 'tree_no_bluetooth',
        'tree_removed', 'tree_installed', 'download_note_tree', 'sensecom_note', 'sensecom_comment', 'senseglove_api_note')
ROWS = ('sensecom', 'senseglove-api-libs')


class Pinned(unittest.TestCase):
    def test_every_vendor_row_names_the_file_list_it_was_pinned_with(self):
        for name in ROWS:
            row = catalogue.entry(name)
            self.assertEqual(row['kind'], 'tree')
            found = vendortree.listing(row)
            self.assertEqual(row['size'], vendortree.download_size(row))
            self.assertTrue(found['base'].startswith('https://raw.githubusercontent.com/Adjuvo/'))
            self.assertIn(found['commit'], found['base'])
            self.assertEqual(len(found['commit']), 40)
            self.assertEqual(found['id'], name)
            self.assertIn(row['licence']['dest'], [each['dest'] for each in found['files']])

    def test_sensecom_keeps_the_makers_updater_and_fetches_its_identical_file_once(self):
        found = vendortree.listing(catalogue.entry('sensecom'))
        dests = [each['dest'] for each in found['files']]
        self.assertIn('update/sensecom-update.x86_64', dests)
        self.assertEqual(dict((each['dest'], each['mode']) for each in found['files'])['SenseCom.x86_64'], '0755')
        self.assertEqual(len(vendortree.unique(found)), len(found['files']) - 168)
        self.assertEqual(next(each for each in found['files'] if each['dest'] == 'UnityPlayer.so')['sha256'],
                         next(each for each in found['files'] if each['dest'] == 'update/UnityPlayer.so')['sha256'])

    def test_a_changed_file_list_is_refused_before_anything_is_fetched(self):
        row = dict(catalogue.entry('sensecom'))
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'vendor').mkdir()
            text = (SOURCE / 'vendor' / row['manifest']).read_text().replace('"0755"', '"0644"', 1)
            (Path(directory) / 'vendor' / row['manifest']).write_text(text)
            with patch.object(common, 'BASE', Path(directory)):
                with self.assertRaisesRegex(vendortree.Damaged, 'SenseCom'):
                    vendortree.listing(row)
                self.assertFalse(vendortree.installed(row))

    def test_a_path_that_leaves_the_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'vendor').mkdir()
            body = json.dumps(dict(format=1, id='x', base='https://example.org/', files=[
                dict(src='a', dest='../escape', size=1, sha256='0' * 64, mode='0644')])).encode()
            (Path(directory) / 'vendor' / 'x.json').write_bytes(body)
            row = dict(id='x', name='X', manifest='x.json', manifest_sha256=hashlib.sha256(body).hexdigest())
            with patch.object(common, 'BASE', Path(directory)):
                with self.assertRaises(vendortree.Damaged):
                    vendortree.listing(row)

    def test_the_new_sentences_are_in_the_ten_languages(self):
        english = json.loads((SOURCE / 'lang/en.json').read_text())

        def fields(text):
            return sorted(each[1] for each in string.Formatter().parse(text) if each[1])
        for code in REQUIRED:
            texts = json.loads((SOURCE / 'lang' / (code + '.json')).read_text())
            for key in KEYS:
                self.assertTrue(texts.get(key), (code, key))
                self.assertEqual(fields(texts[key]), fields(english[key]), (code, key))
                if code != 'en':
                    self.assertNotEqual(texts[key], english[key], (code, key))

    def test_the_menu_entry_has_its_comment_in_every_language_with_one_exec_line(self):
        text = vendortree.desktop_file(catalogue.entry('sensecom'))
        self.assertEqual(text.count('\nExec='), 1)
        self.assertIn('Exec=/opt/sensecom/SenseCom.x86_64\n', text)
        for code in REQUIRED[1:]:
            self.assertIn('Comment[%s]=' % code, text)

    def test_the_facts_name_the_size_the_address_the_pin_and_the_licence(self):
        text = vendortree.facts(catalogue.entry('sensecom'))
        for part in ('101.5 MiB', 'raw.githubusercontent.com', 'dbfd4266f040', '638f76fd9ec191dc', 'MIT', 'SenseGlove B.V.'):
            self.assertIn(part, text)


def fixture(directory, flaw=None):
    """A tiny maker: three files (two with the same bytes), a licence, a pinned list; returns (row, address -> bytes)."""
    blobs = {'LICENSE': b'MIT licence text\n', 'bin/run': b'#!/bin/sh\nexit 0\n', 'lib/a.so': b'lib', 'lib/b.so': b'lib'}
    base = 'https://raw.githubusercontent.com/Maker/Thing/' + 'a' * 40 + '/'
    files = [dict(src='src/' + name, dest=name, size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                  mode='0755' if name == 'bin/run' else '0644') for name, data in sorted(blobs.items())]
    body = json.dumps(dict(format=1, id='thing', version='1', commit='a' * 40, base=base, files=files)).encode()
    (directory / 'vendor').mkdir()
    (directory / 'vendor' / 'thing.json').write_bytes(body)
    served = {base + 'src/' + name: data for name, data in blobs.items()}
    if flaw == 'bytes':
        served[base + 'src/bin/run'] = b'#!/bin/sh\nrm -rf ~\n'
    root = directory / 'opt'
    row = dict(id='thing', name='Thing', version='1', manifest='thing.json', manifest_sha256=hashlib.sha256(body).hexdigest(),
               prefix=str(root / 'thing'), launcher={str(directory / 'bin-thing'): 'bin/run'}, min_glibc='2.17',
               licence=dict(name='MIT', holder='Maker', dest='LICENSE'), size=0)
    return row, served


def fake_curl(served, exit_code=0):
    def run(command, *args, **kwargs):
        if exit_code:
            return subprocess.CompletedProcess(command, exit_code)
        pairs = [(command[i + 1], command[i + 2]) for i, word in enumerate(command) if word == '--output']
        for output, address in pairs:
            Path(output).write_bytes(served[address])
        return subprocess.CompletedProcess(command, 0)
    return run


class Install(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='tree-test-'))
        self.addCleanup(lambda: subprocess.run(['rm', '-rf', str(self.directory)]))
        patcher = patch.object(common, 'BASE', self.directory)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.said = []

    def run_change(self, row, served, operation='install', code=0):
        with patch.object(vendortree.subprocess, 'run', fake_curl(served, code)):
            vendortree.change(row, operation, say=self.said.append)

    def test_green_the_files_are_checked_and_placed_with_their_modes_and_the_licence_is_shown_first(self):
        row, served = fixture(self.directory)
        self.run_change(row, served)
        base = Path(row['prefix'])
        self.assertTrue(vendortree.installed(row))
        self.assertEqual((base / 'bin/run').stat().st_mode & 0o777, 0o755)
        self.assertEqual((base / 'lib/b.so').read_bytes(), b'lib')
        self.assertEqual(Path(next(iter(row['launcher']))).resolve(), (base / 'bin/run').resolve())
        self.assertTrue(self.said[1].startswith('MIT licence text') or 'MIT licence text' in ''.join(self.said[:3]))
        self.assertTrue(any('Thing is installed in' in line for line in self.said))
        self.run_change(row, served, 'remove')
        self.assertFalse(base.exists())
        self.assertFalse(vendortree.installed(row))

    def test_red_a_file_with_other_bytes_is_refused_and_nothing_is_installed(self):
        row, served = fixture(self.directory, flaw='bytes')
        with self.assertRaisesRegex(RuntimeError, 'bin/run.*SHA-256'):
            self.run_change(row, served)
        self.assertFalse(Path(row['prefix']).exists())
        self.assertFalse(Path(next(iter(row['launcher']))).exists())

    def test_red_no_network_is_said_with_the_host_and_curls_exit_and_nothing_is_installed(self):
        row, served = fixture(self.directory)
        with self.assertRaisesRegex(RuntimeError, r'raw\.githubusercontent\.com.*curl exit 6'):
            self.run_change(row, served, code=6)
        self.assertFalse(Path(row['prefix']).exists())

    def test_a_folder_that_is_not_ours_is_never_replaced(self):
        row, served = fixture(self.directory)
        Path(row['prefix']).mkdir(parents=True)
        (Path(row['prefix']) / 'mine.txt').write_text('mine')
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            self.run_change(row, served)
        self.assertEqual((Path(row['prefix']) / 'mine.txt').read_text(), 'mine')

    def test_a_file_changed_after_the_installation_is_not_installed_any_more(self):
        row, served = fixture(self.directory)
        self.run_change(row, served)
        (Path(row['prefix']) / 'lib/a.so').write_bytes(b'lib!')
        self.assertFalse(vendortree.installed(row))

    def test_no_bluetooth_adapter_is_said(self):
        row, served = fixture(self.directory)
        row['bluetooth'] = True
        with patch.object(vendortree, 'adapter', return_value=False):
            self.assertEqual(len(vendortree.hints(row)), 1)
            self.run_change(row, served)
        self.assertTrue(any('no Bluetooth adapter' in line for line in self.said))
        with patch.object(vendortree, 'adapter', return_value=True):
            self.assertEqual(vendortree.hints(row), [])

    def test_the_old_glibc_is_said_before_anything_is_fetched(self):
        row, served = fixture(self.directory)
        row['min_glibc'] = '99.0'
        with self.assertRaisesRegex(RuntimeError, '99.0'):
            self.run_change(row, served)
        self.assertFalse(Path(row['prefix']).exists())


if __name__ == '__main__':
    unittest.main()
