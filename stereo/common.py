# SPDX-FileCopyrightText: 2026 Daniel Ramos (Capitain Jack)
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import re
import sys
from pathlib import Path

PACKAGE = 'sparky-aptus-stereo-appcenter'
BASE = Path('/usr/lib') / PACKAGE
ACTION = str(BASE / 'actions/zram')
LANGDIR = Path('/usr/share/sparky') / PACKAGE


def language():
    candidates = os.environ.get('LANGUAGE', '').split(':')
    candidates += [os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG', 'en')]
    for candidate in candidates:
        code = candidate.split('.')[0].split('@')[0]
        if not re.fullmatch(r"[A-Za-z]{2,3}(?:_[A-Za-z0-9]+)?", code):
            continue
        for name in (code, code.split('_')[0]):
            if (LANGDIR / (name + '.json')).is_file():
                return name
    return 'en'


def messages():
    text = json.loads((LANGDIR / 'en.json').read_text())
    text.update(json.loads((LANGDIR / (language() + '.json')).read_text()))
    return text


def install_downloads():
    """The one reader of the install-time download declaration (sparky-stereo-apt): the same code, declaration and words as
    apt's own notice. Its absence is an error the page shows, never a silently missing note."""
    sys.path.insert(0, os.environ.get('SPARKY_INSTALL_DOWNLOADS_LIB', '/usr/lib/sparky-stereo-apt'))
    import sparky_install_downloads
    if 'SPARKY_INSTALL_DOWNLOADS_LANG' not in os.environ:
        sparky_install_downloads.LANGDIR = str(LANGDIR / 'install-downloads')
    return sparky_install_downloads


def problem_records():
    """Read the store as this authorized package caller."""
    import subprocess
    env=dict(os.environ,PATH='/usr/sbin:/usr/bin:/sbin:/bin')
    env.pop('PKEXEC_UID',None)
    result=subprocess.run(['/usr/bin/sparky-stereo-problems','list','--json',PACKAGE],capture_output=True,text=True,check=True,env=env)
    records=json.loads(result.stdout)
    if isinstance(records,dict):records=records.get('problems',[])
    return records


def problem_text(identifier):
    """The shared problems engine is the source of an entry's failure text."""
    records=problem_records()
    return '\n'.join(record.get('text',record.get('text_en',''))+'\n'+record.get('output','') for record in records if record['key']==identifier)
