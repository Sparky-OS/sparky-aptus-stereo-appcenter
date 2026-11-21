#!/usr/bin/python3
"""A maker's program published as one archive (kind "tree" with "archive" in its pinned list): fetched once, checked against the
maker's SHA-256, unpacked (regular files and folders under its own top folder only), every listed file checked again, placed as a
tree is, removed as a tree is. Each failure says which one it is and leaves nothing installed.

No network: curl is replaced by a function that writes the bytes a fixture holds for the address it was given.
The red control of the checksum is the green case's archive with one byte changed."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
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
import vendortree

REQUIRED = ('en', 'pl', 'pt_BR', 'fr', 'de', 'es', 'ja', 'ko', 'zh_CN', 'zh_TW')
KEYS = ('tree_facts_archive', 'tree_no_room', 'tree_extract_failed', 'tree_not_ours')
BASE = 'https://www.example.org/downloads/'
FILE = 'thing-1.linux-x86_64.tar.xz'


def tar(members):
    """members: [(name, bytes or None for a folder, or ('link', target))] -> the bytes of a tar.xz."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:xz') as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            if data is None:
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                archive.addfile(info)
            elif isinstance(data, tuple):
                info.type, info.linkname = tarfile.SYMTYPE, data[1]
                archive.addfile(info)
            else:
                info.size, info.mode = len(data), 0o644
                archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


FILES = {'thing/thing': b'#!/bin/sh\nexit 0\n', 'thing/lib/a.so': b'lib', 'thing/lib/b.so': b'lib', 'thing/omni.ja': b'resources'}


def fixture(directory, archive=None, listed=None):
    """The maker's archive, its pinned list and the row; returns (row, address -> bytes)."""
    data = archive if archive is not None else tar([('thing', None), ('thing/lib', None)] + sorted(FILES.items()))
    listed = FILES if listed is None else listed
    files = [dict(src=name, dest=name.split('/', 1)[1], size=len(content), sha256=hashlib.sha256(content).hexdigest(),
                  mode='0755' if name == 'thing/thing' else '0644') for name, content in sorted(listed.items())]
    pinned = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(), file=FILE, root='thing')
    body = json.dumps(dict(format=1, id='thing', version='1', base=BASE, archive=pinned, files=files)).encode()
    (directory / 'vendor').mkdir(exist_ok=True)
    (directory / 'vendor' / 'thing.json').write_bytes(body)
    row = dict(id='thing', name='Thing', kind='tree', version='1', manifest='thing.json', manifest_sha256=hashlib.sha256(body).hexdigest(),
               prefix=str(directory / 'opt' / 'thing'), exec='thing', launcher={str(directory / 'bin-thing'): 'thing'}, min_glibc='2.17',
               licence=dict(name='MPL-2.0', holder='Maker'), size=len(data), url=BASE + FILE)
    return row, {BASE + FILE: data}


def fake_curl(served, exit_code=0, calls=None):
    def run(command, *args, **kwargs):
        if calls is not None:
            calls.append(command)
        if exit_code:
            return subprocess.CompletedProcess(command, exit_code)
        pairs = [(command[i + 1], command[i + 2]) for i, word in enumerate(command) if word == '--output']
        for output, address in pairs:
            Path(output).write_bytes(served[address])
        return subprocess.CompletedProcess(command, 0)
    return run


class Sentences(unittest.TestCase):
    def test_the_kinds_sentences_are_in_english_and_brazilian_portuguese_and_the_rest_are_listed(self):
        for code in ('en', 'pt_BR'):
            text = json.loads((common.LANGDIR / (code + '.json')).read_text())
            for key in KEYS:
                self.assertTrue(text.get(key, '').strip(), code + ' ' + key)
        pending = [code for code in REQUIRED if any(key not in json.loads((common.LANGDIR / (code + '.json')).read_text()) for key in KEYS)]
        # the eight others come from the translations lane (ORDER 70's table); until then they fall back to English
        print('waiting for their translation:', ' '.join(pending) or 'none', file=sys.stderr)


