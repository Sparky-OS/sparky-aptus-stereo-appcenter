#!/usr/bin/python3
"""Transaction controls independent of package-manager and network side effects."""
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SOURCE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import common
common.BASE = SOURCE
common.LANGDIR = SOURCE / 'lang'
import catalogue
spec = importlib.util.spec_from_loader('entry_action', importlib.machinery.SourceFileLoader('entry_action', str(SOURCE / 'actions/entry')))
action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(action)


class Transactions(unittest.TestCase):
    def test_exact_routes_only(self):
        for row in catalogue.entries():
            for operation in ('install', 'remove', 'repair'):
                self.assertEqual(catalogue.route(f"aptus://stereo_entry_{row['id']}_{operation}"),
                                 [str(SOURCE/'actions/entry'),row['id'],operation])
        for uri in ('aptus://stereo_other','aptus://stereo_entry_bino_install?x=1',
                    'aptus://sysoth_bleachbit','file:///usr/lib/sparky-aptus-appcenter/system.html'):
            self.assertIsNone(catalogue.route(uri))

    def test_edition_candidate(self):
        row=catalogue.entry('bino')
        version=types.SimpleNamespace(version='2.8+stereo3d9+lc1',origins=[types.SimpleNamespace(origin='Sparky Stereo OS',trusted=True)])
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda: {'bino':types.SimpleNamespace(candidate=version)})), patch.object(action.subprocess,'run') as run:
            action.apt_change(row,'install')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','--no-remove','install','bino=2.8+stereo3d9+lc1'])
            for origin,trusted in [('Debian',True),('Sparky Stereo OS',False)]:
                version.origins=[types.SimpleNamespace(origin=origin,trusted=trusted)]
                run.reset_mock()
                with self.assertRaisesRegex(RuntimeError,'bino'):
                    action.apt_change(row,'install')
                run.assert_not_called()

    def test_absent_edition_candidate(self):
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda:{})), patch.object(action.subprocess,'run') as run:
            with self.assertRaises(RuntimeError): action.apt_change(catalogue.entry('bino'),'install')
            run.assert_not_called()

    def test_remove_does_not_require_available_archive(self):
        with patch.object(action.subprocess,'run') as run:
            action.apt_change(catalogue.entry('bino'),'remove')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','remove','bino'])

    def test_flatpak_never_creates_remote(self):
        with patch.object(action.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')) as run:
            with self.assertRaisesRegex(RuntimeError,'Flathub'): action.flatpak_change(catalogue.entry('slimevr'),'install')
            self.assertEqual(run.call_count,1)
        with patch.object(action.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'flathub\n','')) as run:
            action.flatpak_change(catalogue.entry('slimevr'),'install')
            self.assertEqual(run.call_args.args[0],['/usr/bin/flatpak','install','--system','--noninteractive','flathub','dev.slimevr.SlimeVR'])

    def test_checksum_refusal_and_download_removal(self):
        row=dict(catalogue.entry('slimevr-driver'))
        row['sha256']=hashlib.sha256(b'verified').hexdigest()
        with tempfile.TemporaryDirectory() as tmp, patch.object(action,'DOWNLOADS',Path(tmp)):
            def download(command,**kwargs):
                Path(command[command.index('--output')+1]).write_bytes(b'tampered')
            with patch.object(action.subprocess,'run',side_effect=download):
                with self.assertRaisesRegex(RuntimeError,'SHA-256'): action.download(row,'install')
                self.assertEqual(list(Path(tmp).iterdir()),[])
            def download_good(command,**kwargs):
                Path(command[command.index('--output')+1]).write_bytes(b'verified')
            with patch.object(action.subprocess,'run',side_effect=download_good): action.download(row,'install')
            self.assertTrue(action.installed(row))
            # A failed refresh must retain the already verified file.
            with patch.object(action.subprocess,'run',side_effect=download):
                with self.assertRaises(RuntimeError): action.download(row,'install')
            self.assertTrue(action.installed(row))
            action.download(row,'remove')
            self.assertFalse(action.installed(row))

    def test_download_failure_has_visible_repair(self):
        spec = importlib.util.spec_from_loader('page', importlib.machinery.SourceFileLoader('page', str(SOURCE/'appcenter')))
        page = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(page)
        zram = dict(installed=False,title='zram',description='',state='absent',restart='',error='',button='Install')
        states = {row['id']:dict(installed=False,error='') for row in catalogue.entries()}
        states['slimevr-driver']['error']='SHA-256 mismatch'
        results = [subprocess.CompletedProcess([],0,json.dumps(zram)),subprocess.CompletedProcess([],0,json.dumps(states))]
        with patch.object(page.subprocess,'run',side_effect=results):
            html = page.render()
        self.assertIn('aptus://stereo_entry_slimevr-driver_repair',html)
        self.assertIn('SHA-256 mismatch',html)
        sections = ['stereo-emulation','stereo-media','stereo-vr','stereo-drivers','stereo-system','pawel-categories']
        self.assertEqual(sorted(sections,key=lambda name:html.index('id="'+name+'"')),sections)

    def test_zram_does_not_show_another_entry_failure(self):
        spec = importlib.util.spec_from_loader('zram_status', importlib.machinery.SourceFileLoader('zram_status', str(SOURCE/'actions/zram')))
        zram = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(zram)
        records=[dict(key='slimevr-driver',text='checksum failure',output='SHA-256')]
        results=[subprocess.CompletedProcess([],1,''),subprocess.CompletedProcess([],0,''),
                 subprocess.CompletedProcess([],0,json.dumps(records))]
        with patch.object(zram.subprocess,'run',side_effect=results), patch.object(zram,'active',return_value=False):
            self.assertEqual(zram.status()['error'],'')

    def test_catalogues(self):
        english=json.loads((SOURCE/'lang/en.json').read_text())
        import string
        def fields(s): return sorted(x[1] for x in string.Formatter().parse(s) if x[1])
        for path in (SOURCE/'lang').glob('*.json'):
            texts=json.loads(path.read_text())
            self.assertEqual(set(texts),set(english),path.name)
            for key in english:
                self.assertEqual(fields(texts[key]),fields(english[key]),(path.name,key))
                self.assertEqual(texts[key].count('%s'),english[key].count('%s'),(path.name,key))
            self.assertIn('LOCAL91=',path.with_suffix('').read_text())

if __name__=='__main__': unittest.main()
