#!/usr/bin/python3
"""The store-link kind (ORDER 10): an entry that only opens a vendor's store page in the person's web browser, built for CODESYS 4 and for any
vendor after it. The card's sentences in the ten required languages, the address checked in the data (https, the vendor's own domain), the
app center's Depends unchanged, no network use by the page, the button's command as built, and the failures said.
No package manager and no network: every command is a recorded stand-in."""
import ast
import contextlib
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

SOURCE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
sys.path.append(str(Path(__file__).resolve().parent))
import layout
READER = layout.reader(SOURCE)
RECIPE = SOURCE
SOURCE = layout.assembled(SOURCE)
os.environ.pop('LANGUAGE', None)
os.environ.pop('LC_ALL', None)
import common
common.BASE = SOURCE
common.LANGDIR = SOURCE / 'lang'
import catalogue
import storelink
import mainpages
import tools

REQUIRED = ('en', 'pl', 'pt_BR', 'fr', 'de', 'es', 'ja', 'ko', 'zh_CN', 'zh_TW')
# the Depends line of 0.1.14+lc1 and of 0.1.15+lc1: a link needs nothing installed (Daniel, 2026-11-14: "only when someone install vinci - same for
# anything that needs this sort of dependancy")
DEPENDS = ('Depends: sparky-aptus-appcenter, sparky-stereo-apt (>= 20261104.3~sparky9~0), python3, python3-apt, curl, sparky-stereo-hardware, '
           'apt, dpkg, systemd, udev, kmod, pkexec, yad, sparky-stereo-problems (>= 0.1.1)')
KEYS = ('store_maker', 'store_how', 'store_address', 'store_button', 'store_no_opener', 'store_failed', 'store_no_user', 'store_bad_address',
        'store_unchangeable')
SENTENCE_KEYS = ('store_maker', 'store_how', 'store_address')


def say(code):
    """The person's messages in language CODE (the app center's own lookup)."""
    with patch.dict(os.environ, {'LANG': code + '.UTF-8'}):
        return common.messages()


def stores():
    return [row for row in catalogue.entries() if row['kind'] == 'store']


def stereo_page(code='en'):
    spec = importlib.util.spec_from_loader('store_page', importlib.machinery.SourceFileLoader('store_page', str(SOURCE / 'appcenter')))
    page = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(page)
    zram = dict(installed=False, title='zram', description='', state='absent', restart='', error='', button='Install')
    states = {row['id']: dict(installed=False, error='', visible=True, download=None) for row in catalogue.entries()}
    results = [subprocess.CompletedProcess([], 0, json.dumps(zram)), subprocess.CompletedProcess([], 0, json.dumps(states))]
    with patch.dict(os.environ, {'LANG': code + '.UTF-8'}), patch.object(page.subprocess, 'run', side_effect=results):
        return page.render()


def card(html, identifier):
    start = html.index('id="entry-%s"' % identifier)
    return html[start:html.index('</article>', start)]


class Fixed:
    """A second vendor, to show the kind is not CODESYS's: the same row shape, another domain, on a main page."""
    ROW = dict(id='exampletool', name='Example Tool', section='main', kind='store', vendor='Example GmbH', store='Example Store',
               domain='example.com', url='https://shop.example.com/tool', note='codesys4_note', page='development.html', key='devtoo')


