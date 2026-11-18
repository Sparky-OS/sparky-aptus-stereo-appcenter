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
import storelink
import signeddeb


def request(uri):
    for row in main_entries():
        if uri == f'aptus://{row["key"]}_{row["id"]}':
            return row, None
        for prefix, action in (('debinst', 'install'), ('debrein', 'reinstall'), ('debremo', 'remove')):
            if uri == f'aptus://{prefix}_{row["id"]}':
                return row, action
    return None


def problem_text(owner, key):
    """The sentences the one engine keeps for OWNER's problem KEY (all of OWNER's when KEY is None), in the person's language."""
    problems = subprocess.run(['/usr/bin/sparky-stereo-problems', 'list', '--json', owner],
                              capture_output=True, text=True, check=True)
    records = json.loads(problems.stdout)
    if isinstance(records, dict):
        records = records.get('problems', [])
    return '\n'.join(record.get('text', record.get('text_en', '')) + '\n' + record.get('output', '')
                     for record in records if key is None or record['key'] == key)


def apt_state(row):
    """What the action says about an apt entry without the cost of the whole page: installed, the tools and the install-time
    download of its package (sizes said first), or the reason they cannot be read."""
    result = subprocess.run([str(BASE / 'actions/entry'), 'status', row['id']], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or 'actions/entry status: %d' % result.returncode)
    return json.loads(result.stdout)


def render(row):
    text, main, e = messages(), BASE / 'main', html.escape
    if row['kind'] == 'apt':
        return render_apt(row, text, main, e)
    if row['kind'] == 'store':
        return render_store(row, text, main, e)
    if row['kind'] == 'signed-deb':
        try:
            row = signeddeb.selected(row)
        except RuntimeError as error:
            return in_page(row, text, main, e, '<p>' + e(str(error)) + '</p>')
    selected = signeddeb.installed(row) if row['kind'] == 'signed-deb' else appimage.installed(row)
    errors = problem_text(PACKAGE, row['id'])
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
    return in_page(row, text, main, e, f'''<p><b>{e(row['name'])}</b></p><p>{e(text[row['id'] + '_note'])}</p>
<p>{e(row.get('author', 'Dionatan Simioni'))} · {e(row['version'])}</p>
<p>{e(text['download_size'])}: {row['size']:,} B</p>{needs}
<p>{e(text['installed' if selected else 'absent'])}</p>
<div style="color:#9a1818;white-space:pre-wrap">{e(errors)}</div>{lines}<p>{buttons}</p>''')


def in_page(row, text, main, e, card):
    """Retain the main page's header, navigation, language script, style and footer around the entry's card."""
    page = (main / row['page']).read_text()
    table = re.search(r'<table\b[^>]*>', page)
    if table is None or '</table>' not in page[table.end():]:
        raise RuntimeError(text['appimage_payload'])
    before = page[:table.start()]
    after = page[page.index('</table>', table.end()) + len('</table>'):]
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


def render_apt(row, text, main, e):
    """An entry that installs a package of the edition: what it brings is said before the button, with apt's sizes and the
    package's own install-time download (its size and where it comes from), then the metered notice when the setting asks for it."""
    state = apt_state(row)
    selected = state['installed']
    errors = '\n'.join(filter(None, [problem_text(PACKAGE, row['id']), problem_text(row['package'], None)]))
    lines = ''
    if not selected:
        if state.get('tools') and state['tools'].get('error'):
            errors = '\n'.join(filter(None, [errors, state['tools']['error']]))
        elif state.get('tools'):
            lines += ''.join('<p class="tools">' + e(line) + '</p>' for line in state['tools']['text'])
        note = state.get('download')
        if note and note.get('error'):
            errors = '\n'.join(filter(None, [errors, note['error']]))
        elif note:
            lines += ''.join('<p>' + e(line) + '</p>' for line in note['text'])
        elif state.get('declared'):
            lines += ''.join('<p>' + e(line) + '</p>' for line in state['declared'])
    operation, label = ('debremo', 'remove') if selected else ('debinst', 'install')
    buttons = f'<a class="buttonmenu" href="aptus://{operation}_{row["id"]}">{e(text[label])}</a>'
    return in_page(row, text, main, e, f'''<p><b>{e(row['name'])}</b></p><p>{e(text[row['id'] + '_note'])}</p>
<p>{e(row.get('author', ''))}</p>{lines}
<p>{e(text['installed' if selected else 'absent'])}</p>
<div style="color:#9a1818;white-space:pre-wrap">{e(errors)}</div><p>{buttons}</p>''')


def render_store(row, text, main, e):
    """An entry that is a link to the vendor's store page: what the program is, who makes it, what the button does and what it does not, the
    address as text; the button is an aptus:// address that the handler opens with the person's browser. The page reads nothing from the network."""
    lines = ''.join('<p>' + e(line) + '</p>' for line in storelink.sentences(row, text))
    button = f'<a class="buttonmenu" href="aptus://storeopen_{row["id"]}">{e(text["store_button"].format(store=row["store"]))}</a>'
    return in_page(row, text, main, e, f'''<p><b>{e(row['name'])}</b></p>{lines}<p>{button}</p>''')
