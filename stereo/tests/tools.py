#!/usr/bin/python3
"""The tools an entry needs: declared once, planned with apt's simulation, installed by the entry's action, refusals said.
No package manager and no network: every command is a recorded stand-in."""
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import string
import subprocess
import sys
import tempfile
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
import appimage
spec = importlib.util.spec_from_loader('entry_action', importlib.machinery.SourceFileLoader('entry_action', str(SOURCE / 'actions/entry')))
action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(action)

SIMULATION = '''NOTE: This is only a simulation!
Reading package lists...
Inst libsubid5 (1:4.19.0-2 Debian:testing [amd64])
Inst passt (0.0~git20260120-1 Debian:testing [amd64])
Inst libfuse3-4 [3.18.2-1] (3.18.3-1 Debian:testing, Debian-Security:testing-security [amd64])
Inst podman (5.8.6+ds1-3 Debian:testing [amd64])
Inst distrobox (1.8.2.5-1 Debian:testing [all])
Inst bsdextrautils (2.42-3 Debian:testing [amd64])
Conf podman (5.8.6+ds1-3 Debian:testing [amd64])
'''
REQUIRED = ('en', 'pl', 'pt_BR', 'fr', 'de', 'es', 'ja', 'ko', 'zh_CN', 'zh_TW')
NEW = ('tools_needed', 'tools_sizes', 'tools_total', 'tools_unavailable', 'tools_download_failed', 'tools_failed',
       'download_failed', 'tools_kept')


def done(code=0, out='', err=''):
    return subprocess.CompletedProcess([], code, out, err)


class Declaration(unittest.TestCase):
    def test_each_entry_declares_its_own_tools(self):
        self.assertEqual(tools.declared(catalogue.entry('vinci')), ['bsdextrautils', 'distrobox', 'fuse3', 'podman'])
        self.assertEqual(tools.declared(catalogue.entry('kamlynk')), ['fuse3'])
        # an entry kind declares what every entry of that kind needs: the stereo catalogue stays as published
        self.assertEqual(tools.declared(catalogue.entry('slimevr')), ['flatpak'])
        for name in ('bino', 'slimevr-driver', 'syncthing'):
            self.assertEqual(tools.declared(catalogue.entry(name)), [])
        self.assertNotIn('dependencies', json.dumps(catalogue.entries()))

    def test_the_new_sentences_are_in_the_ten_languages(self):
        english = json.loads((SOURCE / 'lang/en.json').read_text())

        def fields(text):
            return sorted(each[1] for each in string.Formatter().parse(text) if each[1])
        for code in REQUIRED:
            texts = json.loads((SOURCE / 'lang' / (code + '.json')).read_text())
            for key in NEW:
                self.assertTrue(texts.get(key), (code, key))
                self.assertEqual(fields(texts[key]), fields(english[key]), (code, key))
                if code != 'en':
                    self.assertNotEqual(texts[key], english[key], (code, key))


