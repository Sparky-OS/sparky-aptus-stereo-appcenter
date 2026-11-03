# SPDX-FileCopyrightText: 2026 Daniel Ramos (Capitain Jack)
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import re
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
    return json.loads((LANGDIR / (language() + '.json')).read_text())
