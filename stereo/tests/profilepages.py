#!/usr/bin/python3
"""Profile pages use shared metering and package-owned declarations."""
import json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import layout
source=Path(__file__).resolve().parents[1];layout.reader(source)
import common
source=layout.assembled(source);common.BASE=source;common.LANGDIR=source/'lang'
import packagepages,mainpages,catalogue
packagepages.BASE=source

class Profiles(unittest.TestCase):
    def test_only_declared_literal_profile_names_are_offered(self):
        with tempfile.TemporaryDirectory() as work,patch.object(packagepages,'PROFILES',Path(work)):
            path=Path(work)/'spirula-studio-model-fixture.json'
            path.write_text(json.dumps(dict(package='spirula-studio-model-fixture',title='Fixture')))
            row=catalogue.entry('spirula-studio-model-fixture')
            self.assertTrue(row['model_profile'])
            self.assertEqual(mainpages.request('aptus://debinst_spirula-studio-model-fixture'),(row,'install'))
            for name in ['../fixture','absent','-oFoo','spirula-studio-model-fixture?accept=1']:
                with self.assertRaises(StopIteration):packagepages.profile_entry(name)
            path.unlink();path.symlink_to('/etc/passwd')
            with self.assertRaises(StopIteration):packagepages.profile_entry('spirula-studio-model-fixture')
    def test_metered_notice_and_purge_are_visible_before_install(self):
        import apt_pkg
        apt_pkg.init_config()
        reader=common.install_downloads()
        record={'Sparky-Install-Download-Size':'2997054','Sparky-Install-Download-Source':'https://example.invalid/publisher-model'}
        candidate=types.SimpleNamespace(version='1+lc1',description='Fixture profile',record=record)
        row=dict(id='spirula-studio-model-fixture',package='spirula-studio-model-fixture',name='Fixture',model_profile=True)
        with tempfile.TemporaryDirectory() as work:
            words=Path(work)/'words.json';words.write_text(json.dumps({'en':{'purge':'Purge deletes {package} models.'}}))
            with patch.dict(sys.modules,apt=types.SimpleNamespace(Cache=lambda:{row['package']:types.SimpleNamespace(candidate=candidate,is_installed=False)})),patch.object(packagepages,'MODEL_MESSAGES',words),patch.object(reader,'metered',return_value=('yes','fixture')):
                page=packagepages.render(row)
            self.assertIn('2.9 MiB',page)
            self.assertIn('https://example.invalid/publisher-model',page)
            self.assertIn('Purge deletes spirula-studio-model-fixture models.',page)
            self.assertIn('aptus://debinst_spirula-studio-model-fixture',page)
            self.assertNotIn('--consented',page)
if __name__=='__main__':unittest.main(verbosity=2)