class Plan(unittest.TestCase):
    row = catalogue.entry('vinci')

    def test_nothing_is_planned_or_run_when_the_tools_are_present(self):
        with patch.object(tools, 'present', return_value=True), patch.object(tools.subprocess, 'run') as run:
            self.assertIsNone(tools.plan(self.row))
            run.assert_not_called()
            self.assertEqual(tools.lines(self.row, None), [])

    def test_only_the_missing_tools_are_simulated_and_apt_gives_the_sizes(self):
        have = {'fuse3'}
        with patch.object(tools, 'present', side_effect=lambda name: name in have), \
             patch.object(tools.subprocess, 'run', return_value=done(0, SIMULATION)) as run, \
             patch.object(tools, 'sizes', return_value=(31 * 1024 * 1024, 120 * 1024 * 1024)) as sizes:
            found = tools.plan(self.row)
        self.assertEqual(run.call_args.args[0], ['/usr/bin/apt-get', '-s', '--no-remove', '--no-install-recommends',
                                                 '--no-allow-unauthenticated', 'install', 'bsdextrautils', 'distrobox', 'podman'])
        self.assertEqual(found['tools'], ['bsdextrautils', 'distrobox', 'podman'])
        self.assertEqual(len(found['packages']), 6)
        self.assertIn(('libfuse3-4', '3.18.3-1'), found['packages'])
        self.assertEqual(sizes.call_args.args[0], found['packages'])
        self.assertEqual(found['sources'], ['Debian', 'Debian-Security'])
        said = tools.lines(self.row, found)
        self.assertIn('bsdextrautils, distrobox, podman', said[0])
        self.assertNotIn('fuse3', said[0])
        self.assertIn('6 packages', said[1])
        self.assertIn('31.0 MiB to download', said[1])
        self.assertIn('120.0 MiB', said[1])
        # the program's own download and the tools' together
        self.assertIn(tools.human(31 * 1024 * 1024 + self.row['size']), said[2])
        self.assertEqual(tools.download(found), {'package': 'bsdextrautils, distrobox, podman', 'version': '',
                                                 'size': 31 * 1024 * 1024, 'source': 'Debian, Debian-Security'})

    def test_a_tool_apt_cannot_install_is_refused_with_apts_reason(self):
        with patch.object(tools, 'present', return_value=False), \
             patch.object(tools.subprocess, 'run', return_value=done(100, '', 'E: Unable to locate package podman\n')):
            with self.assertRaises(tools.Refused) as refused:
                tools.plan(self.row)
        text = str(refused.exception)
        for part in ('Vinci', 'podman', 'Unable to locate package podman', 'apt update', 'Nothing was changed'):
            self.assertIn(part, text)

    def test_a_tool_the_simulation_does_not_install_is_refused(self):
        with patch.object(tools, 'present', return_value=False), \
             patch.object(tools.subprocess, 'run', return_value=done(0, 'Inst fuse3 (3.18.3-1 Debian:testing [amd64])\n')):
            with self.assertRaisesRegex(tools.Refused, 'bsdextrautils, distrobox, podman'):
                tools.plan(self.row)


class Ensure(unittest.TestCase):
    row = catalogue.entry('vinci')
    found = {'tools': ['distrobox', 'podman'], 'packages': [('podman', '5'), ('distrobox', '1')], 'download': 1, 'disk': 1,
             'sources': ['Debian']}
    auto = ()

    def run_with(self, results, after=True):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return results.pop(0)
        with tempfile.TemporaryDirectory() as tmp, patch.object(tools, 'RECORDS', Path(tmp) / 'tools'), \
             patch.object(tools.subprocess, 'run', side_effect=run), patch.object(tools, 'present', return_value=after), \
             patch.object(tools, 'automatic', side_effect=lambda name: name in self.auto):
            try:
                tools.ensure(self.row, self.found)
                error = None
            except tools.Refused as refused:
                error = str(refused)
            recorded = tools.brought('vinci')
        return calls, error, recorded

    def test_archives_first_then_the_install_and_the_record(self):
        calls, error, recorded = self.run_with([done(), done()])
        self.assertIsNone(error)
        options = ['--no-remove', '--no-install-recommends', '--no-allow-unauthenticated', 'install', 'distrobox', 'podman']
        self.assertEqual(calls, [['/usr/bin/apt-get', '-y', '--download-only', *options], ['/usr/bin/apt-get', '-y', *options]])
        self.assertEqual(recorded, ['distrobox', 'podman'])

    def test_a_failed_download_stops_before_any_install(self):
        calls, error, recorded = self.run_with([done(100)])
        self.assertEqual(len(calls), 1)
        for part in ('Vinci', 'distrobox, podman', 'apt exit 100', 'internet connection', 'Nothing was installed'):
            self.assertIn(part, error)
        self.assertEqual(recorded, [])

    def test_a_failed_install_is_said_and_never_recorded(self):
        calls, error, recorded = self.run_with([done(), done(100)], after=False)
        self.assertEqual(len(calls), 2)
        for part in ('Installing the tools Vinci needs failed', 'apt exit 100', 'Vinci was not installed'):
            self.assertIn(part, error)
        self.assertEqual(recorded, [])

    def test_a_present_tool_is_only_kept_from_autoremove(self):
        """Nothing is installed; a tool apt had marked automatic is marked manual and recorded, a manual one is not touched."""
        calls = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(tools, 'RECORDS', Path(tmp) / 'tools'), \
             patch.object(tools.subprocess, 'run', side_effect=lambda command, **k: calls.append(command) or done()), \
             patch.object(tools, 'automatic', side_effect=lambda name: name in ('distrobox', 'fuse3')):
            tools.ensure(self.row, None)
            self.assertEqual(calls, [['/usr/bin/apt-mark', 'manual', 'distrobox', 'fuse3']])
            self.assertEqual(tools.brought('vinci'), ['distrobox', 'fuse3'])
        calls = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(tools, 'RECORDS', Path(tmp) / 'tools'), \
             patch.object(tools.subprocess, 'run', side_effect=lambda command, **k: calls.append(command) or done()), \
             patch.object(tools, 'automatic', return_value=False):
            tools.ensure(self.row, None)
            self.assertEqual(calls, [])
            self.assertFalse((Path(tmp) / 'tools').exists())

    def test_apt_exit_0_with_a_tool_still_absent_is_a_failure(self):
        _, error, recorded = self.run_with([done(), done()], after=False)
        self.assertIn('failed', error)
        self.assertEqual(recorded, [])


