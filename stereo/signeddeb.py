# SPDX-FileCopyrightText: 2026 Daniel Campos Ramos
# SPDX-License-Identifier: GPL-3.0-or-later
"""Vendor Debian packages authenticated before any installation."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit
from common import messages
import tools


def selected(row, architecture=None):
    if architecture is None:
        architecture = subprocess.run(['/usr/bin/dpkg', '--print-architecture'],
                                      capture_output=True, text=True, check=True).stdout.strip()
    if architecture not in row['assets']:
        raise RuntimeError(messages()['vendor_architecture'].format(name=row['name'], architecture=architecture))
    return dict(row, **row['assets'][architecture])


def installed(row):
    return tools.present(row['package'])


def change(row, operation, ensure_tools, run_apt):
    text = messages()
    if operation == 'remove':
        run_apt(['/usr/bin/apt-get', '-y', 'remove', row['package']])
        return
    with tempfile.TemporaryDirectory(prefix='aptus-signed-deb-') as folder:
        work = Path(folder)
        package = work / Path(row['url']).name
        signature = work / (package.name + '.minisig')
        for url, target in ((row['url'], package), (row['url'] + '.minisig', signature)):
            result = subprocess.run(['/usr/bin/curl', '--fail', '--location', '--proto', '=https',
                                     '--proto-redir', '=https', '--connect-timeout', '30', '--max-time', '600',
                                     '--output', str(target), url])
            if result.returncode:
                raise RuntimeError(text['download_failed'].format(name=row['name'], host=urlsplit(url).hostname,
                                                                  code=result.returncode))
        with package.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if package.stat().st_size != row['size'] or digest != row['sha256']:
            raise RuntimeError(text['checksum_failed'])
        # An absent verifier is extracted from authenticated apt archives, never installed before trust is checked.
        with tools.staged_command(row, 'minisign') as (verifier, environment):
            checked = subprocess.run([verifier, '-V', '-P', row['public_key'], '-m', str(package), '-x', str(signature)],
                                     env=environment, capture_output=True, text=True)
        if checked.returncode:
            raise RuntimeError(text['signature_failed'].format(name=row['name']))
        ensure_tools()
        run_apt(['/usr/bin/apt-get', '-y', '--no-remove', '--no-install-recommends', '--no-allow-unauthenticated',
                 'install', str(package)])
