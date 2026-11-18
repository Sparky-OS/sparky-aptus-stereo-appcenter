#!/usr/bin/python3
"""Vendor package authentication: use real minisign against externally supplied release fixtures."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
SOURCE = Path(sys.argv.pop(1)).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
import common
common.LANGDIR=SOURCE/'lang'
os.environ['LANG']='en_US.UTF-8'
os.environ.pop('LC_ALL',None)
import signeddeb
import tools
ROW=next(r for r in json.loads((SOURCE/'main-entries.json').read_text()) if r['id']=='openlogi')
FIXTURES=Path(os.environ['OPENLOGI_FIXTURE_DIR'])
REAL_RUN=subprocess.run

class SignedDeb(unittest.TestCase):
    def setUp(self):
        self.row=signeddeb.selected(ROW,'amd64')
        self.installs=[]
        self.ensured=[]

    def copy_download(self,args,**kwargs):
        if args[0]=='/usr/bin/curl':
            target=Path(args[args.index('--output')+1])
            shutil.copyfile(FIXTURES/args[-1].rsplit('/',1)[-1],target)
            return subprocess.CompletedProcess(args,0)
        return REAL_RUN(args,**kwargs)

    def change(self,row=None):
        with patch.object(signeddeb.subprocess,'run',side_effect=self.copy_download):
            signeddeb.change(row or self.row,'install',lambda:self.ensured.append(True),lambda command:self.installs.append(command))

    def test_authentic_file_is_verified_before_install(self):
        self.change()
        self.assertEqual(self.ensured,[True])
        self.assertEqual(len(self.installs),1)
        self.assertEqual(self.installs[0][0],'/usr/bin/apt-get')
        self.assertIn('--no-remove',self.installs[0])

    def test_tampered_payload_is_refused_before_tools_or_install(self):
        original=self.copy_download
        def tamper(args,**kwargs):
            result=original(args,**kwargs)
            if args[0]=='/usr/bin/curl' and args[-1].endswith('.deb'):
                with Path(args[args.index('--output')+1]).open('ab') as stream:stream.write(b'x')
            return result
        with patch.object(signeddeb.subprocess,'run',side_effect=tamper):
            with self.assertRaisesRegex(RuntimeError,'SHA-256'):
                signeddeb.change(self.row,'install',lambda:self.ensured.append(True),lambda c:self.installs.append(c))
        self.assertEqual((self.ensured,self.installs),([],[]))

    def test_wrong_key_is_refused_before_tools_or_install(self):
        with tempfile.TemporaryDirectory() as folder:
            secret=Path(folder)/'key';public=Path(folder)/'key.pub'
            REAL_RUN(['/usr/bin/minisign','-G','-W','-s',str(secret),'-p',str(public)],check=True,stdout=subprocess.DEVNULL)
            row=dict(self.row,public_key=public.read_text().splitlines()[1])
            with self.assertRaisesRegex(RuntimeError,'signature'):
                self.change(row)
        self.assertEqual((self.ensured,self.installs),([],[]))

    def test_network_refusal_does_not_install_anything(self):
        with patch.object(signeddeb.subprocess,'run',return_value=subprocess.CompletedProcess([],6)):
            with self.assertRaisesRegex(RuntimeError,'download'):
                signeddeb.change(self.row,'install',lambda:self.ensured.append(True),lambda c:self.installs.append(c))
        self.assertEqual((self.ensured,self.installs),([],[]))

    def test_architecture_without_asset_is_refused(self):
        with patch.object(signeddeb.subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'riscv64'):
                signeddeb.selected(ROW,'riscv64')
            run.assert_not_called()

    def test_native_dpkg_frontend_lock_is_detected_in_a_fresh_process(self):
        import fcntl
        script = """import importlib.util,importlib.machinery,sys
from pathlib import Path
source=Path(sys.argv[1]);sys.path.insert(0,str(source))
import common
common.LANGDIR=source/'lang'
spec=importlib.util.spec_from_loader('entry_action',importlib.machinery.SourceFileLoader('entry_action',str(source/'actions/entry')))
action=importlib.util.module_from_spec(spec);spec.loader.exec_module(action)
try:action.held({'name':'OpenLogi'})
except RuntimeError as e:print(e)
else:raise SystemExit('native frontend lock was missed')
"""
        with open('/var/lib/dpkg/lock-frontend','a+') as lock:
            fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            result=REAL_RUN([sys.executable,'-c',script,str(SOURCE)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('apt',result.stdout.lower())

    def test_both_architectures_and_ten_translations(self):
        self.assertEqual(set(ROW['assets']),{'amd64','arm64'})
        for arch in ROW['assets']:
            row=signeddeb.selected(ROW,arch)
            file=FIXTURES/Path(row['url']).name
            self.assertEqual(file.stat().st_size,row['payload_size'])
            with file.open('rb') as stream:
                self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),row['sha256'])
        for code in ('en','pl','pt_BR','fr','de','es','ja','ko','zh_CN','zh_TW'):
            data=json.loads((SOURCE/'lang'/(code+'.json')).read_text())
            for key in ('openlogi_note','signature_failed','vendor_architecture'):
                self.assertTrue(data[key],(code,key))

class Page(unittest.TestCase):
    def setUp(self):
        sys.path.append(str(SOURCE/'tests'))
        import layout
        layout.reader(SOURCE)
        import mainpages
        self.page=mainpages
        self.page.BASE=layout.assembled(SOURCE)

    def test_size_and_shared_metered_notice_precede_install_button(self):
        reader=unittest.mock.Mock()
        reader.OPTION='Sparky::Install-Downloads::Announce'
        reader.announce_mode.return_value=('always','')
        reader.assess.return_value={'announce':True,'text':['Metered connection: OpenLogi download','Continue?']}
        with patch.object(self.page.signeddeb,'installed',return_value=False), patch.object(self.page,'problem_text',return_value=''), patch.object(self.page.tools,'plan',return_value=None), patch.object(self.page,'install_downloads',return_value=reader):
            rendered=self.page.render(ROW)
        self.assertLess(rendered.index('21,743,090 B'),rendered.index('debinst_openlogi'))
        self.assertLess(rendered.index('Metered connection'),rendered.index('debinst_openlogi'))
        self.assertEqual(reader.assess.call_args.args[0][0]['size'],21743090)
        self.assertIn('Solaar',rendered)

    def test_unsupported_architecture_has_a_sentence_and_no_install_button(self):
        with patch.object(self.page.signeddeb,'selected',side_effect=RuntimeError('OpenLogi: unsupported riscv64')):
            rendered=self.page.render(ROW)
        self.assertIn('riscv64',rendered)
        self.assertNotIn('debinst_openlogi',rendered)

if __name__=='__main__':unittest.main()