class Release(unittest.TestCase):
    def test_brought_tools_stay_and_are_marked_automatic_unless_another_entry_needs_them(self):
        row = catalogue.entry('vinci')
        with tempfile.TemporaryDirectory() as tmp, patch.object(tools, 'RECORDS', Path(tmp)):
            tools.record('vinci').write_text(json.dumps(['bsdextrautils', 'distrobox', 'fuse3', 'podman']))
            out = io.StringIO()
            with patch.object(tools, 'present', side_effect=lambda name: name != 'bsdextrautils'), \
                 patch.object(tools.subprocess, 'run', return_value=done()) as run, contextlib.redirect_stdout(out):
                tools.release(row, {'fuse3'})
            # never a removal; fuse3 is another installed entry's, bsdextrautils is already gone
            self.assertEqual(run.call_args.args[0], ['/usr/bin/apt-mark', 'auto', 'distrobox', 'podman'])
            self.assertEqual(run.call_count, 1)
            self.assertIn('distrobox, podman', out.getvalue())
            self.assertIn('stay installed', out.getvalue())
            self.assertFalse(tools.record('vinci').exists())

    def test_tools_that_were_already_there_are_left_as_they_were(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(tools, 'RECORDS', Path(tmp)), \
             patch.object(tools.subprocess, 'run') as run:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                tools.release(catalogue.entry('vinci'), set())
            run.assert_not_called()
            self.assertEqual(out.getvalue(), '')


class Action(unittest.TestCase):
    def test_a_refused_plan_stops_the_entry_before_any_download(self):
        row = catalogue.entry('vinci')
        with patch.object(tools, 'plan', side_effect=tools.Refused('refused')), \
             patch.object(action, 'appimage_change') as handler, patch.object(action.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'refused'):
                action.change(row, 'install')
            handler.assert_not_called()
            run.assert_not_called()

    def test_sizes_are_said_first_and_the_metered_notice_names_program_and_tools(self):
        row = catalogue.entry('vinci')
        found = {'tools': ['podman'], 'packages': [('podman', '5')] * 35, 'download': 30 << 20, 'disk': 100 << 20, 'sources': ['Debian']}
        reader = common.install_downloads()
        out = io.StringIO()
        with patch.object(reader, 'metered', return_value=('yes', 'yes')), patch.object(action, 'announce_setting', return_value='metered'), \
             contextlib.redirect_stdout(out):
            action.announce(row, found)
        said = out.getvalue().splitlines()
        self.assertIn('podman', said[0])
        self.assertIn('35 packages from Debian: 30.0 MiB to download', said[1])
        self.assertIn('metered', said[3])
        self.assertTrue(any('Vinci: 36.6 MiB from https://github.com/' in line for line in said))
        self.assertTrue(any('podman: 30.0 MiB from Debian' in line for line in said))
        # not metered: the sizes are still said, the metered notice is not
        out = io.StringIO()
        with patch.object(reader, 'metered', return_value=('no', 'no')), patch.object(action, 'announce_setting', return_value='metered'), \
             contextlib.redirect_stdout(out):
            action.announce(row, found)
        self.assertEqual(len(out.getvalue().splitlines()), 3)
        # the tools are there already: nothing about tools, the program's own notice as before
        out = io.StringIO()
        with patch.object(reader, 'metered', return_value=('yes', 'yes')), patch.object(action, 'announce_setting', return_value='metered'), \
             contextlib.redirect_stdout(out):
            action.announce(row, None)
        self.assertNotIn('podman', out.getvalue())
        self.assertNotIn('tools', out.getvalue())
        self.assertIn('Vinci: 36.6 MiB', out.getvalue())

    def test_removal_releases_the_tools_and_names_those_needed_elsewhere(self):
        row = catalogue.entry('vinci')
        states = {'vinci': False, 'kamlynk': True}
        with patch.object(action, 'installed', side_effect=lambda each: states.get(each['id'], False)), \
             patch.object(action, 'appimage_change'), patch.object(tools, 'release') as release:
            action.change(row, 'remove')
        release.assert_called_once_with(row, {'fuse3'})

    def test_flatpak_absent_means_not_installed_and_the_entry_brings_it(self):
        row = catalogue.entry('slimevr')
        with patch.object(action.Path, 'exists', return_value=False), patch.object(action.subprocess, 'run') as run:
            self.assertFalse(action.installed(row))
            run.assert_not_called()
        order = []
        with patch.object(tools, 'ensure', side_effect=lambda *a: order.append('tools')), \
             patch.object(action.subprocess, 'run', side_effect=lambda command, **k: order.append(command[1]) or done(0, 'flathub\n')):
            action.flatpak_change(row, 'install', {'tools': ['flatpak']})
        self.assertEqual(order, ['tools', 'remotes', 'install'])


class Program(unittest.TestCase):
    """The AppImage is fetched and verified first, then the tools, then the placement."""
    def setUp(self):
        self.row = dict(catalogue.entry('vinci'), sha256=hashlib.sha256(b'program').hexdigest())

    def test_a_failed_program_download_is_said_plainly_and_no_tool_is_installed(self):
        ensure = unittest.mock.Mock()
        with tempfile.TemporaryDirectory() as tmp, patch.object(appimage, 'paths', return_value=(Path(tmp) / 'opt/vinci', {})), \
             patch.object(appimage.subprocess, 'run', return_value=done(6)):
            with self.assertRaises(RuntimeError) as refused:
                appimage.change(self.row, 'install', ensure)
        for part in ('Vinci could not be downloaded from github.com', 'curl exit 6', 'internet connection', 'No application was changed'):
            self.assertIn(part, str(refused.exception))
        ensure.assert_not_called()

    def test_a_wrong_checksum_is_refused_before_the_tools(self):
        ensure = unittest.mock.Mock()

        def run(command, **kwargs):
            Path(command[command.index('--output') + 1]).write_bytes(b'tampered')
            return done()
        with tempfile.TemporaryDirectory() as tmp, patch.object(appimage, 'paths', return_value=(Path(tmp) / 'opt/vinci', {})), \
             patch.object(appimage.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                appimage.change(self.row, 'install', ensure)
        ensure.assert_not_called()

    def test_a_refused_tool_leaves_no_application(self):
        def run(command, cwd=None, **kwargs):
            if command[0] == 'curl':
                Path(command[command.index('--output') + 1]).write_bytes(b'program')
            else:
                wanted = Path(cwd) / 'squashfs-root' / command[2]
                wanted.parent.mkdir(parents=True, exist_ok=True)
                wanted.write_text('x')
            return done()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'opt/vinci'
            with patch.object(appimage, 'paths', return_value=(base, {})), patch.object(appimage.subprocess, 'run', side_effect=run):
                with self.assertRaisesRegex(RuntimeError, 'no tools'):
                    appimage.change(self.row, 'install', unittest.mock.Mock(side_effect=tools.Refused('no tools')))
            self.assertFalse(base.exists())


if __name__ == '__main__':
    unittest.main()
