"""Where a test finds what the package gets from elsewhere.

The page imports the one reader of the install-time download declaration (sparky-stereo-apt) and reads Paweł's pages from
`main/`, which the package build lays down from the tracked tree `9/` (package_main.py). Neither is in this folder, so a test
finds them here, or stops and says which one is missing. Run the tests where python3-apt is installed (a container).
"""
import atexit
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def reader(source):
    """The folder of sparky_install_downloads.py: SPARKY_INSTALL_DOWNLOADS_LIB, the edition's build tree beside the source, or the installed package."""
    candidates = []
    if os.environ.get('SPARKY_INSTALL_DOWNLOADS_LIB'):
        candidates.append(Path(os.environ['SPARKY_INSTALL_DOWNLOADS_LIB']))
    candidates += [source.parents[1] / 'packages/sparky-stereo-apt/install-downloads', Path('/usr/lib/sparky-stereo-apt')]
    for folder in candidates:
        if (folder / 'sparky_install_downloads.py').is_file():
            os.environ['SPARKY_INSTALL_DOWNLOADS_LIB'] = str(folder)
            for words in (folder / 'lang', Path('/usr/share/sparky/sparky-stereo-apt/install-downloads')):
                if (words / 'en.json').is_file():
                    os.environ['SPARKY_INSTALL_DOWNLOADS_LANG'] = str(words)
                    break
            return folder
    sys.exit('sparky_install_downloads.py not found in ' + ', '.join(map(str, candidates)) + ': set SPARKY_INSTALL_DOWNLOADS_LIB to the folder of sparky-stereo-apt\'s reader')


def assembled(source):
    """The source with Paweł's pages laid down as the package build does, in a folder removed at exit; a tree that has main/ is returned as it is."""
    if (source / 'main').is_dir():
        return source
    tracked = source.parent / '9'
    if not (tracked / 'lib/sparky-aptus-appcenter').is_dir():
        sys.exit('no main/ in ' + str(source) + ' and no tracked tree ' + str(tracked) + ' to lay it down from')
    work = Path(tempfile.mkdtemp(prefix='aptus-stereo-tests-'))
    atexit.register(shutil.rmtree, work, True)
    tree = work / 'stereo'
    shutil.copytree(source, tree, ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    root = work / 'root'
    subprocess.run([sys.executable, '-I', str(source / 'package_main.py'), str(tracked), str(root)], check=True)
    shutil.move(str(root / 'usr/lib/sparky-aptus-stereo-appcenter/main'), str(tree / 'main'))
    shutil.move(str(root / 'usr/share/sparky/sparky-aptus-stereo-appcenter/main'), str(tree / 'lang/main'))
    shutil.copytree(source / 'tests', tree / 'tests')
    return tree
