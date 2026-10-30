---
name: server-disk-cleanup
description: Use when freeing disk space on a self-hosted server.
version: 1.1.0
author: Hermes Agent
license: MIT
---

# Server Disk Cleanup

## When to Use
- The user asks what's taking up disk space, or to free/clear space, on a self-hosted Linux server (the host this agent runs on, or a remote server reachable over SSH).
- `df` shows the root filesystem filling up.

Analyze top-down before deleting anything; report the breakdown and the safe wins, then get a go/no-go on how aggressive to be before touching Docker.

## Analyze first (top-down)
Map the disk before acting. Big consumers on a typical self-hosted box are Docker/containerd, /var/log, /root and /var/lib.

    df -h /
    du -xh --max-depth=1 / | sort -rh | head -30
    du -xh --max-depth=1 /var | sort -rh | head -15
    du -xh --max-depth=2 /var/lib/containerd | sort -rh | head -12

Prefer `du -xh` (no cross-filesystem, human units) over `du -sh *`; drill two or three levels deep rather than stopping at the first summary.

## Docker cleanup (usually the biggest win)
Show real usage and container-to-image references, not the estimate:

    docker system df
    docker images
    docker ps -a                    # which images each container (running OR stopped) needs
    docker ps --format '{{.Names}}\t{{.Image}}'

Order matters — image prune FIRST, then build cache:

    docker image prune -a -f        # removes images with ZERO container references
    docker builder prune -f         # frees far more AFTER the images are gone

Pitfalls:
- `docker system df` "reclaimable" overstates real freeable space because images share layers; actual reclaimed is often 3-4x lower. Re-measure with `df` after pruning.
- `docker image prune -a` removes ONLY images referenced by no container at all — running AND stopped/created containers' images survive. This is the safe aggressive option: it cannot delete data held by a container.
- Watch for `<none>` (untagged) images that are actually in use: a container may be pinned to an image ID whose tag was removed (e.g. after an upgrade), so that `<none>` image is NOT garbage. Confirm with `docker ps -a` before assuming untagged images are free to delete.
- Build cache shows ~0 reclaimable until image prune removes the images pinning those layers, then it jumps to GBs. Always image-prune first.
- NEVER run `docker system prune -a` blind: it deletes stopped containers, losing their data when it is not in a named volume. Prune images and build cache, not containers.

## Caches (safe, re-downloadable)
    npm cache clean --force
    rm -rf /root/.cache/uv /root/.cache/pip /root/.cache/electron \
           /root/.cache/node-gyp /root/.cache/typescript \
           /root/.cache/puppeteer /root/.cache/google-chrome-for-testing-headless

KEEP `/root/.cache/ms-playwright` — HyperFrames' active browser (re-download is expensive and it is in live use). Same rule for any cache the running stack actively loads from.

## Logs
    journalctl --vacuum-size=100M   # systemd journals, often 1-3GB+ reclaimable

## Remote machine (a second server over SSH)
The same cleanup applies to a remote host. Reuse the existing SSH key rather than asking for credentials:

- Find connection details from env (e.g. `<name>_machine_IP`, `<name>_SSH_user`, `<name>_SSH_key_private`).
- PuTTY-format keys (`PuTTY-User-Key-File-3`) must be converted to OpenSSH before `ssh` can use them:
      puttygen key.ppk -O private-openssh -o ~/.ssh/name_id_rsa && chmod 600 ~/.ssh/name_id_rsa
  (`puttygen` ships with the putty-tools package; the `cryptography` / `paramiko` libs are alternatives if it is absent.)
- Run the same top-down analysis remotely:
      ssh -i ~/.ssh/name_id_rsa user@host 'du -xh --max-depth=1 / | sort -rh | head; sudo docker system df'
  Note: `sudo` on the remote box may need to be passwordless — use `sudo docker` (not bare `docker`) where the SSH user is not root, and confirm it resolves before scripting it.

## Recurring cleanup
Prevent docker bloat re-accumulating. Pick whichever fits:

1. Hermes cron (no_agent script, deliver=local):
      script: docker image prune -a -f && docker builder prune -f
      schedule: 0 3 */2 * *   (every 2 days at 03:00 UTC)
2. System cron directly on a remote box — self-contained, keeps working even if the Hermes host is down:
      echo "0 3 */2 * * root docker image prune -a -f && docker builder prune -f" \
        | sudo tee /etc/cron.d/docker-prune

`no_agent=true` runs the script with no LLM; `deliver=local` stays quiet. For the system-cron variant, verify `docker` resolves in cron's default PATH (`command -v docker` — usually /usr/bin/docker).