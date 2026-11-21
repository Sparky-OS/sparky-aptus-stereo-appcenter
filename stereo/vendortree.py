# SPDX-FileCopyrightText: 2026 Daniel Ramos (Capitain Jack)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A maker's prebuilt program that has no source we can build, fetched from the maker on the person's machine.

The row names a pinned file list (vendor/NAME.json): the maker's address at one commit, and for every file its size, its SHA-256
and its mode. Nothing is rebuilt, changed or mirrored: each file is fetched from the maker's address, checked against the list,
and only then put in place, all at once. The maker's own updater is not run and not removed; the installed copy is the pinned
one, and a newer version arrives by a newer pin.

    plan       what will be downloaded: the files, the size once (identical files are fetched once), the address
    installed  the marker, every file present at its size and SHA-256, the links
    change     install: licence first, then the files, then everything is checked, then placed; remove: what this entry placed
A maker who publishes one archive of the program (a tar file) instead of a tree of files: the pinned list names it ("archive":
its file name under the maker's address, its size and the maker's SHA-256) and lists the files inside it as for a tree. The
archive is fetched once, checked, unpacked in the work folder (regular files and folders only, nothing outside its own top
folder), every listed file is checked again against the list, and only then is the tree placed, as for any tree.
"""
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit
import common
from common import messages

NAME = re.compile(r'[a-z0-9][a-z0-9-]*')
RELATIVE = re.compile(r'[A-Za-z0-9._+@-]+(?:/[A-Za-z0-9._+@ -]+)*')
HEX = re.compile(r'[0-9a-f]{64}')
CURL = ['/usr/bin/curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
        '--fail-early', '--connect-timeout', '30', '--max-time', '1800', '--silent', '--show-error']


class Damaged(RuntimeError):
    """The pinned list is not what the catalogue says it is."""


def prefix(row):
    return Path(row.get('prefix', '/opt/' + row['id']))


def listing(row):
    """The pinned file list, read only when it is the file the row's hash names, with a shape that cannot reach outside the folder."""
    path = common.BASE / 'vendor' / (row['manifest'])
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != row['manifest_sha256']:
        raise Damaged(messages()['tree_manifest_failed'].format(name=row['name']))
    found = json.loads(data)
    if found.get('format') != 1 or found.get('id') != row['id'] or not urlsplit(found['base']).scheme == 'https':
        raise Damaged(messages()['tree_manifest_failed'].format(name=row['name']))
    archive = found.get('archive')
    if archive is not None and not (isinstance(archive, dict) and RELATIVE.fullmatch(archive.get('file', '')) and '/' not in archive['file']
                                    and HEX.fullmatch(archive.get('sha256', '')) and isinstance(archive.get('size'), int)
                                    and NAME.fullmatch(archive.get('root', '')) and 'dest' not in row.get('licence', {})):
        raise Damaged(messages()['tree_manifest_failed'].format(name=row['name']))
    seen = set()
    for each in found['files']:
        if not (RELATIVE.fullmatch(each['dest']) and RELATIVE.fullmatch(each['src']) and HEX.fullmatch(each['sha256'])
                and isinstance(each['size'], int) and each['mode'] in ('0644', '0755')
                and not any(part in ('.', '..') for part in each['dest'].split('/'))) or each['dest'] in seen:
            raise Damaged(messages()['tree_manifest_failed'].format(name=row['name']))
        seen.add(each['dest'])
    return found


def unique(found):
    """One file for each different content: the maker's tree holds the same bytes twice (the Unity player, in the updater's folder)."""
    once = {}
    for each in found['files']:
        once.setdefault(each['sha256'], each)
    return list(once.values())


def download_size(row):
    found = listing(row)
    if found.get('archive'):
        return found['archive']['size']
    return sum(each['size'] for each in unique(found))


def unpacked_size(found):
    return sum(each['size'] for each in found['files'])


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def links(row):
    """{link: target} for what the row puts outside its folder."""
    base = prefix(row)
    found = {}
    for link, target in row.get('launcher', {}).items():
        found[Path(link)] = base / target
    if row.get('desktop'):
        found[Path('/usr/share/applications') / (row['desktop'] + '.desktop')] = base / 'application.desktop'
    return found


def marker_text(row):
    return '%s\n%s\n%s\n' % (row['id'], row['version'], row['manifest_sha256'])


def installed(row):
    try:
        found = listing(row)
    except (Damaged, OSError, ValueError, KeyError):
        return False
    base = prefix(row)
    marker = base / '.aptus-managed'
    if base.is_symlink() or not marker.is_file() or marker.read_text() != marker_text(row):
        return False
    for each in found['files']:
        path = base / each['dest']
        if path.is_symlink() or not path.is_file() or path.stat().st_size != each['size'] or digest(path) != each['sha256']:
            return False
    return all(link.is_symlink() and os.readlink(link) == str(target) for link, target in links(row).items())


