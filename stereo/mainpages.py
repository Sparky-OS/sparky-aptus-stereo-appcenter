# SPDX-FileCopyrightText: 2026 Daniel Campos Ramos
# SPDX-License-Identifier: GPL-3.0-or-later
"""Localized vendor entries reached from the same main pages and protocol keys."""
import html
import json
import os
from pathlib import Path
import signal
import re
import subprocess
import tempfile
from common import BASE, PACKAGE, messages, language, install_downloads
from catalogue import main_entries
import appimage
import tools


def request(uri):
    for row in main_entries():
        if uri == f'aptus://{row["key"]}_{row["id"]}':
            return row, None
        for prefix, action in (('debinst', 'install'), ('debrein', 'reinstall'), ('debremo', 'remove')):
            if uri == f'aptus://{prefix}_{row["id"]}':
                return row, action
    return None


def render(row):
    text, main, e = messages(), BASE / 'main', html.escape
    selected = appimage.installed(row)
    problems = subprocess.run(['/usr/bin/sparky-stereo-problems', 'list', '--json', PACKAGE],
                              capture_output=True, text=True, check=True)
    records = json.loads(problems.stdout)
    if isinstance(records, dict):
        records = records.get('problems', [])
    errors = '\n'.join(record.get('text', record.get('text_en', '')) + '\n' + record.get('output', '')
                       for record in records if record['key'] == row['id'])
    reader = install_downloads()
    import apt_pkg
    apt_pkg.init_config()
    mode, problem = reader.announce_mode(apt_pkg.config.find(reader.OPTION, ''))
    if problem:
        raise RuntimeError(problem)
    # the tools this entry brings, with apt's sizes, said before the person installs; a tool that cannot be installed is said too
    downloads, needs = [dict(package=row['name'], version=row['version'], size=row['size'], source=row['url'])], ''
    if not selected:
        try:
            found = tools.plan(row)
        except tools.Refused as error:
            found, errors = None, '\n'.join(filter(None, [errors, str(error)]))
        if found:
            downloads.append(tools.download(found))
            needs = ''.join('<p class="tools">' + e(line) + '</p>' for line in tools.lines(row, found))
    notice = reader.assess(downloads, mode, 'asked')
    lines = ''.join('<p>' + e(line) + '</p>' for line in notice['text'][:-1]) if notice['announce'] else ''
    operation, label = ('debremo', 'remove') if selected else ('debinst', 'install')
    buttons = f'<a class="buttonmenu" href="aptus://{operation}_{row["id"]}">{e(text[label])}</a>'
    if selected:
        buttons += f' <a class="buttonmenu" href="aptus://debrein_{row["id"]}">{e(text["reinstall"])}</a>'
    # Retain the main page's header, navigation, language script, style and footer.
    page = (main / row['page']).read_text()
    table = re.search(r'<table\b[^>]*>', page)
    if table is None or '</table>' not in page[table.end():]:
        raise RuntimeError(text['appimage_payload'])
    before = page[:table.start()]
    after = page[page.index('</table>', table.end()) + len('</table>'):]
    card = f'''<p><b>{e(row['name'])}</b></p><p>{e(text[row['id'] + '_note'])}</p>
<p>Dionatan Simioni · {e(row['version'])}</p>
<p>{e(text['download_size'])}: {row['size']:,} B</p>{needs}
<p>{e(text['installed' if selected else 'absent'])}</p>
<div style="color:#9a1818;white-space:pre-wrap">{e(errors)}</div>{lines}<p>{buttons}</p>'''
    return before.replace('<head>', '<head><meta charset="utf-8"><base href="' + main.as_uri() + '/">') + card + after


def handle(row, operation):
    if operation:
        command = [str(BASE / 'actions/entry'), row['id'], operation]
        if os.geteuid() != 0:
            command.insert(0, '/usr/bin/pkexec')
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            saved = subprocess.run(['/usr/bin/sparky-stereo-problems', 'list', '--json', PACKAGE],
                                   capture_output=True, text=True, check=True)
            records = json.loads(saved.stdout)
            if isinstance(records, dict):
                records = records.get('problems', [])
            if not any(record.get('key') == row['id'] for record in records):
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or
                                   str(subprocess.CalledProcessError(result.returncode, command)))
    if os.environ.get('YAD_PID', '').isdigit():
        replace_window([str(BASE / 'main-entry'), row['id']])
        return
    show(row)


def replace_window(command):
    child_env = dict(os.environ)
    child_env.pop('YAD_PID', None)
    subprocess.Popen(command, env=child_env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    if os.environ.get('YAD_PID', '').isdigit():
        os.kill(int(os.environ['YAD_PID']), signal.SIGUSR1)


def show(row):
    with tempfile.TemporaryDirectory(prefix='aptus-main-entry-') as directory:
        page = Path(directory) / 'index.html'
        page.write_text(render(row))
        code = {'pt_BR': 'pt'}.get(language(), language())
        if not (BASE / 'main/lang/main' / (code + '.js')).exists():
            code = 'en'
        subprocess.run(['yad', '--html', '--browser', '--width=900', '--height=780',
                        '--title=APTus AppCenter', '--uri=' + page.as_uri(), '--user-agent=' + code,
                        '--uri-handler=' + str(BASE / 'handler')])
