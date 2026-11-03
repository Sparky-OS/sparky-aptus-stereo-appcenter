
The shared zram action activates dev-zram0.swap immediately after installation.
It stops the swap before its setup service and removes the package only after both stops succeed.
The complete operation runs under the shared problems engine so a failed start, stop or package change retains the same repair until it succeeds.
A restart is mentioned only when systemd is not running, with that reason.

Removal checks the setup service’s Result and the device’s disksize, because systemctl stop can succeed when ExecStop fails.
A failed reset leaves the package installed and a repair in the engine.
The explicit repair retries Debian’s device reset only after swap is inactive, then removes the package.
