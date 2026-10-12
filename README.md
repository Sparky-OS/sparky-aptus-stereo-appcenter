Sparky Stereo OS:
-----------------

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23309032.svg)](https://doi.org/10.5281/zenodo.23309032)

This is the stereo version of Sparky APTus AppCenter by Sparky Stereo OS, forked
from sparkylinux/sparky-aptus-appcenter
(https://github.com/sparkylinux/sparky-aptus-appcenter). It adds the edition's
entries to the application catalogue.

Where it comes from:

- Sparky APTus AppCenter (https://github.com/sparkylinux/sparky-aptus-appcenter)
  is made by Paweł Pijanowski and others; see the copyright file.
- Debian (https://www.debian.org/) is the base of the system.
- SparkyLinux (https://sparkylinux.org/), by Paweł "pavroo" Pijanowski, builds
  on Debian.
- Sparky Stereo OS (https://github.com/Sparky-OS/sparky-stereo-os) is the stereo
  3D edition of SparkyLinux: SparkyOS, powered by Debian.

The master branch holds the version the distribution builds. The licence is
unchanged: GNU GPL version 3 or later, as stated below.

Sparky Stereo OS, Daniel Ramos's edition of SparkyLinux (by Paweł "pavroo" Pijanowski).


Sparky APTus AppCenter
This tool helps you keep your system up to date and clean, install and remove packages. It is a lightweight gui frontend to APT and DPKG tools.

Copyright (C) 2020-2026 Paweł Pijanowski and others, see copyright file.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Dependencies:
-------------
adduser apt coreutils curl dconf-cli dctrl-tools dialog dpkg gdebi-core gettext-base gpg grep gawk iputils-ping libc6 (>= 2.31) sparky-apt sparky-desktop-data sparky-editor sparky-info sparky-remsu (>= 0.2.14) sparky-xterm spterm ssft teamspeak-installer vmplayer-installer vrms wget yad (>= 5.0~sparky6~0) zenity

Install:
-------------
su (or sudo) 
./install.sh

Uninstall:
-------------
su (or sudo)
./install.sh uninstall
