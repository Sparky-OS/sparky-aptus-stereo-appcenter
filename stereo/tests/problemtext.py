#!/usr/bin/python3
"""The authorized package reader does not inherit pkexec's direct-call marker."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
path=Path(__file__).resolve().parents[1]/'common.py'
spec=importlib.util.spec_from_file_location('shared_common',path)
common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)

class Problems(unittest.TestCase):
    def test_authorized_read_has_no_inherited_marker(self):
        with patch.dict(os.environ,PKEXEC_UID='1000'),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],0,'[]','')) as read:
            self.assertEqual(common.problem_records(),[])
        self.assertNotIn('PKEXEC_UID',read.call_args.kwargs['env'])
        self.assertEqual(read.call_args.args[0],['/usr/bin/sparky-stereo-problems','list','--json',common.PACKAGE])

    def test_saved_failure_text_is_preserved(self):
        with patch.object(common,'problem_records',return_value=[dict(key='ours',text='The profile failed.',output='Hash mismatch.'),dict(key='other',text='Other')]):
            self.assertEqual(common.problem_text('ours'),'The profile failed.\nHash mismatch.')

    def test_engine_read_failure_is_not_hidden(self):
        with patch.object(subprocess,'run',side_effect=subprocess.CalledProcessError(2,['sparky-stereo-problems'])):
            with self.assertRaises(subprocess.CalledProcessError):common.problem_records()

if __name__=='__main__':unittest.main()