class TheRow(unittest.TestCase):
    def test_codesys_4_is_a_row_of_data(self):
        rows = {row['id']: row for row in stores()}
        row = rows['codesys4']
        self.assertEqual((row['name'], row['section'], row['vendor'], row['store'], row['domain']),
                         ('CODESYS 4', 'media', 'CODESYS GmbH', 'CODESYS Store', 'codesys.com'))
        self.assertEqual(row['url'], 'https://store.codesys.com/en/codesys-4.html')
        # nothing to install: no package, no tools, no sizes, no download
        for key in ('package', 'tools', 'also', 'sizes', 'sha256', 'filename', 'documentation'):
            self.assertNotIn(key, row)
        self.assertEqual(tools.declared(row), [])
        self.assertEqual(tools.announced(row), [])

    def test_every_address_is_https_and_the_vendors_own(self):
        rows = stores() + [Fixed.ROW]
        for row in rows:
            parts = __import__('urllib.parse').parse.urlsplit(row['url'])
            self.assertEqual(parts.scheme, 'https', row['id'])
            self.assertTrue(parts.hostname == row['domain'] or parts.hostname.endswith('.' + row['domain']), row['id'])
            self.assertIsNone(parts.username)
            self.assertIn(parts.port, (None, 443))
            self.assertTrue(storelink.secure(row), row['id'])

    def test_the_check_refuses_what_is_not_the_vendors_own_https_address(self):
        good = dict(domain='codesys.com', url='https://store.codesys.com/en/codesys-4.html')
        self.assertTrue(storelink.secure(good))
        self.assertTrue(storelink.secure(dict(good, url='https://codesys.com/')))
        for bad in ('http://store.codesys.com/en/codesys-4.html', 'https://evilcodesys.com/', 'https://codesys.com.example.org/',
                    'https://example.org/?https://store.codesys.com/', 'https://user:secret@store.codesys.com/', 'https://store.codesys.com:8443/',
                    'https://store.codesys.com/a b', 'https://store.codesys.com/\n', ' https://store.codesys.com/', 'javascript:alert(1)',
                    'file:///etc/passwd', 'aptus://stereo_hardware', '', 'https://'):
            self.assertFalse(storelink.secure(dict(good, url=bad)), bad)
        self.assertFalse(storelink.secure(dict(good, domain='')))
        self.assertFalse(storelink.secure(dict(good, domain='com')))

    def test_the_old_hard_coded_card_is_gone(self):
        source = (SOURCE / 'appcenter').read_text()
        self.assertNotIn('codesys', source.lower())

    def test_depends_do_not_change(self):
        recipe = os.environ.get('APTUS_BUILD_SH')
        candidates = [Path(recipe)] if recipe else [RECIPE.parents[1] / 'packages/sparky-aptus-stereo-appcenter/build.sh']
        found = [path for path in candidates if path.is_file()]
        if not found:
            self.fail('the package recipe was not found: set APTUS_BUILD_SH to sparky-os/packages/sparky-aptus-stereo-appcenter/build.sh of the build tree')
        text = found[0].read_text()
        self.assertIn('\n' + DEPENDS + '\n', text)
        for field in ('Pre-Depends', 'Recommends', 'Suggests'):
            self.assertNotIn('\n' + field + ':', text)


class TheCard(unittest.TestCase):
    def test_the_ten_languages_hold_every_sentence_translated(self):
        english = say('en')
        for code in REQUIRED:
            texts = json.loads((SOURCE / 'lang' / (code + '.json')).read_text())
            for key in KEYS + ('codesys4_note',):
                self.assertTrue(texts.get(key), (code, key))
                if code != 'en':
                    self.assertNotEqual(texts[key], english[key], (code, key))
            for key in ('store_how', 'store_button', 'store_no_opener', 'store_failed', 'store_no_user'):
                self.assertIn('{store}', texts[key], (code, key))
            for key in ('store_failed', 'store_no_opener', 'store_no_user'):
                self.assertIn('{url}', texts[key], (code, key))
            self.assertIn('{vendor}', texts['store_maker'], code)
            self.assertIn('{vendor}', texts['store_how'], code)

    def test_the_stereo_page_says_everything_before_the_button_in_each_language(self):
        row = catalogue.entry('codesys4')
        for code in REQUIRED:
            text = say(code)
            article = card(stereo_page(code), 'codesys4')
            wanted = [text['codesys4_note'], text['store_maker'].format(vendor='CODESYS GmbH'),
                      text['store_how'].format(store='CODESYS Store', vendor='CODESYS GmbH'), text['store_address'].format(url=row['url'])]
            button = 'href="aptus://stereo_entry_codesys4_open"'
            self.assertIn(button, article, code)
            self.assertEqual(article.count('<a '), 1, code)
            last = -1
            for sentence in wanted:
                import html as h
                self.assertIn(h.escape(sentence), article, (code, sentence))
                position = article.index(h.escape(sentence))
                self.assertGreater(position, last)
                self.assertLess(position, article.index(button), (code, sentence))
                last = position
            self.assertIn(h.escape(text['store_button'].format(store='CODESYS Store')), article)
            self.assertIn('CODESYS GmbH', article)
            # it says that nothing is installed or downloaded, the registration and the licence of the vendor
            self.assertIn('CODESYS Store', article)

    def test_the_english_card_says_the_four_things_plainly(self):
        article = card(stereo_page('en'), 'codesys4')
        import html as h
        for words in ('opens the CODESYS Store in your web browser', 'You register there if it asks you to',
                      "under CODESYS GmbH's own licence agreement", 'installs nothing and downloads nothing', 'Made by CODESYS GmbH',
                      'web-based IEC 61131-3 development environment', 'https://store.codesys.com/en/codesys-4.html'):
            self.assertIn(h.escape(words), article)

    def test_the_card_stays_in_the_media_section_where_the_old_card_was(self):
        page = stereo_page('en')
        section = page[page.index('id="stereo-media"'):page.index('id="stereo-vr"')]
        self.assertIn('id="entry-codesys4"', section)
        self.assertEqual(page.count('id="entry-codesys4"'), 1)
        self.assertNotIn('id="codesys"', page)

    def test_the_card_has_no_state_and_no_install_button(self):
        article = card(stereo_page('en'), 'codesys4')
        for words in ('Not installed', 'Installed', 'Uninstall', '>Install<', '_install"', '_remove"', '_repair"'):
            self.assertNotIn(words, article)

    def test_the_main_page_form_for_the_next_vendor(self):
        row = Fixed.ROW
        for code in REQUIRED:
            text = say(code)
            with patch.dict(os.environ, {'LANG': code + '.UTF-8'}):
                page = mainpages.render(row)
            import html as h
            self.assertIn('<title>Development | APTus AppCenter</title>', page)
            self.assertIn('<a href="index.html">', page)
            self.assertNotIn('devtoo_bibledit', page)
            for sentence in storelink.sentences(row, text):
                self.assertIn(h.escape(sentence), page)
            self.assertIn('href="aptus://storeopen_exampletool"', page)
            self.assertLess(page.index(h.escape(text['store_how'].format(store='Example Store', vendor='Example GmbH'))),
                            page.index('aptus://storeopen_exampletool'))
        with patch.object(catalogue, 'entries', return_value=catalogue.entries() + [row]):
            self.assertEqual(catalogue.store_request('aptus://storeopen_exampletool'), row)
            self.assertIsNone(catalogue.route('aptus://stereo_entry_exampletool_install'))


