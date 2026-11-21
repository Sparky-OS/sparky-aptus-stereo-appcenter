# SPDX-FileCopyrightText: 2026 Daniel Campos Ramos
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the tracked main tree in the edition's namespace, keeping stock files intact."""
from pathlib import Path
import shutil
import sys

source, root = map(Path, sys.argv[1:])
base = '/usr/lib/sparky-aptus-stereo-appcenter'
data = '/usr/share/sparky/sparky-aptus-stereo-appcenter'
main = root / base.lstrip('/') / 'main'
shutil.copytree(source / 'lib/sparky-aptus-appcenter', main)
shutil.copytree(source / 'share/sparky/sparky-aptus-appcenter', root / data.lstrip('/') / 'main')
shutil.copy2(source / 'bin/sparky-aptus-appcenter', main / 'launcher')
replacements = {
    '/usr/lib/sparky-aptus-appcenter': base + '/main',
    '/usr/share/sparky/sparky-aptus-appcenter': data + '/main',
    '/usr/bin/sparky-aptus-appcenter': base + '/main/launcher',
}
for path in main.rglob('*'):
    if not path.is_file() or path.is_symlink():
        continue
    raw = path.read_bytes()
    if b'\0' in raw:
        continue
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        continue
    for old, new in replacements.items():
        text = text.replace(old, new)
    if text.encode() != raw:
        path.write_bytes(text.encode())
(main / 'handler').rename(main / 'handler.stock')
(main / 'handler').write_text('#!/bin/sh\nexec /usr/lib/sparky-aptus-stereo-appcenter/handler "$@"\n')
(main / 'handler').chmod(0o755)
(main / 'SOURCE').write_text('Upstream: https://github.com/sparkylinux/sparky-aptus-appcenter\nCommit: e886632f98c6b65e4ab9794cad96e45047cb0d1d\nTree: 9\nEdition changes are tracked in the source checkout selected by the build gitlink.\n')

# Keep direct backend calls on the edition's translated, metered, shared action.
for name, action in (('aptus-app', None), ('aptus-package-install', 'install'),
                     ('aptus-package-reinstall', 'reinstall'), ('aptus-package-remove', 'remove')):
    path = main / 'bin' / name
    text = path.read_text()
    first, rest = text.split('\n', 1)
    command = (base + '/main-entry "$1"') if action is None else (base + '/actions/entry "$1" ' + action)
    guard = 'case "$1" in vinci|kamlynk|vibe) exec ' + command + ' ;; esac\n'
    path.write_text(first + '\n' + guard + rest)

# Main's empty selector is its Applications/Home destination; retain the edition's tabs there.
path = main / 'aptus-appcenter'
first, rest = path.read_text().split('\n', 1)
path.write_text(first + '\nif [ "$#" -eq 0 ]; then exec ' + base + '/appcenter; fi\n' + rest)
