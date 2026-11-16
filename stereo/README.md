
The shared zram action activates dev-zram0.swap immediately after installation.
It stops the swap before its setup service and removes the package only after both stops succeed.
The complete operation runs under the shared problems engine so a failed start, stop or package change retains the same repair until it succeeds.
A restart is mentioned only when systemd is not running, with that reason.

Removal checks the setup service’s Result and the device’s disksize, because systemctl stop can succeed when ExecStop fails.
A failed reset leaves the package installed and a repair in the engine.
The explicit repair retries Debian’s device reset only after swap is inactive, then removes the package.

Removal temporarily masks the swap unit at runtime while APT runs: its logind inhibitor can otherwise pull the stopped swap back in. Existing runtime masks are retained; only the action’s own mask is released, including on failure. Final swap inactivity is checked after APT.
The mask is installed only after swapoff and setup reset have completed. Reloading a mask on an active generated swap can remove the ordering that keeps reset behind swapoff.

The start page lists edition packages from sparky-os/lists in the 3D emulation, stereo tools and VR sections.
Package actions read the generated /etc/apt/preferences.d/sparky-stereo-only-ours policy supplied by sparky-stereo-apt.
Only names covered for the native architecture require a trusted Sparky Stereo OS candidate.
Other names use APT's candidate from the configured signed archives; unavailable names are omitted from the page.
Only-ours names stay visible with their retained failure and Repair when the edition candidate is missing.
Installation requests the exact candidate version and explicitly refuses unauthenticated packages.
An unavailable edition candidate is a retained problem, never a request for Debian's replacement.
The system Flathub remote supplies SlimeVR; this package never adds a remote.
The SlimeVR OpenVR Driver ZIP is offered as a verified download in /var/cache/sparky-aptus-stereo-appcenter.
It is marked Downloaded, not Installed: SlimeVR's linked instructions explain registration in the person's SteamVR installation.
The checksum is pinned to the v6.0.0 release asset digest from GitHub's release API.
Hardware Setup owns the NVIDIA and AMD choices.
CODESYS 4 is a store link, with registration and the EULA managed by CODESYS.
Every recognized changing action runs under the existing problems engine, with a fixed repair command.
All other URIs and extra arguments pass to Paweł's installed handler unchanged.

An entry that is not installed shows, beside its button, the install-time downloads it brings: the packages apt would install for it (python-apt marks them in memory, nothing changes) whose control file declares Sparky-Install-Download-Size and Sparky-Install-Download-Source, with the size and the source, on a metered connection (NetworkManager says yes or guess-yes) and also, said, when NetworkManager cannot be read.
The declaration, the metered test, the setting Sparky::Install-Downloads::Announce and the words in the nine languages are those of sparky-stereo-apt's reader (/usr/lib/sparky-stereo-apt/sparky_install_downloads.py), the same one apt's own notice uses: one declaration, one reader, two front ends. A package that cannot be read is an error the page shows, never a missing note.
FlightGear is an entry since 0.1.4: its data downloader, flightgear-data-installer, declares 1.75 GiB from SourceForge.

An entry's tools arrive with the entry (0.1.9).
A program an entry offers may need packages to run: Vinci needs podman, distrobox, fuse3 and bsdextrautils, KamLynk needs fuse3, a Flatpak entry needs flatpak.
The entry declares them (`tools` in its row; `KIND_TOOLS` in tools.py for a whole kind), and the package never depends on them, so a system that never installs the entry never gets them.
tools.py is the one mechanism: `plan` reads `apt-get -s` for the tools that are missing (the packages apt would install, their download and disk sizes, their archive) and refuses with apt's reason when one cannot be installed; `lines` says it on the entry's page and in the action's output before anything starts; `download` hands the same plan to sparky-stereo-apt's reader, so the metered notice names the program's download and the tools' together; `ensure` downloads every archive, then installs; `release` runs when the entry is removed.
The order of an AppImage entry is: plan and say, download the program and verify it, the tools, then the placement; a failure at any step is said and leaves no application.
Tools that are already installed are left alone: no reinstall, no upgrade, no notice.
Only a mark changes: a declared tool that apt had installed automatically is marked manual while the entry is installed, because apt's autoremove could otherwise take it from under the program.
Removing an entry removes no tool: the ones the entry brought or marked (recorded in /var/lib/sparky-aptus-stereo-appcenter/tools) are marked as automatically installed unless another installed entry declares them, and apt's own rule decides from there; the entry names the ones it brought.
An installation that fails after its tools arrived does the same.

DisplayCAL is an entry of the Tools and utilities section since 0.1.10 (ORDER 575).
It is offered and not installed: nothing on the image depends on it, because its colour measuring needs calibrator hardware (a colorimeter or a spectrophotometer), which the card says beside the button.
The row is `"sizes": true`: tools.py simulates the entry's own program the way the action installs it (Debian's displaycal with its Recommends, and what it depends on, ArgyllCMS among it) and the card and the action say apt's sizes first.
`actions/entry status ID` answers for one entry without the cost of the whole page; the Info Centre's Stereo 3D and Deep Colour page asks it for DisplayCAL and runs `pkexec actions/entry displaycal install` from its button.
An install that fails says why in the person's language: apt busy (the lock is held), no network, a package the sources do not offer, or apt's exit status with its own lines above.

## Tests

`python3 tests/entries.py`, `tools.py`, `displaycal.py` and `zram.py` run with no package manager and no network; run them where python3-apt is installed (a container).
What the package gets from elsewhere is found by `tests/layout.py`: the reader of the install-time download declaration (sparky-stereo-apt) from `SPARKY_INSTALL_DOWNLOADS_LIB`, the edition's build tree beside this folder, or the installed package, and Paweł's pages (`main/`), which it lays down from the tracked tree `9/` with `package_main.py` into a folder removed at exit.
When one of them is missing the test stops and names it.
The ten required languages hold every key of English; the eleven older page languages hold the sentences of the older versions and read the rest in English.
