# SPDX-FileCopyrightText: 2026 Daniel Ramos (Capitain Jack)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The tools an entry's program needs, brought by the entry's own action when the person installs that entry.

An entry declares them once, as package names ("tools" in its row; an entry kind may declare them for all its entries).
The app center package never depends on them: a system that never installs the entry never gets them.

    plan     what apt would install for the tools that are missing, with apt's own sizes (a simulation, nothing changes);
             it refuses, with apt's reason, when a tool cannot be installed
    lines    the sentences that say it, for the entry's page and the action's output
    download the same plan as a row of the install-time download notice (the metered notice of sparky-stereo-apt's reader)
    ensure   downloads, then installs, the missing tools; a failure is said and stops the entry. A tool that is there
             already is left as it is, except its mark: one apt installed automatically is marked manual while the entry
             is installed, or apt's autoremove could take it from under the program
    release  when the entry is removed: the tools it brought or marked stay, marked as automatically installed again unless
             another installed entry needs them, so apt's own rule decides when they go
"""
import json
import os
from pathlib import Path
import re
import subprocess
from common import PACKAGE, messages

APT = '/usr/bin/apt-get'
OPTIONS = ['--no-remove', '--no-install-recommends', '--no-allow-unauthenticated']
RECORDS = Path('/var/lib') / PACKAGE / 'tools'
# what an entry of a kind needs before its own installer can run
KIND_TOOLS = {'flatpak': ['flatpak']}
INST = re.compile(r'^Inst (\S+) (?:\[[^\]]*\] )?\((\S+) (.*?)\s*\[[^\]]+\]\)')
ENV = dict(os.environ, PATH='/usr/sbin:/usr/bin:/sbin:/bin', DEBIAN_FRONTEND='noninteractive')
ENV.pop('PKEXEC_UID', None)


class Refused(RuntimeError):
    """A tool cannot be installed; the text says what failed, why and what to do."""


def declared(row):
    return list(row.get('tools', KIND_TOOLS.get(row['kind'], [])))


def present(name):
    result = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${db:Status-Status}', name], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip())
    return result.returncode == 0 and result.stdout == 'installed'


def missing(row):
    return [name for name in declared(row) if not present(name)]


def automatic(name):
    result = subprocess.run(['/usr/bin/apt-mark', 'showauto', name], capture_output=True, text=True, check=True, env=ENV)
    return name in result.stdout.split()


def human(count):
    if count >= 1 << 30:
        return '%.2f GiB' % (count / (1 << 30))
    if count >= 1 << 20:
        return '%.1f MiB' % (count / (1 << 20))
    return '%.1f KiB' % (count / 1024)


def sizes(packages):
    """Download size and added disk space of (name, version) pairs, from apt's own records, in bytes."""
    import apt_pkg
    apt_pkg.init()
    cache = apt_pkg.Cache(None)
    download = disk = 0
    for name, wanted in packages:
        base, _, arch = name.partition(':')
        package = cache[base, arch] if arch else cache[base]
        version = next(each for each in package.version_list if each.ver_str == wanted)
        download += version.size
        disk += version.installed_size - (package.current_ver.installed_size if package.current_ver else 0)
    return download, disk


def plan(row):
    """None when the entry needs no tool that is missing. Otherwise what apt would install for the missing ones:
    {tools, packages [(name, version)], download, disk, sources}. Nothing is changed."""
    names = missing(row)
    if not names:
        return None
    result = subprocess.run([APT, '-s', *OPTIONS, 'install', *names], capture_output=True, text=True, env=ENV)
    if result.returncode:
        said = [line[3:].strip().rstrip('.') for line in (result.stderr + result.stdout).splitlines() if line.startswith('E: ')]
        raise Refused(messages()['tools_unavailable'].format(name=row['name'], tools=', '.join(names),
                                                             why=('; '.join(said) or 'apt-get: %d' % result.returncode) + '.'))
    packages, sources = [], []
    for line in result.stdout.splitlines():
        found = INST.match(line)
        if not found:
            continue
        packages.append((found.group(1), found.group(2)))
        for origin in found.group(3).split(', '):
            origin = origin.split(':')[0]
            if origin and origin not in sources:
                sources.append(origin)
    absent = [name for name in names if name not in [package.split(':')[0] for package, _ in packages]]
    if absent:
        raise Refused(messages()['tools_unavailable'].format(name=row['name'], tools=', '.join(absent),
                                                             why='apt-get -s: ' + ' '.join(result.stdout.split()[-12:]) + '.'))
    download, disk = sizes(packages)
    return {'tools': names, 'packages': packages, 'download': download, 'disk': disk, 'sources': sources}


def lines(row, found):
    """What the person reads before anything starts: the tools, how many packages they bring and apt's sizes."""
    if not found:
        return []
    text = messages()
    said = [text['tools_needed'].format(name=row['name'], tools=', '.join(found['tools'])),
            text['tools_sizes'].format(count=len(found['packages']), source=', '.join(found['sources']) or 'apt',
                                       download=human(found['download']), disk=human(max(found['disk'], 0)))]
    if row.get('size'):
        said.append(text['tools_total'].format(name=row['name'], size=human(found['download'] + row['size'])))
    return said


def download(found):
    """The plan as a row of the install-time download notice: one reader, one metered test, the same words."""
    return {'package': ', '.join(found['tools']), 'version': '', 'size': found['download'],
            'source': ', '.join(found['sources']) or 'apt'}


def record(identifier):
    return RECORDS / (identifier + '.json')


def brought(identifier):
    path = record(identifier)
    return json.loads(path.read_text()) if path.is_file() else []


def answered_elsewhere(name, identifier):
    """Another entry's record names this tool: that entry marked or brought it, and this one needs it too."""
    if not RECORDS.is_dir():
        return False
    return any(name in json.loads(path.read_text()) for path in RECORDS.glob('*.json') if path.stem != identifier)


def ensure(row, found):
    """Install the missing tools: every archive is downloaded first, so a failed download changes nothing. Then record
    what this entry answers for: the tools it installed, and the ones that were there but only as automatic packages."""
    names, text = (found['tools'] if found else []), messages()
    if names:
        said = dict(name=row['name'], tools=', '.join(names))
        fetched = subprocess.run([APT, '-y', '--download-only', *OPTIONS, 'install', *names], env=ENV)
        if fetched.returncode:
            raise Refused(text['tools_download_failed'].format(code=fetched.returncode, **said))
        installed = subprocess.run([APT, '-y', *OPTIONS, 'install', *names], env=ENV)
        still = [name for name in names if not present(name)]
        if installed.returncode or still:
            raise Refused(text['tools_failed'].format(code=installed.returncode, **dict(said, tools=', '.join(still or names))))
    held = [name for name in declared(row) if name not in names and automatic(name)]
    if held:
        subprocess.run(['/usr/bin/apt-mark', 'manual', *held], check=True, env=ENV, stdout=subprocess.DEVNULL)
    # a tool another entry already answers for is shared: whichever of the two is removed last gives the mark back
    shared = [name for name in declared(row) if name not in names + held and answered_elsewhere(name, row['id'])]
    if names or held or shared:
        RECORDS.mkdir(mode=0o755, parents=True, exist_ok=True)
        record(row['id']).write_text(json.dumps(sorted(set(brought(row['id'])) | set(names) | set(held) | set(shared))) + '\n')


def release(row, needed_elsewhere):
    """The entry is gone. The tools it brought or marked stay installed; those no other installed entry needs are marked as
    automatically installed, so apt offers to remove them only when nothing else needs them. Nothing is removed here."""
    path = record(row['id'])
    names = [name for name in brought(row['id']) if present(name) and name not in needed_elsewhere]
    if names:
        subprocess.run(['/usr/bin/apt-mark', 'auto', *names], check=True, env=ENV, stdout=subprocess.DEVNULL)
        print(messages()['tools_kept'].format(name=row['name'], tools=', '.join(names)), flush=True)
    path.unlink(missing_ok=True)