class NoNetwork(unittest.TestCase):
    def test_the_pages_open_no_socket(self):
        def refuse(*args, **kwargs):
            raise AssertionError('the page used the network')
        with patch.object(socket.socket, 'connect', refuse), patch.object(socket, 'create_connection', refuse), \
                patch.object(socket, 'getaddrinfo', refuse):
            html = stereo_page('en')
            mainpages.render(Fixed.ROW)
        article = card(html, 'codesys4')
        self.assertEqual(re.findall(r'href="([^"]*)"', article), ['aptus://stereo_entry_codesys4_open'])
        self.assertNotRegex(article, r'(src|href|action)="https?:')
        self.assertNotRegex(article, r'<(img|link|script|iframe|form)\b')
        page = mainpages.render(Fixed.ROW)
        self.assertNotRegex(page[page.index('Example Tool'):page.index('storeopen_exampletool')], r'(src|href)="https?:')

    def test_the_module_imports_nothing_that_speaks_to_a_network(self):
        names = set()
        for node in ast.walk(ast.parse((SOURCE / 'storelink.py').read_text())):
            if isinstance(node, ast.Import):
                names |= {alias.name.split('.')[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module.split('.')[0])
        self.assertEqual(names, {'os', 'pwd', 'subprocess', 'tempfile', 'pathlib', 'urllib'})
        self.assertEqual({a.name for n in ast.walk(ast.parse((SOURCE / 'storelink.py').read_text())) if isinstance(n, ast.ImportFrom) and n.module == 'urllib.parse'
                          for a in n.names}, {'urlsplit'})


class TheButton(unittest.TestCase):
    ROW = None

    def setUp(self):
        self.row = catalogue.entry('codesys4')
        self.user = types.SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_dir='/home/person', pw_name='person')
        self.text = say('en')

    def test_as_the_person_the_command_is_xdg_open_and_the_address(self):
        argv, env = storelink.command(self.row, {'PATH': '/usr/bin', 'DISPLAY': ':0'}, euid=1000)
        self.assertEqual(argv, ['/usr/bin/xdg-open', 'https://store.codesys.com/en/codesys-4.html'])

    def test_as_administrator_it_drops_to_the_person_pkexec_names(self):
        with patch.object(storelink.pwd, 'getpwuid', return_value=self.user) as lookup, \
                patch.object(storelink.Path, 'glob', return_value=[Path('/run/user/1000/wayland-0'), Path('/run/user/1000/wayland-0.lock')]):
            argv, env = storelink.command(self.row, {'PKEXEC_UID': '1000', 'DISPLAY': ':0', 'XAUTHORITY': '/home/person/.Xauthority', 'LANG': 'pt_BR.UTF-8',
                                                     'SECRET_TOKEN': 'x'}, euid=0)
        lookup.assert_called_once_with(1000)
        self.assertEqual(argv, ['/usr/bin/setpriv', '--reuid', '1000', '--regid', '1000', '--init-groups', '--', '/usr/bin/xdg-open',
                                'https://store.codesys.com/en/codesys-4.html'])
        self.assertEqual(env['XDG_RUNTIME_DIR'], '/run/user/1000')
        self.assertEqual(env['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=/run/user/1000/bus')
        self.assertEqual((env['HOME'], env['USER'], env['LOGNAME'], env['PATH']), ('/home/person', 'person', 'person', '/usr/bin:/bin'))
        self.assertEqual((env['DISPLAY'], env['LANG'], env['WAYLAND_DISPLAY']), (':0', 'pt_BR.UTF-8', 'wayland-0'))
        self.assertNotIn('SECRET_TOKEN', env)
        # a desktop name pkexec dropped is not invented: xdg-open's own lookup of the person's default browser then runs
        self.assertNotIn('XDG_CURRENT_DESKTOP', env)
        self.assertNotIn('KDE_FULL_SESSION', env)
        self.assertNotIn('PKEXEC_UID', env)

    def test_administrator_without_a_person_opens_nothing(self):
        for environ in ({}, {'PKEXEC_UID': '0'}, {'PKEXEC_UID': 'x'}, {'PKEXEC_UID': '-1'}):
            launch = unittest.mock.Mock()
            with patch.object(storelink.os, 'access', return_value=True), self.assertRaises(storelink.Refused) as error:
                storelink.open_page(self.row, self.text, environ=environ, euid=0, launch=launch)
            launch.assert_not_called()
            self.assertIn('administrator', str(error.exception))
            self.assertIn(self.row['url'], str(error.exception))
            self.assertIn('Nothing was installed', str(error.exception))
        with patch.object(storelink.pwd, 'getpwuid', side_effect=KeyError(1000)), patch.object(storelink.os, 'access', return_value=True), \
                self.assertRaises(storelink.Refused):
            storelink.open_page(self.row, self.text, environ={'PKEXEC_UID': '1000'}, euid=0, launch=unittest.mock.Mock())

    def fake(self, code=0, output='', timeout=False):
        calls = []

        class Process:
            def __init__(self, argv, **kwargs):
                calls.append((argv, kwargs))
                kwargs['stdout'].write(output)
                kwargs['stdout'].flush()

            def wait(self, timeout=None):
                if timeout_flag:
                    raise subprocess.TimeoutExpired('xdg-open', timeout)
                return code
        timeout_flag = timeout
        return Process, calls

    def test_the_click_runs_xdg_open_and_nothing_else(self):
        process, calls = self.fake()
        with patch.object(storelink.os, 'access', return_value=True):
            storelink.open_page(self.row, self.text, environ={'PATH': '/usr/bin'}, euid=1000, launch=process)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ['/usr/bin/xdg-open', self.row['url']])
        self.assertIs(calls[0][1]['stdin'], subprocess.DEVNULL)
        self.assertTrue(calls[0][1]['start_new_session'])
        self.assertNotIn('shell', calls[0][1])

    def test_a_browser_still_starting_is_not_a_failure(self):
        process, calls = self.fake(timeout=True)
        with patch.object(storelink.os, 'access', return_value=True):
            storelink.open_page(self.row, self.text, environ={}, euid=1000, launch=process, wait=0.01)

    def test_failures_say_what_failed_in_each_language(self):
        for code in REQUIRED:
            text = say(code)
            process, calls = self.fake(code=3, output='xdg-open: no method available\n')
            with patch.object(storelink.os, 'access', return_value=True), self.assertRaises(storelink.Refused) as error:
                storelink.open_page(self.row, text, environ={}, euid=1000, launch=process)
            words = str(error.exception)
            self.assertIn('xdg-open exit 3: xdg-open: no method available.', words)
            self.assertIn(self.row['url'], words)
            self.assertIn('CODESYS Store', words)
            self.assertEqual(words, text['store_failed'].format(store='CODESYS Store', why='xdg-open exit 3: xdg-open: no method available.', url=self.row['url']))
            with patch.object(storelink.os, 'access', return_value=False), self.assertRaises(storelink.Refused) as error:
                storelink.open_page(self.row, text, environ={}, euid=1000, launch=process)
            self.assertEqual(str(error.exception), text['store_no_opener'].format(store='CODESYS Store', url=self.row['url']))
        self.assertEqual(len(calls), 1)

    def test_the_last_line_of_xdg_open_is_the_reason(self):
        process, calls = self.fake(code=3, output="/usr/bin/xdg-open: 1032: lynx: not found\n/usr/bin/xdg-open: 1032: w3m: not found\nxdg-open: no method available for opening 'https://x'\n")
        with patch.object(storelink.os, 'access', return_value=True), self.assertRaises(storelink.Refused) as error:
            storelink.open_page(self.row, self.text, environ={}, euid=1000, launch=process)
        self.assertIn("xdg-open exit 3: xdg-open: no method available for opening 'https://x'.", str(error.exception))
        self.assertNotIn('lynx', str(error.exception))

    def test_an_address_that_fails_the_check_is_never_opened(self):
        launch = unittest.mock.Mock()
        row = dict(self.row, url='http://store.codesys.com/en/codesys-4.html')
        with patch.object(storelink.os, 'access', return_value=True), self.assertRaises(storelink.Refused) as error:
            storelink.open_page(row, self.text, environ={}, euid=1000, launch=launch)
        launch.assert_not_called()
        self.assertEqual(str(error.exception), self.text['store_bad_address'].format(name='CODESYS 4', domain='codesys.com'))

    def test_the_stereo_click_reaches_the_handler_without_pkexec(self):
        row = catalogue.entry('codesys4')
        self.assertEqual(catalogue.store_request('aptus://stereo_entry_codesys4_open'), row)
        for uri in ('aptus://stereo_entry_codesys4_open?x=1', 'aptus://stereo_entry_codesys4_install', 'aptus://stereo_entry_bino_open',
                    'aptus://stereo_entry_codesys4_open ', 'https://store.codesys.com/en/codesys-4.html', ''):
            self.assertIsNone(catalogue.store_request(uri), uri)
        for operation in ('install', 'remove', 'repair', 'reinstall', 'open'):
            self.assertIsNone(catalogue.route('aptus://stereo_entry_codesys4_' + operation))
        source = (SOURCE / 'handler').read_text()
        recorded = []
        fake = types.ModuleType('storelink')
        fake.open_page = lambda row, text: recorded.append(row['id'])
        with patch.dict(sys.modules, storelink=fake), patch.object(sys, 'argv', ['handler', 'aptus://stereo_entry_codesys4_open']), \
                patch.object(subprocess, 'run') as run, patch.object(os, 'execv') as execv, self.assertRaises(SystemExit) as stop:
            exec(compile(source, 'handler', 'exec'), {'__name__': '__main__'})
        self.assertEqual(stop.exception.code, 1)
        self.assertEqual(recorded, ['codesys4'])
        run.assert_not_called()
        execv.assert_not_called()

    def test_a_failed_click_shows_the_sentence_in_a_window(self):
        source = (SOURCE / 'handler').read_text()
        fake = types.ModuleType('storelink')

        def refuse(row, text):
            raise storelink.Refused('the sentence')
        fake.open_page = refuse
        with patch.dict(sys.modules, storelink=fake), patch.object(sys, 'argv', ['handler', 'aptus://stereo_entry_codesys4_open']), \
                patch.object(subprocess, 'run') as run, self.assertRaises(SystemExit):
            exec(compile(source, 'handler', 'exec'), {'__name__': '__main__'})
        self.assertEqual(run.call_args.args[0], ['yad', '--error', '--title=APTus AppCenter', '--text=the sentence'])


class NothingToChange(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_loader('entry_action2', importlib.machinery.SourceFileLoader('entry_action2', str(SOURCE / 'actions/entry')))
        self.action = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.action)

    def test_a_link_is_never_installed_and_always_shown(self):
        row = catalogue.entry('codesys4')
        self.assertFalse(self.action.installed(row))
        self.assertTrue(self.action.visible(row, {}, set()))
        self.assertEqual(self.action.tools_note([row], {row['id']: False}), {})

    def test_the_changing_action_refuses_a_link(self):
        for operation in ('install', 'remove', 'repair', 'reinstall', '--install', '--remove'):
            with patch.object(sys, 'argv', ['entry', 'codesys4', operation]), patch.object(self.action.subprocess, 'run') as run, \
                    patch.object(sys, 'stderr', new=__import__('io').StringIO()) as stderr:
                self.assertEqual(self.action.main(), 2)
            run.assert_not_called()
            self.assertIn('link to the store page of CODESYS GmbH', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
