# SPDX-FileCopyrightText: 2026 Daniel Campos Ramos
# SPDX-License-Identifier: GPL-3.0-or-later
"""Open a native package page from an application, before any install action."""
import os
import re

BASE = '/usr/lib/sparky-aptus-stereo-appcenter'
LAUNCHER = '/usr/bin/sparky-aptus-stereo-appcenter'


def package(uri):
    match = re.fullmatch(r'aptus://graedi_([a-z0-9][a-z0-9+.-]*)', uri)
    if not match:
        raise ValueError(uri)
    return match[1]


def open_page(uri):
    name = package(uri)
    if os.geteuid() != 0:
        os.execv('/usr/bin/pkexec',['/usr/bin/pkexec',LAUNCHER,'--open-package',uri])
    program = BASE + '/main-entry'
    os.execv(program,[program,name])
