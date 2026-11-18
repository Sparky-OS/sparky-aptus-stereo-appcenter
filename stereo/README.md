
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
CODESYS 4 is a store link, of the kind `store` since 0.1.15 (ORDER 10): a link to the vendor's own store page and nothing else.
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

PJeOffice Pro is an entry of Office, Documents since 0.1.13 (ORDER 18), the first package entry of a main page (`kind: apt`, `section: main`, `sizes: true`, `problem_key: install`).
It installs sparky-pjeoffice, whose setup fetches CNJ's program from CNJ's own address; the package declares that download (`Sparky-Install-Download-Size`, `Sparky-Install-Download-Source`), so the card says before the button, whatever the metered setting is, its size and address (`declared_lines`), then apt's sizes for the package and what it depends on and recommends (OpenSC, pcscd and libccid come with it as the package's Recommends: the app center package depends on none of them), then the shared metered notice when the setting asks for it.
`actions/entry status ID` answers for it (installed, tools, download, declared) and the page reads that. A failed setup shows the engine's own sentence for the package (`kept_problem`, the row's `problem_key`) after apt's exit status.
Paweł's page carries the link (`aptus://offdoc_pjeoffice`) in both trees.

DisplayCAL is an entry of the Tools and utilities section since 0.1.10 (ORDER 575).
It is offered and not installed: nothing on the image depends on it, because its colour measuring needs calibrator hardware (a colorimeter or a spectrophotometer), which the card says beside the button.
The row is `"sizes": true`: tools.py simulates the entry's own program the way the action installs it (Debian's displaycal with its Recommends, and what it depends on, ArgyllCMS among it) and the card and the action say apt's sizes first.
`actions/entry status ID` answers for one entry without the cost of the whole page; the Info Centre's Stereo 3D and Deep Colour page asks it for DisplayCAL and runs `pkexec actions/entry displaycal install` from its button.
An install that fails says why in the person's language: apt busy (the lock is held), no network, a package the sources do not offer, or apt's exit status with its own lines above.

## The store-link kind (`kind: store`, 0.1.15, ORDER 10)

For a vendor who allows exactly a link: nothing of theirs is fetched, installed, mirrored or hosted, and the app center's Depends do not change.
A row carries `vendor`, `store` (the store's name), `domain` (the vendor's own domain), `url` (https, on that domain or a subdomain, no credentials, no port) and `note` (the key of one plain sentence on what the program is); storelink.py checks the address at the click and tests/store.py checks it in the data.
The card says, before the button and in the ten languages: what the program is, who makes it and that the names are theirs, that the button opens the store in the person's web browser, that the person registers there if it asks and downloads under the vendor's own licence agreement, that Stereo APTus installs and downloads nothing, and the address as text.
The button is `aptus://stereo_entry_ID_open` (a stereo section) or `aptus://storeopen_ID` (a main page's entry); the handler opens the address with `xdg-open`, as the person: run as administrator (the app center starts through pkexec), it drops to the user named by PKEXEC_UID with setpriv and never opens a browser as root. A failure, or a system without xdg-open, is said in a window with the address to open by hand.
The page makes no request of its own: the address is text, never a link.
To place the entry on another page, change the row's `section` (one of the five stereo sections); to put it on one of Paweł's pages, move the row to `main-entries.json` with `"section": "main"`, `page` and `key`, and add the link `aptus://KEY_ID` to his page in both trees, as PJeOffice Pro's.
The next vendor is one row and one sentence in the ten languages.

## Tests

`python3 tests/entries.py`, `tools.py`, `displaycal.py`, `zram.py`, `pjeoffice.py` and `store.py` run with no package manager and no network; run them where python3-apt is installed (a container).
What the package gets from elsewhere is found by `tests/layout.py`: the reader of the install-time download declaration (sparky-stereo-apt) from `SPARKY_INSTALL_DOWNLOADS_LIB`, the edition's build tree beside this folder, or the installed package, and Paweł's pages (`main/`), which it lays down from the tracked tree `9/` with `package_main.py` into a folder removed at exit.
When one of them is missing the test stops and names it.
The ten required languages hold every key of English; the eleven older page languages hold the sentences of the older versions and read the rest in English.

Phone as a camera is an entry of Graphics, Others since 0.1.16 (ORDER 25), beside Kamoso and Webcamoid (`kind: apt`, `section: main`, `sizes: true`).
It installs sparky-stereo-phone-camera, which brings DroidCam's client, scrcpy (its camera mode, the fully open way), adb and the virtual camera module (v4l2loopback-dkms) as its own Depends; the app center depends on none of them.
The card says in the ten languages what each program is and what the phone needs (the DroidCam app from the phone's own store, or USB debugging and Android 12 or newer for scrcpy), that scrcpy's package fetches its small phone-side server from the project's release page and checks its SHA-256, and that the phone appears as the camera "Phone camera".
The page is the row's `page` and `key` and Paweł's link in both trees: moving the entry to another page is those two fields and the two link lines.

OpenLogi is a signed vendor Debian package entry of Accessories, Devices (0.1.18, ORDER 27).
Its architecture-specific release, size, SHA-256 and public key source are in main-entries.json.
The shared tools machinery stages an absent minisign from authenticated apt archives before verification, so rejected signatures install no package.
Only after verification are the declared tool and the application installed through apt.
The shared install-downloads reader supplies size and metered notices.
Solaar stays available. OpenLogi’s Linux installation guide asks the person to quit Solaar before starting OpenLogi; the entry says so.