def adapter():
    """Whether a Bluetooth adapter is present (/sys/class/bluetooth lists one hciN entry for each)."""
    try:
        return any(name.startswith('hci') for name in os.listdir('/sys/class/bluetooth'))
    except OSError:
        return False


def hints(row):
    """Sentences for the entry's page about this computer: said, never left to a blank window."""
    found = []
    if row.get('bluetooth') and not adapter():
        found.append(messages()['tree_no_bluetooth'].format(name=row['name']))
    return found


def facts(row):
    """What the person is told before the download: size, address, pin and licence."""
    found = listing(row)
    licence = row['licence']
    if found.get('archive'):
        return messages()['tree_facts_archive'].format(
            size=size_text(download_size(row)), host=urlsplit(found['base']).hostname, file=found['archive']['file'],
            sha256=found['archive']['sha256'][:16], unpacked=size_text(unpacked_size(found)), licence=licence['name'],
            holder=licence['holder'])
    return messages()['tree_facts'].format(
        size=size_text(download_size(row)), host=urlsplit(found['base']).hostname, commit=found['commit'][:12],
        manifest=row['manifest_sha256'][:16], licence=licence['name'], holder=licence['holder'])


def size_text(count):
    value = float(count)
    for unit in ('B', 'KiB', 'MiB', 'GiB'):
        if value < 1024 or unit == 'GiB':
            return ('%d %s' % (value, unit)) if unit == 'B' else ('%.1f %s' % (value, unit))
        value /= 1024


def room(row, found, work):
    """The archive and its unpacked files, and the tree placed beside them, fit where they go: said before the download."""
    need = download_size(row) + 2 * unpacked_size(found)
    free = shutil.disk_usage(work).free
    if free < need:
        raise RuntimeError(messages()['tree_no_room'].format(name=row['name'], size=size_text(need), free=size_text(free),
                                                            path=prefix(row).parent))


def unpack(row, found, path, folder):
    """The archive into FOLDER: regular files and folders only, each under the archive's own top folder; a link, a device, a path
    that leaves the folder or a damaged archive refuses the whole installation, with what was wrong."""
    root = found['archive']['root']
    try:
        with tarfile.open(path, 'r:*') as archive:
            for member in archive:
                parts = member.name.split('/')
                if member.name.startswith('/') or '..' in parts or parts[0] != root or not (member.isfile() or member.isdir()):
                    raise ValueError(member.name)
                target = folder.joinpath(*[part for part in parts if part not in ('', '.')])
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('wb') as stream:
                    shutil.copyfileobj(source, stream)
    except (tarfile.TarError, lzma.LZMAError, EOFError, OSError, ValueError) as error:
        raise RuntimeError(messages()['tree_extract_failed'].format(name=row['name'], file=found['archive']['file'], why=error))


def fetch_archive(row, found, work, say=print):
    """The maker's archive once into the work folder, checked against its pinned SHA-256, unpacked, and every listed file checked
    again; the checked files then wait in WORK by their SHA-256, as a tree's files do."""
    text = messages()
    archive = found['archive']
    room(row, found, work)
    path = work.parent / 'archive'
    result = subprocess.run(CURL + ['--output', str(path), found['base'] + archive['file']])
    if result.returncode:
        raise RuntimeError(text['download_failed'].format(name=row['name'], host=urlsplit(found['base']).hostname, code=result.returncode))
    if not path.is_file() or path.stat().st_size != archive['size'] or digest(path) != archive['sha256']:
        raise RuntimeError(text['tree_checksum_failed'].format(name=row['name'], file=archive['file']))
    unpacked = work.parent / 'unpacked'
    unpacked.mkdir()
    unpack(row, found, path, unpacked)
    path.unlink()
    for each in unique(found):
        source = unpacked / each['src']
        if source.is_symlink() or not source.is_file() or source.stat().st_size != each['size'] or digest(source) != each['sha256']:
            raise RuntimeError(text['tree_checksum_failed'].format(name=row['name'], file=each['dest']))
        source.rename(work / each['sha256'])
    shutil.rmtree(unpacked)


def fetch(row, found, work, say=print):
    """Every different file of the list into WORK, one curl for the whole set (one connection), then each one checked against the list.
    A file that is missing, of another size or of another SHA-256 refuses the whole installation."""
    if found.get('archive'):
        return fetch_archive(row, found, work, say)
    text = messages()
    todo = unique(found)
    command = list(CURL)
    for each in todo:
        command += ['--output', str(work / each['sha256']), found['base'] + each['src'].replace(' ', '%20')]
    result = subprocess.run(command)
    if result.returncode:
        raise RuntimeError(text['download_failed'].format(name=row['name'], host=urlsplit(found['base']).hostname, code=result.returncode))
    for each in todo:
        path = work / each['sha256']
        if not path.is_file() or path.stat().st_size != each['size'] or digest(path) != each['sha256']:
            raise RuntimeError(text['tree_checksum_failed'].format(name=row['name'], file=each['dest']))


