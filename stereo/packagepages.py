# SPDX-FileCopyrightText: 2026 Daniel Campos Ramos
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native package details, using the shared install-download notice."""
import html
import json
import re
from pathlib import Path
from common import BASE, messages, language, install_downloads

PROFILES=Path('/usr/share/sparky-install-models/profiles')
MODEL_MESSAGES=Path('/usr/share/sparky-install-models/messages.json')


def profile_entry(identifier):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',identifier):
        raise StopIteration(identifier)
    path=PROFILES/(identifier+'.json')
    if not path.is_file() or path.is_symlink():raise StopIteration(identifier)
    record=json.loads(path.read_text())
    if record['package']!=identifier:raise ValueError(identifier)
    return dict(id=identifier,package=identifier,name=record['title'],section='profiles',kind='apt',model_profile=True)


def render(row):
    import apt
    import apt_pkg
    apt_pkg.init_config()
    reader=install_downloads();text=messages();e=html.escape
    cache=apt.Cache();name=row['package'];package=cache[name] if name in cache else None
    candidate=package.candidate if package else None
    installed=bool(package and package.is_installed)
    errors=[]
    if not candidate:errors.append(text['edition_missing'].format(name=name))
    notice='';details=''
    if candidate:
        details='<p>'+e(candidate.version)+'</p><p>'+e(candidate.description)+'</p>'
        declaration=reader.declaration(candidate.record)
        if declaration:
            details+='<p>'+e(text['download_size'])+': '+e(reader.human(declaration['size']))+' ('+str(declaration['size'])+' B)</p><p>'+e(declaration['source'])+'</p>'
            mode,problem=reader.announce_mode(apt_pkg.config.find(reader.OPTION,''))
            if problem:raise RuntimeError(problem)
            assessed=reader.assess([dict(declaration,package=name,version=candidate.version)],mode,'asked')
            if assessed['announce']:
                notice=''.join('<p>'+e(line)+'</p>' for line in assessed['text'][:-1])
    if row.get('model_profile'):
        model_text=json.loads(MODEL_MESSAGES.read_text());model_text=model_text.get(language(),model_text['en'])
        notice+='<p>'+e(model_text['purge'].format(package=name))+'</p>'
    buttons=''
    if candidate:
        operation,label=('debremo','remove') if installed else ('debinst','install')
        buttons=f'<a class="buttonmenu" href="aptus://{operation}_{e(row["id"])}">{e(text[label])}</a>'
        if installed:buttons+=f' <a class="buttonmenu" href="aptus://debrein_{e(row["id"])}">{e(text["reinstall"])}</a>'
    main=BASE/'main';page=(main/'graphics-editors.html').read_text()
    table=re.search(r'<table\b[^>]*>',page)
    if table is None:raise ValueError('graphics-editors.html')
    before=page[:table.start()];after=page[page.index('</table>',table.end())+len('</table>'):]
    card=f'<p><b>{e(row["name"])}</b></p><p>{e(text["spirula_note"])}</p>{details}<p>{e(text["installed" if installed else "absent"])}</p>'
    card+='<div style="color:#9a1818;white-space:pre-wrap">'+e('\n'.join(errors))+'</div>'+notice+'<p>'+buttons+'</p>'
    return before.replace('<head>','<head><meta charset="utf-8"><base href="'+main.as_uri()+'/">')+card+after
