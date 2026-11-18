# SPDX-FileCopyrightText: 2026 Daniel Ramos (Capitain Jack)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The package-owned allowlist shared by the page and privileged action."""
import json
from common import BASE


def entries():
    return json.loads((BASE / 'catalogue.json').read_text()) + main_entries()


def main_entries():
    return json.loads((BASE / 'main-entries.json').read_text())


def entry(identifier):
    return next(row for row in entries() if row['id'] == identifier)


def route(uri):
    for row in entries():
        if row['kind'] == 'store':
            continue
        for operation in ('install', 'remove', 'repair', 'reinstall'):
            if uri == f"aptus://stereo_entry_{row['id']}_{operation}":
                return [str(BASE / 'actions/entry'), row['id'], operation]
    return None


def store_request(uri):
    """The store-link entry that URI opens (the stereo page's button or a main page's), or None. It changes nothing on the system, so it has no route."""
    for row in entries():
        if row['kind'] == 'store' and uri in (f"aptus://stereo_entry_{row['id']}_open", f"aptus://storeopen_{row['id']}"):
            return row
    return None
