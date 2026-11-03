
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
