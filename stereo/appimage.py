# SPDX-FileCopyrightText: 2026 Daniel Ramos (Capitain Jack)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verified AppImages, installed for all users without touching their data."""
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from common import messages


def paths(row):
    base = Path('/opt') / row['id']
    return base, {
        Path('/usr/bin') / row['id']: base / 'application.AppImage',
        Path('/usr/share/applications') / (row['desktop'] + '.desktop'): base / 'application.desktop',
        Path('/usr/share/icons/hicolor/scalable/apps') / (row['desktop'] + '.svg'): base / 'application.svg',
    }


def installed(row):
    base, _ = paths(row)
    marker = base / '.aptus-managed'
    image = base / 'application.AppImage'
    if not marker.is_file() or not image.is_file():
        return False
    with image.open('rb') as stream:
        return marker.read_text().strip() == row['id'] and hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']


def change(row, operation):
    text = messages()
    base, links = paths(row)
    marker = base / '.aptus-managed'
    if base.is_symlink() or (base.exists() and (not marker.is_file() or marker.read_text().strip() != row['id'])):
        raise RuntimeError(text['appimage_payload'])
    if operation == 'remove':
        for link, target in links.items():
            if link.is_symlink() and os.readlink(link) == str(target):
                link.unlink()
        if base.exists():
            shutil.rmtree(base)
        for filename in row.get('remove_files', []):
            Path(filename).unlink(missing_ok=True)
        return
    minimum = row.get('min_glibc', '2.39')
    if platform.machine() != 'x86_64':
        raise RuntimeError(text['appimage_platform'].format(version=minimum))
    version = os.confstr('CS_GNU_LIBC_VERSION').split()[-1]
    if tuple(map(int, version.split('.'))) < tuple(map(int, minimum.split('.'))):
        raise RuntimeError(text['appimage_platform'].format(version=minimum))
    for link, target in links.items():
        if (link.exists() or link.is_symlink()) and not (link.is_symlink() and os.readlink(link) == str(target)):
            raise RuntimeError(text['appimage_payload'])
    with tempfile.TemporaryDirectory(prefix='aptus-appimage-') as directory:
        work = Path(directory)
        image = work / 'application.AppImage'
        subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                        '--connect-timeout', '30', '--max-time', '600', '--output', str(image), row['url']], check=True)
        with image.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise RuntimeError(text['checksum_failed'])
        image.chmod(0o755)
        desktop = 'usr/share/applications/' + row['desktop'] + '.desktop'
        icon = 'usr/share/icons/hicolor/scalable/apps/' + row['desktop'] + '.svg'
        for wanted in (desktop, icon):
            subprocess.run([str(image), '--appimage-extract', wanted], cwd=work, check=True, stdout=subprocess.DEVNULL)
            if not (work / 'squashfs-root' / wanted).is_file():
                raise RuntimeError(text['appimage_payload'])
        subprocess.run(['apt-get', '-y', '--no-remove', '--no-install-recommends', 'install', *row['dependencies']], check=True)
        for command in row['commands']:
            if shutil.which(command) is None:
                raise RuntimeError(text['appimage_requirements'].format(command=command))
        base.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.' + row['id'] + '-', dir=base.parent) as staging:
            new = Path(staging) / 'new'
            new.mkdir(mode=0o755)
            shutil.copy2(image, new / 'application.AppImage')
            shutil.copyfile(work / 'squashfs-root' / desktop, new / 'application.desktop')
            shutil.copyfile(work / 'squashfs-root' / icon, new / 'application.svg')
            for name in ('application.desktop', 'application.svg'):
                (new / name).chmod(0o644)
            (new / '.aptus-managed').write_text(row['id'] + '\n')
            old = Path(staging) / 'old'
            created = []
            try:
                if base.exists():
                    base.rename(old)
                new.rename(base)
                for link, target in links.items():
                    link.parent.mkdir(parents=True, exist_ok=True)
                    if not link.is_symlink():
                        link.symlink_to(target)
                        created.append(link)
            except OSError:
                for link in created:
                    link.unlink()
                if base.exists():
                    shutil.rmtree(base)
                if old.exists():
                    old.rename(base)
                raise
