#!/usr/bin/python3
"""The actual installed URI entry point opens a page and requires normal admin authorization."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parents[1]/'packageuri.py'
spec=importlib.util.spec_from_file_location('package_route',path)
route=importlib.util.module_from_spec(spec);spec.loader.exec_module(route)
class Uri(unittest.TestCase):
    def test_only_a_literal_debian_package_name(self):
        self.assertEqual(route.package('aptus://graedi_spirula-studio-model-sam3-q4-0'),'spirula-studio-model-sam3-q4-0')
        for uri in ['aptus://graedi_--help','aptus://graedi_x;id','aptus://graedi_x?yes=1','aptus://graedi_x%20y','aptus://main_x','file:///etc/passwd']:
            with self.assertRaises(ValueError):route.package(uri)
    def test_unprivileged_route_authenticates_the_same_page(self):
        uri='aptus://graedi_spirula-studio-model-sam3-q4-0'
        with patch.object(route.os,'geteuid',return_value=1000),patch.object(route.os,'execv',side_effect=SystemExit) as run:
            with self.assertRaises(SystemExit):route.open_page(uri)
            self.assertEqual(run.call_args.args,('/usr/bin/pkexec',['/usr/bin/pkexec',route.LAUNCHER,'--open-package',uri]))
    def test_authorized_route_only_opens_the_package_page(self):
        with patch.object(route.os,'geteuid',return_value=0),patch.object(route.os,'execv',side_effect=SystemExit) as run:
            with self.assertRaises(SystemExit):route.open_page('aptus://graedi_spirula-studio-model-aliked-n16rot')
            self.assertEqual(run.call_args.args[1],[route.BASE+'/main-entry','spirula-studio-model-aliked-n16rot'])
if __name__=='__main__':unittest.main(verbosity=2)