def licence_first(row, found, work, say=print):
    """The maker's licence, fetched from the maker and shown before the large download: the person reads it, nobody accepts it for them."""
    text = messages()
    if 'dest' not in row['licence']:
        return  # a maker's archive: the licence is named in the facts said before the download
    each = next(each for each in found['files'] if each['dest'] == row['licence']['dest'])
    path = work / 'licence'
    result = subprocess.run(CURL + ['--output', str(path), found['base'] + each['src']])
    if result.returncode:
        raise RuntimeError(text['download_failed'].format(name=row['name'], host=urlsplit(found['base']).hostname, code=result.returncode))
    if path.stat().st_size != each['size'] or digest(path) != each['sha256']:
        raise RuntimeError(text['tree_checksum_failed'].format(name=row['name'], file=each['dest']))
    say(text['tree_licence_title'].format(name=row['name'], licence=row['licence']['name']))
    say(path.read_text())


def desktop_file(row):
    """The menu entry; its comment in every language the catalogue has a sentence for."""
    lines = ['[Desktop Entry]', 'Version=1.0', 'Type=Application', 'Name=' + row['name'],
             'Exec=' + str(prefix(row) / row['exec']), 'Icon=' + row.get('icon', 'application-x-executable'),
             'Terminal=false', 'Categories=' + row.get('categories', 'Utility;')]
    key = row['comment']
    for path in sorted(common.LANGDIR.glob('*.json')):
        sentence = json.loads(path.read_text()).get(key)
        if sentence and path.stem != 'en':
            lines.append('Comment[%s]=%s' % (path.stem, ' '.join(sentence.split())))
    lines.insert(5, 'Comment=' + ' '.join(json.loads((common.LANGDIR / 'en.json').read_text())[key].split()))
    return '\n'.join(lines) + '\n'


def change(row, operation, ensure_tools=None, say=print):
    text = messages()
    base = prefix(row)
    marker = base / '.aptus-managed'
    wanted = links(row)
    if base.is_symlink() or (base.exists() and (not marker.is_file() or marker.read_text().split('\n')[0] != row['id'])):
        try:
            archived = bool(listing(row).get('archive'))
        except (Damaged, OSError, ValueError, KeyError):
            archived = False
        # a copy the person placed there (a maker's archive is often unpacked by hand): said as what it is, never replaced
        raise RuntimeError(text['tree_not_ours'].format(name=row['name'], path=base) if archived else text['appimage_payload'])
    if operation == 'remove':
        for link, target in wanted.items():
            if link.is_symlink() and os.readlink(link) == str(target):
                link.unlink()
        if base.exists():
            shutil.rmtree(base)
        say(text['tree_removed'].format(name=row['name']))
        return
    minimum = row.get('min_glibc', '2.39')
    if platform.machine() != 'x86_64':
        raise RuntimeError(text['appimage_platform'].format(version=minimum))
    version = os.confstr('CS_GNU_LIBC_VERSION').split()[-1]
    if tuple(map(int, version.split('.'))) < tuple(map(int, minimum.split('.'))):
        raise RuntimeError(text['appimage_platform'].format(version=minimum))
    for link, target in wanted.items():
        if (link.exists() or link.is_symlink()) and not (link.is_symlink() and os.readlink(link) == str(target)):
            raise RuntimeError(text['appimage_payload'])
    found = listing(row)
    for line in hints(row):
        say(line)
    base.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aptus-tree-', dir=base.parent) as directory:
        work = Path(directory)
        (work / 'blobs').mkdir()
        say(facts(row))
        licence_first(row, found, work, say)
        fetch(row, found, work / 'blobs', say)
        if ensure_tools:
            ensure_tools()
        new = work / 'new'
        new.mkdir(mode=0o755)
        for each in found['files']:
            target = new / each['dest']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(work / 'blobs' / each['sha256'], target)
            target.chmod(int(each['mode'], 8))
        for folder in [new, *[p for p in new.rglob('*') if p.is_dir()]]:
            folder.chmod(0o755)
        if row.get('desktop'):
            (new / 'application.desktop').write_text(desktop_file(row))
            (new / 'application.desktop').chmod(0o644)
        (new / '.aptus-managed').write_text(marker_text(row))
        old = work / 'old'
        created = []
        try:
            if base.exists():
                base.rename(old)
            new.rename(base)
            for link, target in wanted.items():
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
    say(text['tree_installed' if row.get('desktop') else 'tree_installed_library'].format(name=row['name'], path=base))
