#!/usr/bin/python3
"""Transaction regression checks. All OS effects are substituted before invocation."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

source = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'actions/zram'
loader = importlib.machinery.SourceFileLoader('zram', str(source))
spec = importlib.util.spec_from_loader('zram', loader)
zram = importlib.util.module_from_spec(spec)
loader.exec_module(zram)

class Transaction(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.swap = False
        self.failure = None
        self.skip_start = False
        self.manager = True
        self.result = "success"
        self.size = 0
        self.hidden_stop_failure = False
        self.masked = False
        self.inhibitor_start = False
        self.patches = [
            patch.object(zram, 'messages', return_value={'restart':'No running systemd. Starts after restart.', 'active':'active', 'inactive':'inactive'}),
            patch.object(zram, 'systemd_running', create=True, side_effect=lambda: self.manager),
            patch.object(zram, 'active', create=True, side_effect=lambda: self.swap),
            patch.object(zram, 'disk_size', create=True, side_effect=lambda: self.size),
            patch.object(zram.subprocess, 'run', side_effect=self.run_command),
            patch.object(zram.os.path, 'lexists', return_value=False),
            patch.object(zram.os, 'geteuid', return_value=0),
        ]
        for p in self.patches: p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def run_command(self, command, **kwargs):
        self.commands.append(command)
        if 'mask' in command: self.masked=True
        if 'unmask' in command: self.masked=False
        if command[0].endswith('apt-get') and 'remove' in command and self.inhibitor_start and not self.masked:
            self.swap=True
        if self.failure and self.failure in command:
            raise subprocess.CalledProcessError(7, command)
        if command[:3] == ['/usr/bin/systemctl','start','dev-zram0.swap'] and not self.skip_start:
            self.swap=True
        if command[:3] == ['/usr/bin/systemctl','stop','dev-zram0.swap']:
            self.swap=False
        if command[:3] == ['/usr/bin/systemctl','stop','systemd-zram-setup@zram0.service']:
            if self.hidden_stop_failure: self.result='exit-code'; self.size=4096
            else: self.result='success'; self.size=0
        if '--reset-device' in command: self.size=0
        return subprocess.CompletedProcess(command, 0, stdout=self.result)

    def change(self, operation):
        # Red 0.1.0 has no transaction function: exercise its existing public path.
        if hasattr(zram,'change'): zram.change(operation)
        else:
            with patch.object(sys,'argv',[str(source),operation]): zram.main()

    def test_install_activates_without_boot(self):
        self.change('install')
        self.assertTrue(self.swap)
        self.assertEqual([c[1] for c in self.commands if c[0].endswith('systemctl')], ['daemon-reload','start'])
        self.assertIn('--no-remove',self.commands[0])

    def test_remove_stops_swap_then_setup_before_apt(self):
        self.swap=True
        self.change('remove')
        self.assertFalse(self.swap)
        self.assertEqual([c for c in self.commands if 'stop' in c], [['/usr/bin/systemctl','stop','dev-zram0.swap'], ['/usr/bin/systemctl','stop','systemd-zram-setup@zram0.service']])
        self.assertIn(['/usr/bin/apt-get','-y','remove','systemd-zram-generator'],self.commands)

    def test_failed_swap_stop_preserves_provider_and_setup(self):
        self.swap=True
        self.failure='stop'
        with self.assertRaises(subprocess.CalledProcessError): self.change('remove')
        self.assertFalse(any(c[0].endswith('apt-get') for c in self.commands))
        self.assertFalse(self.masked)

    def test_failed_setup_stop_preserves_provider(self):
        self.failure='systemd-zram-setup@zram0.service'
        with self.assertRaises(subprocess.CalledProcessError): self.change('remove')
        self.assertFalse(any(c[0].endswith('apt-get') for c in self.commands))

    def test_failed_install_does_not_start(self):
        self.failure='install'
        with self.assertRaises(subprocess.CalledProcessError): self.change('install')
        self.assertEqual(len(self.commands),1)

    def test_failed_reload_does_not_start(self):
        self.failure='daemon-reload'
        with self.assertRaises(subprocess.CalledProcessError): self.change('install')
        self.assertFalse(any('start' in c for c in self.commands))

    def test_start_failure_is_not_success(self):
        self.failure='start'
        with self.assertRaises(subprocess.CalledProcessError): self.change('install')

    def test_skipped_condition_is_not_success(self):
        self.skip_start=True
        with self.assertRaises(RuntimeError): self.change('install')

    def test_no_systemd_does_not_call_systemctl(self):
        self.manager=False
        self.change('install')
        self.assertTrue(any(c[0].endswith('apt-get') for c in self.commands))
        self.assertFalse(any(c[0].endswith('systemctl') for c in self.commands))

    def test_active_without_systemd_cannot_remove(self):
        self.manager=False
        self.swap=True
        with self.assertRaises(RuntimeError): self.change('remove')
        self.assertEqual(self.commands,[])

    def test_successful_systemctl_with_failed_execstop_preserves_package(self):
        self.hidden_stop_failure=True
        with self.assertRaises(RuntimeError): self.change('remove')
        self.assertFalse(any(c[0].endswith('apt-get') for c in self.commands))

    def test_explicit_repair_retries_failed_reset(self):
        self.hidden_stop_failure=True
        zram.change('remove',repair=True)
        reset=next(i for i,c in enumerate(self.commands) if '--reset-device' in c)
        apt=next(i for i,c in enumerate(self.commands) if c[0].endswith('apt-get'))
        self.assertLess(reset,apt)
        self.assertEqual(self.size,0)

    def test_failed_reset_repair_preserves_package(self):
        self.hidden_stop_failure=True
        self.failure='--reset-device'
        with self.assertRaises(subprocess.CalledProcessError): zram.change('remove',repair=True)
        self.assertFalse(any(c[0].endswith('apt-get') for c in self.commands))

    def test_apt_inhibitor_cannot_reactivate_swap(self):
        self.inhibitor_start=True
        self.swap=True
        self.change('remove')
        self.assertFalse(self.swap)
        self.assertFalse(self.masked)

    def test_existing_runtime_mask_is_preserved(self):
        self.masked=True
        with patch.object(zram.os.path, 'lexists', return_value=True):
            self.change('remove')
        self.assertTrue(self.masked)
        self.assertFalse(any('unmask' in c for c in self.commands))

    def test_apt_failure_releases_only_our_mask(self):
        self.failure='remove'
        with self.assertRaises(subprocess.CalledProcessError): self.change('remove')
        self.assertFalse(self.masked)

    def test_engine_covers_complete_change_and_repairs_public_action(self):
        import json
        with patch.object(sys,'argv',[str(source),'install']): zram.main()
        command=self.commands[0]
        self.assertEqual(command[0],zram.ENGINE)
        self.assertEqual(json.loads(command[command.index('--repair')+1]),[zram.ACTION,'install'])
        self.assertEqual(command[command.index('--')+1:],[zram.ACTION,'--install'])

unittest.main()
