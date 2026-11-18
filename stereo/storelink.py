# SPDX-FileCopyrightText: 2026 Daniel Campos Ramos
# SPDX-License-Identifier: GPL-3.0-or-later
"""The store-link kind: an entry that only opens a vendor's store page in the person's web browser.
Nothing of the vendor's is fetched, installed or hosted. The address lives in the entry's row and is checked here, at the click,
the way the tests check it in the data: https, no credentials, and the vendor's own domain."""
import os
import pwd
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

XDG_OPEN = '/usr/bin/xdg-open'
SETPRIV = '/usr/bin/setpriv'
# what the person's session needs for a program started from here to find the running desktop; pkexec keeps few of these
SESSION = ('DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_CURRENT_DESKTOP', 'KDE_FULL_SESSION', 'XDG_SESSION_TYPE',
           'LANG', 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES')
WAIT = 8


class Refused(RuntimeError):
    """The store page was not opened; the text says what failed, why and what to do."""


def secure(row):
    """True when the row's address is https, carries no credentials or port, and is on the vendor's own domain (the domain or a subdomain of it)."""
    address = row.get('url', '')
    if not isinstance(address, str) or address != address.strip() or any(ord(c) <= 32 or ord(c) == 127 for c in address):
        return False
    parts = urlsplit(address)
    domain = row.get('domain', '').lower()
    host = (parts.hostname or '').lower()
    try:
        port = parts.port
    except ValueError:
        return False
    return (parts.scheme == 'https' and bool(domain) and '.' in domain and port in (None, 443)
            and parts.username is None and parts.password is None
            and (host == domain or host.endswith('.' + domain)))


def sentences(row, text):
    """The card's sentences, before the button: what the program is, who makes it, what the button does and what it does not."""
    return [text[row['note']],
            text['store_maker'].format(vendor=row['vendor']),
            text['store_how'].format(store=row['store'], vendor=row['vendor']),
            text['store_address'].format(url=row['url'])]


def target(environ=os.environ, euid=None):
    """(the user the browser is opened for, or None when this program already runs as that user)."""
    if (os.geteuid() if euid is None else euid) != 0:
        return None
    raw = environ.get('PKEXEC_UID', '')
    if not raw.isdigit() or int(raw) == 0:
        return False
    try:
        return pwd.getpwuid(int(raw))
    except KeyError:
        return False


def command(row, environ=os.environ, euid=None):
    """(the argument list and the environment that open ROW's address with the person's default browser). Run as root (the app
    center starts through pkexec), the program drops to the user pkexec names, never opens a browser as root."""
    user = target(environ, euid)
    if user is False:
        raise Refused(None)
    if user is None:
        return [XDG_OPEN, row['url']], dict(environ)
    uid = user.pw_uid
    runtime = '/run/user/%d' % uid
    env = {key: environ[key] for key in SESSION if key in environ}
    env.update(PATH='/usr/bin:/bin', HOME=user.pw_dir, USER=user.pw_name, LOGNAME=user.pw_name,
               XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS='unix:path=%s/bus' % runtime)
    if 'WAYLAND_DISPLAY' not in env:
        sockets = sorted(p.name for p in Path(runtime).glob('wayland-[0-9]*') if not p.name.endswith('.lock'))
        if sockets:
            env['WAYLAND_DISPLAY'] = sockets[0]
    return [SETPRIV, '--reuid', str(uid), '--regid', str(user.pw_gid), '--init-groups', '--', XDG_OPEN, row['url']], env


def open_page(row, text, environ=os.environ, euid=None, launch=subprocess.Popen, wait=WAIT):
    """Open ROW's store page with the default browser, as the person. Raises Refused with a sentence in the person's language, and
    returns when the browser took the address (xdg-open exited 0, or is still starting the browser after WAIT seconds)."""
    fields = dict(name=row['name'], store=row['store'], vendor=row['vendor'], url=row['url'], domain=row['domain'])
    if not secure(row):
        raise Refused(text['store_bad_address'].format(**fields))
    if not os.access(XDG_OPEN, os.X_OK):
        raise Refused(text['store_no_opener'].format(**fields))
    try:
        argv, env = command(row, environ, euid)
    except Refused:
        raise Refused(text['store_no_user'].format(**fields))
    with tempfile.TemporaryFile('w+') as output:
        process = launch(argv, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            return
        if code:
            output.seek(0)
            lines = [' '.join(line.split()) for line in output.read().splitlines() if line.strip()]
            tail = lines[-1][-300:] if lines else ''   # xdg-open's own verdict is its last line; the lines above are the helpers it tried
            why = 'xdg-open exit %d%s.' % (code, ': ' + tail if tail else '')
            raise Refused(text['store_failed'].format(why=why, **fields))
