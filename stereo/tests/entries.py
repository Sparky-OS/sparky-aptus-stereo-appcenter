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
import os
import unittest
from unittest.mock import patch

SOURCE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
# the one reader of the install-time download declaration lives in sparky-stereo-apt: layout.py finds it
sys.path.append(str(Path(__file__).resolve().parent))
import layout
READER = layout.reader(SOURCE)
import common
SOURCE = layout.assembled(SOURCE)
sys.path.insert(0, str(SOURCE))
common.BASE = SOURCE
common.LANGDIR = SOURCE / 'lang'
import catalogue
spec = importlib.util.spec_from_loader('entry_action', importlib.machinery.SourceFileLoader('entry_action', str(SOURCE / 'actions/entry')))
action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(action)


class Transactions(unittest.TestCase):
    def setUp(self):
        policy = patch.object(action, 'only_ours', return_value={'bino'})
        policy.start()
        self.addCleanup(policy.stop)

    def test_exact_routes_only(self):
        for row in catalogue.entries():
            for operation in ('install', 'remove', 'repair'):
                # a store link changes nothing on the system: no route, no pkexec (tests/store.py)
                self.assertEqual(catalogue.route(f"aptus://stereo_entry_{row['id']}_{operation}"),
                                 None if row['kind']=='store' else [str(SOURCE/'actions/entry'),row['id'],operation])
        for uri in ('aptus://stereo_other','aptus://stereo_entry_bino_install?x=1',
                    'aptus://sysoth_bleachbit','file:///usr/lib/sparky-aptus-appcenter/system.html'):
            self.assertIsNone(catalogue.route(uri))

    def test_edition_candidate(self):
        row=catalogue.entry('bino')
        version=types.SimpleNamespace(version='2.8+stereo3d9+lc1',origins=[types.SimpleNamespace(origin='Sparky Stereo OS',trusted=True)])
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda: {'bino':types.SimpleNamespace(candidate=version)})), patch.object(action.subprocess,'run') as run:
            action.apt_change(row,'install')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','--no-remove','--no-allow-unauthenticated','install','bino=2.8+stereo3d9+lc1'])
            for origin,trusted in [('Debian',True),('Sparky Stereo OS',False)]:
                version.origins=[types.SimpleNamespace(origin=origin,trusted=trusted)]
                run.reset_mock()
                with self.assertRaisesRegex(RuntimeError,'bino'):
                    action.apt_change(row,'install')
                run.assert_not_called()

    def test_configured_archive_candidate(self):
        row=catalogue.entry('simple-scan')
        version=types.SimpleNamespace(version='50.0-2', origins=[types.SimpleNamespace(origin='Debian',trusted=True)])
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda: {'simple-scan':types.SimpleNamespace(candidate=version)})), patch.object(action.subprocess,'run') as run:
            action.apt_change(row,'install')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','--no-remove','--no-allow-unauthenticated','install','simple-scan=50.0-2'])

    def test_cloudcompare_is_an_apt_entry_of_the_stereo_players_editors_and_tools(self):
        row=catalogue.entry('cloudcompare')
        self.assertEqual((row['section'],row['kind'],row['package']),('media','apt','cloudcompare'))
        self.assertEqual(row['name'],'CloudCompare')
        version=types.SimpleNamespace(version='2.13.2+git20240821+ds-7+stereo3d1+lc1',origins=[types.SimpleNamespace(origin='Sparky Stereo OS',trusted=True)],downloadable=True)
        cache={'cloudcompare':types.SimpleNamespace(candidate=version)}
        self.assertTrue(action.visible(row,cache,{'bino'}))
        self.assertFalse(action.visible(row,{},{'bino'}))
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda: cache)), patch.object(action.subprocess,'run') as run:
            run.return_value.returncode=0
            action.apt_change(row,'install')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','--no-remove','--no-allow-unauthenticated','install','cloudcompare=2.13.2+git20240821+ds-7+stereo3d1+lc1'])

    def test_model_viewer_is_an_apt_entry_of_the_stereo_players_editors_and_tools(self):
        row=catalogue.entry('stereo-model-viewer')
        self.assertEqual((row['section'],row['kind'],row['package']),('media','apt','sparky-stereo-model-viewer'))
        self.assertEqual(row['name'],'Stereo Model Viewer')
        version=types.SimpleNamespace(version='0.1.0+lc1',origins=[types.SimpleNamespace(origin='Sparky Stereo OS',trusted=True)],downloadable=True)
        cache={'sparky-stereo-model-viewer':types.SimpleNamespace(candidate=version)}
        self.assertTrue(action.visible(row,cache,{'bino'}))
        self.assertFalse(action.visible(row,{},{'bino'}))
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda: cache)), patch.object(action.subprocess,'run') as run:
            run.return_value.returncode=0
            action.apt_change(row,'install')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','--no-remove','--no-allow-unauthenticated','install','sparky-stereo-model-viewer=0.1.0+lc1'])

    def test_visibility_follows_archive_and_edition_policy(self):
        cache={'simple-scan':types.SimpleNamespace(candidate=types.SimpleNamespace(downloadable=True))}
        self.assertTrue(action.visible(catalogue.entry('simple-scan'),cache,{'bino'}))
        self.assertFalse(action.visible(catalogue.entry('openrv'),cache,{'bino'}))
        self.assertTrue(action.visible(catalogue.entry('bino'),cache,{'bino'}))
        cache['simple-scan'].candidate.downloadable=False
        self.assertFalse(action.visible(catalogue.entry('simple-scan'),cache,{'bino'}))

    def test_absent_edition_candidate(self):
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda:{})), patch.object(action.subprocess,'run') as run:
            with self.assertRaises(RuntimeError): action.apt_change(catalogue.entry('bino'),'install')
            run.assert_not_called()

    def test_remove_does_not_require_available_archive(self):
        with patch.object(action.subprocess,'run') as run:
            action.apt_change(catalogue.entry('bino'),'remove')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','remove','bino'])

    def test_flatpak_never_creates_remote(self):
        # the entry's own tool (flatpak) is the subject of tests/tools.py; here it is present
        tools_present = patch.object(action.tools,'ensure')
        tools_present.start()
        self.addCleanup(tools_present.stop)
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
        states = {row['id']:dict(installed=False,error='',visible=True) for row in catalogue.entries()}
        states['slimevr-driver']['error']='SHA-256 mismatch'
        states['openrv']['visible']=False
        states['xstudio']['visible']=False
        results = [subprocess.CompletedProcess([],0,json.dumps(zram)),subprocess.CompletedProcess([],0,json.dumps(states))]
        with patch.object(page.subprocess,'run',side_effect=results):
            html = page.render()
        self.assertIn('aptus://stereo_entry_slimevr-driver_repair',html)
        self.assertIn('SHA-256 mismatch',html)
        self.assertNotIn('entry-openrv',html)
        self.assertNotIn('entry-xstudio',html)
        sections = ['stereo-emulation','stereo-media','stereo-vr','stereo-vpn','stereo-tools','stereo-drivers','stereo-system','pawel-categories']
        self.assertEqual(sorted(sections,key=lambda name:html.index('id="'+name+'"')),sections)

    def test_entry_with_companions_installs_and_removes_them_together(self):
        row=catalogue.entry('syncthing')
        self.assertEqual(row['also'],['syncthingtray-kde-plasma'])
        version=types.SimpleNamespace(version='1.29.5~ds1-5',origins=[types.SimpleNamespace(origin='Debian',trusted=True)])
        with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda: {'syncthing':types.SimpleNamespace(candidate=version)})), patch.object(action.subprocess,'run') as run:
            action.apt_change(row,'install')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','--no-remove','--no-allow-unauthenticated','install','syncthing=1.29.5~ds1-5','syncthingtray-kde-plasma'])
        with patch.object(action.subprocess,'run') as run:
            action.apt_change(row,'remove')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','remove','syncthing','syncthingtray-kde-plasma'])
        # control: an entry without companions keeps the one-package command
        with patch.object(action.subprocess,'run') as run:
            action.apt_change(catalogue.entry('keepassxc'),'remove')
            self.assertEqual(run.call_args.args[0],['/usr/bin/apt-get','-y','remove','keepassxc'])

    def test_entry_is_visible_only_when_all_its_packages_are_offered(self):
        ok=types.SimpleNamespace(candidate=types.SimpleNamespace(downloadable=True))
        no=types.SimpleNamespace(candidate=types.SimpleNamespace(downloadable=False))
        row=catalogue.entry('syncthing')
        self.assertTrue(action.visible(row,{'syncthing':ok,'syncthingtray-kde-plasma':ok},set()))
        self.assertFalse(action.visible(row,{'syncthing':ok,'syncthingtray-kde-plasma':no},set()))
        self.assertFalse(action.visible(row,{'syncthing':ok},set()))
        self.assertFalse(action.visible(catalogue.entry('hplip'),{},set()))

    def test_vpn_section_offers_the_plain_plugins_only(self):
        vpn=[row for row in catalogue.entries() if row['section']=='vpn']
        self.assertGreaterEqual(len(vpn),6)
        for row in vpn:
            self.assertRegex(row['package'],r'^network-manager-[a-z0-9]+$')
            self.assertNotIn('gnome',row['package'])
        self.assertNotIn('network-manager-vpnc-gnome',[row.get('package') for row in catalogue.entries()])

    def test_catalogue_shape_and_section_titles_in_every_language(self):
        rows=catalogue.entries()
        self.assertEqual(len({row['id'] for row in rows}),len(rows))
        for row in rows:
            # the five sections of the stereo page, and 'main': Paweł's pages' own entries (Vinci, KamLynk), ORDER 553 (0.1.8)
            self.assertIn(row['section'],('emulation','media','vr','vpn','tools','main'))
            self.assertIn(row['kind'],('apt','flatpak','download','appimage','store','signed-deb'))   # appimage: Vinci and KamLynk, 0.1.7 (ORDER 553); store: a link to a vendor's store page, 0.1.15 (ORDER 10)
            if 'also' in row:
                self.assertEqual(row['kind'],'apt')
                self.assertTrue(all(isinstance(name,str) and name for name in row['also']))
        for path in sorted((SOURCE/'lang').glob('*.json')):
            titles=json.loads(path.read_text())
            for key in ('vpn','tools'):
                self.assertTrue(titles.get(key),path.name+' lacks '+key)
        for code in ('en','pl','pt_BR','fr','de','ja','ko','zh_CN','zh_TW'):
            self.assertTrue((SOURCE/'lang'/(code+'.json')).is_file(),code)

    def test_zram_does_not_show_another_entry_failure(self):
        spec = importlib.util.spec_from_loader('zram_status', importlib.machinery.SourceFileLoader('zram_status', str(SOURCE/'actions/zram')))
        zram = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(zram)
        records=[dict(key='slimevr-driver',text='checksum failure',output='SHA-256')]
        results=[subprocess.CompletedProcess([],1,''),subprocess.CompletedProcess([],0,''),
                 subprocess.CompletedProcess([],0,json.dumps(records))]
        with patch.object(zram.subprocess,'run',side_effect=results), patch.object(zram,'active',return_value=False):
            self.assertEqual(zram.status()['error'],'')


    def test_install_time_download_notice(self):
        """A package an entry brings along declares a download: the note has its size and source, on a metered connection only."""
        reader = common.install_downloads()
        declared = {'flightgear-data-installer': {'size': 1883333376, 'source': 'https://sourceforge.net/x/download', 'version': '2024.1.5-1'}}
        cache = {'flightgear': object(), 'bino': object()}
        row = {'id': 'flightgear', 'kind': 'apt', 'package': 'flightgear'}
        def notes(state, present=False, brings=('flightgear-data-installer',), installed=None, found=None, rows=None):
            with patch.object(reader, 'metered', return_value=state), patch.object(action, 'announce_setting', return_value='metered'), \
                 patch.object(reader, 'declaring', return_value=(declared if found is None else found, None)), \
                 patch.object(reader, 'dependants', return_value={'flightgear', 'flightgear-data-installer'}), \
                 patch.object(reader, 'installed_declaration', return_value=installed), \
                 patch.object(action, 'new_depcache', return_value=None), \
                 patch.object(action, 'brought_in', side_effect=lambda depcache, apt_cache, names, entry: list(brings)):
                return action.downloads_note(cache, {'flightgear': present, 'bino': False}, rows or [row])
        shown = notes(('yes', 'yes'))
        self.assertEqual(list(shown), ['flightgear'])
        self.assertEqual(shown['flightgear']['downloads'][0]['size_text'], '1.75 GiB')
        self.assertEqual(shown['flightgear']['downloads'][0]['source'], 'https://sourceforge.net/x/download')
        self.assertTrue(any('1.75 GiB from https://sourceforge.net/x/download' in line for line in shown['flightgear']['text']))
        self.assertFalse(any('Answer n' in line for line in shown['flightgear']['text']))
        self.assertIn('metered', ' '.join(shown['flightgear']['text']))
        self.assertEqual(notes(('no', 'no')), {})
        self.assertIn('Could not tell', ' '.join(notes(('unknown', 'NetworkManager did not answer'))['flightgear']['text']))
        self.assertEqual(notes(('yes', 'yes'), present=True), {})
        self.assertEqual(notes(('yes', 'yes'), brings=()), {})
        self.assertEqual(notes(('yes', 'yes'), found={}), {})
        # an entry that cannot bring a declaring package in is never resolved
        self.assertEqual(notes(('yes', 'yes'), rows=[{'id': 'bino', 'kind': 'apt', 'package': 'bino'}]), {})
        # a package whose installed version declares the same download keeps its data
        self.assertEqual(notes(('yes', 'yes'), installed={'size': 1883333376, 'source': 'https://sourceforge.net/x/download'}), {})
        self.assertEqual(list(notes(('yes', 'yes'), installed={'size': 1, 'source': 'https://old'})), ['flightgear'])
        said = notes(('yes', 'yes'), found={'flightgear-data-installer': ValueError('Sparky-Install-Download-Size is "many", not a number of bytes')})
        self.assertIn('could not be checked', said['flightgear']['error'])
        self.assertIn('flightgear-data-installer', said['flightgear']['error'])

    def test_page_shows_the_note_beside_the_entry(self):
        spec = importlib.util.spec_from_loader('page2', importlib.machinery.SourceFileLoader('page2', str(SOURCE/'appcenter')))
        page = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(page)
        zram = dict(installed=False,title='zram',description='',state='absent',restart='',error='',button='Install')
        states = {row['id']:dict(installed=False,error='',visible=True,download=None) for row in catalogue.entries()}
        states['flightgear']['download'] = {'state': 'yes', 'downloads': [], 'text': ['This connection is metered (NetworkManager says: yes).',
            'These packages download more data while they are installed:', '  flightgear-data-installer: 1.75 GiB from https://sourceforge.net/x/download']}
        results = [subprocess.CompletedProcess([],0,json.dumps(zram)),subprocess.CompletedProcess([],0,json.dumps(states))]
        with patch.object(page.subprocess,'run',side_effect=results):
            html = page.render()
        card = html[html.index('id="entry-flightgear"'):]
        card = card[:card.index('</article>')]
        self.assertIn('1.75 GiB from https://sourceforge.net/x/download', card)
        self.assertIn('class="download"', card)
        self.assertNotIn('class="download"', html[html.index('id="entry-bino"'):html.index('id="entry-bino"') + 400])

    def test_catalogues(self):
        english=json.loads((SOURCE/'lang/en.json').read_text())
        import string
        def fields(s): return sorted(x[1] for x in string.Formatter().parse(s) if x[1])
        # The ten languages the edition requires hold every key of English. The eleven older page languages (Paweł's list) hold
        # the sentences of the older versions; a key they lack is read in English (common.messages), and none holds a key English lacks.
        # ORDER 565 and 575 added sentences "in the ten languages" (CHANGELOG 0.1.9, 0.1.10).
        required={'en','pl','pt_BR','fr','de','es','ja','ko','zh_CN','zh_TW'}
        self.assertEqual(required-{path.stem for path in (SOURCE/'lang').glob('*.json')},set())
        for path in (SOURCE/'lang').glob('*.json'):
            texts=json.loads(path.read_text())
            if path.stem in required:
                self.assertEqual(set(texts),set(english),path.name)
            else:
                self.assertEqual(set(texts)-set(english),set(),path.name)
            for key in texts:
                self.assertEqual(fields(texts[key]),fields(english[key]),(path.name,key))
                self.assertEqual(texts[key].count('%s'),english[key].count('%s'),(path.name,key))
            self.assertIn('LOCAL91=',path.with_suffix('').read_text())

class GeneratedPolicy(unittest.TestCase):
    def test_installed_pin_records_and_architectures(self):
        try:
            import apt_pkg
        except ImportError:
            self.fail('python3-apt is not installed: the package Depends on it, run these tests where it is (a container)')
        apt_pkg.init_config()
        native=apt_pkg.config.find('APT::Architecture')
        other='arm64' if native!='arm64' else 'amd64'
        with tempfile.TemporaryDirectory() as tmp:
            policy=Path(tmp)/'only-ours'
            policy.write_text(f'Package: bino:{native} foreign:{other} global:any plain\nPin: release o=Debian\nPin-Priority: -1\n\nPackage: carried:any\nPin: release o=Sparky Stereo OS\nPin-Priority: 400\n')
            with patch.object(action,'ONLY_OURS',policy):
                self.assertEqual(action.only_ours(),{'bino','global','plain'})
            policy.unlink()
            with patch.object(action,'ONLY_OURS',policy):
                with self.assertRaises(FileNotFoundError): action.only_ours()

if __name__=='__main__': unittest.main()
