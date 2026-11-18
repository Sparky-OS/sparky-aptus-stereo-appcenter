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
    for row in entries():
        if row['id']==identifier:return row
    from packagepages import profile_entry
    return profile_entry(identifier)


def route(uri):
    for row in entries():
        for operation in ('install', 'remove', 'repair', 'reinstall'):
            if uri == f"aptus://stereo_entry_{row['id']}_{operation}":
                return [str(BASE / 'actions/entry'), row['id'], operation]
    return None
