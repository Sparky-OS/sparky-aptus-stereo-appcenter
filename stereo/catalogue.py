# SPDX-FileCopyrightText: 2026 Daniel Ramos (Capitain Jack)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The package-owned allowlist shared by the page and privileged action."""
import json
from common import BASE


def entries():
    return json.loads((BASE / 'catalogue.json').read_text())


def entry(identifier):
    return next(row for row in entries() if row['id'] == identifier)


def route(uri):
    for row in entries():
        for operation in ('install', 'remove', 'repair'):
            if uri == f"aptus://stereo_entry_{row['id']}_{operation}":
                return [str(BASE / 'actions/entry'), row['id'], operation]
    return None