class Install(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='tree-archive-test-'))
        self.addCleanup(lambda: subprocess.run(['rm', '-rf', str(self.directory)]))
        patcher = patch.object(common, 'BASE', self.directory)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.said = []

    def run_change(self, row, served, operation='install', code=0, calls=None):
        with patch.object(vendortree.subprocess, 'run', fake_curl(served, code, calls)):
            vendortree.change(row, operation, say=self.said.append)

    def assertNothingInstalled(self, row):
        self.assertFalse(Path(row['prefix']).exists())
        self.assertFalse(Path(next(iter(row['launcher']))).is_symlink())
        self.assertEqual([p.name for p in (self.directory / 'opt').iterdir()] if (self.directory / 'opt').exists() else [], [])

    def test_green_fetched_once_checked_unpacked_placed_and_removed_exactly(self):
        row, served = fixture(self.directory)
        calls = []
        (self.directory / 'opt').mkdir()
        (self.directory / 'opt' / 'other').mkdir()
        self.run_change(row, served, calls=calls)
        base = Path(row['prefix'])
        self.assertEqual(len(calls), 1)
        self.assertTrue(vendortree.installed(row))
        self.assertEqual((base / 'thing').stat().st_mode & 0o777, 0o755)
        self.assertEqual((base / 'lib/b.so').read_bytes(), b'lib')
        self.assertEqual(sorted(str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()),
                         ['.aptus-managed', 'lib/a.so', 'lib/b.so', 'omni.ja', 'thing'])
        self.assertEqual(Path(next(iter(row['launcher']))).resolve(), (base / 'thing').resolve())
        facts = vendortree.facts(row)
        self.assertIn(FILE, facts)
        self.assertIn(hashlib.sha256(served[BASE + FILE]).hexdigest()[:16], facts)
        self.assertIn('MPL-2.0', facts)
        self.run_change(row, served, 'remove')
        self.assertFalse(base.exists())
        self.assertFalse(Path(next(iter(row['launcher']))).is_symlink())
        self.assertTrue((self.directory / 'opt' / 'other').is_dir())

    def test_red_the_archive_with_one_byte_changed_is_refused_and_nothing_is_installed(self):
        row, served = fixture(self.directory)
        data = bytearray(served[BASE + FILE])
        data[len(data) // 2] ^= 0xff
        served[BASE + FILE] = bytes(data)
        with self.assertRaisesRegex(RuntimeError, FILE.replace('.', r'\.') + '.*SHA-256'):
            self.run_change(row, served)
        self.assertNothingInstalled(row)

    def test_red_no_network_is_said_with_the_host_and_nothing_is_installed(self):
        row, served = fixture(self.directory)
        with self.assertRaisesRegex(RuntimeError, r'www\.example\.org.*curl exit 6'):
            self.run_change(row, served, code=6)
        self.assertNothingInstalled(row)

    def test_red_no_room_is_said_before_anything_is_downloaded(self):
        row, served = fixture(self.directory)
        calls = []
        with patch.object(vendortree.shutil, "disk_usage", return_value=vendortree.shutil._ntuple_diskusage(10 ** 6, 10 ** 6, 10)):
            with self.assertRaisesRegex(RuntimeError, 'needs .* free in'):
                self.run_change(row, served, calls=calls)
        self.assertEqual(calls, [])
        self.assertNothingInstalled(row)

    def test_red_an_archive_that_cannot_be_unpacked_is_said(self):
        row, served = fixture(self.directory, archive=b'not an archive at all')
        with self.assertRaisesRegex(RuntimeError, 'could not be unpacked'):
            self.run_change(row, served)
        self.assertNothingInstalled(row)

    def test_red_a_link_or_a_path_outside_the_top_folder_is_refused(self):
        for members in ([('thing', None)] + sorted(FILES.items()) + [('thing/evil', ('link', '/etc/passwd'))],
                        [('thing', None)] + sorted(FILES.items()) + [('thing/../evil', b'x')],
                        [('other', None), ('other/thing', b'x')] + sorted(FILES.items())):
            row, served = fixture(self.directory, archive=tar(members))
            with self.assertRaisesRegex(RuntimeError, 'could not be unpacked'):
                self.run_change(row, served)
            self.assertFalse(Path(row['prefix']).exists())

    def test_red_a_listed_file_missing_from_the_archive_is_refused(self):
        listed = dict(FILES, **{'thing/missing.so': b'gone'})
        row, served = fixture(self.directory, listed=listed)
        with self.assertRaisesRegex(RuntimeError, 'missing.so.*SHA-256'):
            self.run_change(row, served)
        self.assertNothingInstalled(row)

    def test_red_a_copy_the_person_placed_is_said_and_never_replaced(self):
        row, served = fixture(self.directory)
        Path(row['prefix']).mkdir(parents=True)
        (Path(row['prefix']) / 'mine').write_text('mine')
        with self.assertRaisesRegex(RuntimeError, 'did not install'):
            self.run_change(row, served)
        self.assertEqual((Path(row['prefix']) / 'mine').read_text(), 'mine')

    def test_an_archive_list_with_a_licence_file_to_fetch_alone_is_refused(self):
        row, served = fixture(self.directory)
        row['licence'] = dict(row['licence'], dest='LICENSE')
        with self.assertRaises(vendortree.Damaged):
            vendortree.listing(row)


if __name__ == '__main__':
    unittest.main()
