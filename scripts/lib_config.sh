#!/usr/bin/env bash
# scripts/lib_config.sh — shared identity / config helpers for AstromechOS
# install + deploy + update scripts.
#
# Source with:
#     . "$(dirname "$0")/lib_config.sh"
# or:
#     . "$REPO_PATH/scripts/lib_config.sh"
#
# Provides:
#   cfg_get <section> <key> <default>   read a value from /boot init,
#                                       local.cfg, main.cfg, default.
#   capture_user                        set TARGET_USER + TARGET_HOME from
#                                       $SUDO_USER / logname / prompt /
#                                       legacy 'astromech'.
#   slave_user                          SSH user on the Slave (cfg + waterfall).
#   slave_host                          Slave hostname/IP (cfg + waterfall).
#   slave_target                        composite user@host string.
#
# Resolution waterfall (matches shared/identity.py for the Python side):
#   1. /boot/astromech_init.cfg  (AstromechOS Imager bootstrap)
#   2. local.cfg  ([system]/[deploy]/[slave])
#   3. main.cfg   (in-repo defaults)
#   4. $SUDO_USER / $(logname) / $(whoami) auto-detection
#   5. Legacy 'astromech' / 'astromech-slave.local' (rétrocompat for the
#      original R2-D2 install — never reached on a fresh Imager install).

# Resolve REPO + cfg paths if the caller didn't set them.
: "${REPO:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${REPO_PATH:=$REPO}"
: "${LOCAL_CFG:=$REPO/master/config/local.cfg}"
: "${MAIN_CFG:=$REPO/master/config/main.cfg}"

# Find a working Python 3 interpreter. Raspbian / Pi OS ships `python3`
# only; Windows Git Bash (dev) ships `python` only. This helper hides
# the difference so write_local_cfg / dna_validate / future Python
# bridges work uniformly. Forwards all args + stdin to the interpreter.
_python() {
    if command -v python3 >/dev/null 2>&1; then
        python3 "$@"
    elif command -v python >/dev/null 2>&1; then
        python "$@"
    else
        echo "[ERR] no python interpreter found in PATH" >&2
        return 127
    fi
}

# Candidate paths for the Imager bootstrap (Bookworm moved /boot → /boot/firmware).
ASTRO_BOOT_INIT_CANDIDATES=(
    "/boot/astromech_init.cfg"
    "/boot/firmware/astromech_init.cfg"
)

# ──────────────────────────────────────────────────────────────────
# cfg_get <section> <key> <default>
# Read a key from /boot init → local.cfg → main.cfg → default.
# Prints the resolved value to stdout (or the default on miss).
# ──────────────────────────────────────────────────────────────────
cfg_get() {
    local section="$1" key="$2" default="$3"
    local f val
    # 1. Imager bootstrap (one-shot file, written by the Imager UI to /boot).
    for f in "${ASTRO_BOOT_INIT_CANDIDATES[@]}"; do
        [ -f "$f" ] || continue
        val=$(awk -F= -v s="[$section]" -v k="$key" '
            /^\[/{cur=$0}
            cur==s && $1 ~ "^[[:space:]]*"k"[[:space:]]*$" {
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
                print $2; exit
            }' "$f" 2>/dev/null)
        if [ -n "$val" ]; then echo "$val"; return 0; fi
    done
    # 2. local.cfg, then 3. main.cfg.
    for f in "$LOCAL_CFG" "$MAIN_CFG"; do
        [ -f "$f" ] || continue
        val=$(awk -F= -v s="[$section]" -v k="$key" '
            /^\[/{cur=$0}
            cur==s && $1 ~ "^[[:space:]]*"k"[[:space:]]*$" {
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
                print $2; exit
            }' "$f" 2>/dev/null)
        if [ -n "$val" ]; then echo "$val"; return 0; fi
    done
    # 4. Caller-supplied default.
    echo "$default"
}

# ──────────────────────────────────────────────────────────────────
# capture_user — set TARGET_USER + TARGET_HOME for the install.
# Exits non-zero if root or non-existent user (caller should `|| exit`).
# Waterfall: Imager bootstrap [system] user → $SUDO_USER → logname →
# whoami → interactive prompt (TTY) → legacy 'astromech'.
# ──────────────────────────────────────────────────────────────────
capture_user() {
    local u=""
    # 1. Imager bootstrap (future: /boot/astromech_init.cfg).
    u=$(cfg_get system user "")
    # 2. $SUDO_USER (set by sudo when invoked from a regular login).
    if [ -z "$u" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        u="$SUDO_USER"
    fi
    # 3. logname (the login-session user, even if running as root).
    if [ -z "$u" ] && command -v logname >/dev/null 2>&1; then
        u=$(logname 2>/dev/null || true)
    fi
    # 4. whoami (last-ditch).
    [ -z "$u" ] && u=$(whoami)
    # 5. Interactive prompt (only if we have a TTY and still don't have a user
    #    OR ended up with root — refuse to install as root).
    if { [ "$u" = "root" ] || [ -z "$u" ]; } && [ -t 0 ]; then
        echo "" >&2
        echo "[!] AstromechOS install: could not auto-detect the target Linux user." >&2
        echo "    (Tip: run via 'sudo bash $0' from a regular login, or pre-write" >&2
        echo "     [system] user = <name> in /boot/astromech_init.cfg via the Imager.)" >&2
        printf "    Linux user to install AstromechOS for: " >&2
        read -r u
    fi
    # 6. Hard fallback — keeps both the new convention AND the original
    # R2-D2 install path working. If we land here, neither astromech_init.cfg,
    # sudo, logname, whoami, nor an interactive prompt could give us a user.
    # Prefer the new generic 'astromech' (AstromechOS Imager default since
    # 2026-05-30); fall back to the legacy 'artoo' only on a pre-existing
    # account that was deployed before the migration.
    if [ -z "$u" ]; then
        if id "astromech" &>/dev/null; then
            echo "[WARN] capture_user: defaulting to 'astromech' — set [system] user in /boot/astromech_init.cfg or run via 'sudo bash $0' from a regular login for explicit selection." >&2
            u="astromech"
        elif id "artoo" &>/dev/null; then
            echo "[WARN] capture_user: falling back to legacy 'artoo' (no 'astromech' account on this box) — set [system] user in /boot/astromech_init.cfg to silence this warning." >&2
            u="artoo"
        else
            u="astromech"  # last-ditch default — validation below will fail and the caller reports it.
        fi
    fi
    # Validation.
    [ "$u" = "root" ] && { echo "[ERR] refusing to install as root — pick a regular user" >&2; return 1; }
    id "$u" &>/dev/null || { echo "[ERR] user '$u' does not exist on this system" >&2; return 1; }
    TARGET_USER="$u"
    TARGET_HOME=$(getent passwd "$u" | cut -d: -f6)
    [ -z "$TARGET_HOME" ] && TARGET_HOME="/home/$u"
    export TARGET_USER TARGET_HOME
}

# ──────────────────────────────────────────────────────────────────
# slave_user / slave_host / slave_target — SSH endpoint for Master→Slave.
# ──────────────────────────────────────────────────────────────────
slave_user() {
    # AstromechOS architecture rule (2026-05-28): the Master and the Slave
    # always run as the SAME Linux user. So the slave SSH user is just
    # whichever user is invoking us / was captured by capture_user — never
    # a separate cfg key. Matches shared/identity.py::slave_user.
    local u="${TARGET_USER:-}"
    [ -z "$u" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ] && u="$SUDO_USER"
    [ -z "$u" ] && u=$(logname 2>/dev/null || true)
    [ -z "$u" ] && u=$(whoami 2>/dev/null || true)
    if [ -z "$u" ]; then
        if id "astromech" &>/dev/null; then
            echo "[WARN] slave_user: defaulting to 'astromech' — capture_user was not called and no SUDO_USER/logname/whoami succeeded." >&2
            u="astromech"
        elif id "artoo" &>/dev/null; then
            echo "[WARN] slave_user: falling back to legacy 'artoo' (no 'astromech' account on this box)." >&2
            u="artoo"
        else
            u="astromech"  # last-ditch default; caller should detect via id check.
        fi
    fi
    echo "$u"
}

slave_host() {
    local h
    h=$(cfg_get slave host "")
    [ -z "$h" ] && h=$(cfg_get deploy slave_host "")
    [ -z "$h" ] && h="astromech-slave.local"
    echo "$h"
}

slave_target() {
    echo "$(slave_user)@$(slave_host)"
}

# ──────────────────────────────────────────────────────────────────
# install_service_template <src.template> <dest_name>
# Substitutes __USER__/__HOME__/__UID__/__REPO_PATH__ from the LOCAL
# capture_user state (or the current process owner if capture_user
# wasn't called) and installs to /etc/systemd/system/<dest_name> via
# 'sudo tee'. Used by setup_master.sh / update.sh for MASTER services.
# ──────────────────────────────────────────────────────────────────
install_service_template() {
    local src="$1" dest_name="$2"
    [ -f "$src" ] || { echo "[ERR] service template not found: $src" >&2; return 1; }
    local U H UD R
    U="${TARGET_USER:-$(whoami)}"
    H="${TARGET_HOME:-$(getent passwd "$U" 2>/dev/null | cut -d: -f6)}"
    [ -z "$H" ] && H="/home/$U"
    UD=$(id -u "$U" 2>/dev/null) || UD=1000
    R="${REPO_PATH:-$H/astromechos}"
    sed -e "s|__USER__|$U|g" \
        -e "s|__HOME__|$H|g" \
        -e "s|__UID__|$UD|g" \
        -e "s|__REPO_PATH__|$R|g" \
        "$src" | sudo tee "/etc/systemd/system/$dest_name" > /dev/null
}

# ──────────────────────────────────────────────────────────────────
# install_service_template_remote <relpath> <dest_name> <ssh_target>
# Same as above but executes the substitution on the REMOTE side, so
# __USER__/__HOME__/__UID__/__REPO_PATH__ resolve to the SLAVE's local
# values (which, per the Master-==-Slave-user rule, match the Master's
# but the home directory could still differ on edge-case installs).
# <relpath> is relative to the slave's REPO root (e.g.
# slave/services/astromech-slave.service.template). The template must
# already have been rsynced to the slave before this is called.
# ──────────────────────────────────────────────────────────────────
install_service_template_remote() {
    local relpath="$1" dest_name="$2" target="$3"
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$target" \
        bash -s -- "$relpath" "$dest_name" << 'REMOTE'
        REL="$1"; DEST="$2"
        U=$(whoami); H="$HOME"; UD=$(id -u); R="$H/astromechos"
        SRC="$R/$REL"
        [ -f "$SRC" ] || { echo "[ERR] template not found on slave: $SRC" >&2; exit 1; }
        sed -e "s|__USER__|$U|g" \
            -e "s|__HOME__|$H|g" \
            -e "s|__UID__|$UD|g" \
            -e "s|__REPO_PATH__|$R|g" \
            "$SRC" | sudo tee "/etc/systemd/system/$DEST" > /dev/null
        sudo systemctl daemon-reload
REMOTE
}

# ──────────────────────────────────────────────────────────────────
# reinstall_changed_service_templates
# Walk master/services/*.service.template (and *.path.template), render
# each via the SAME substitution rules as install_service_template, and
# diff the result against the installed unit in /etc/systemd/system/.
# Any template that DIFFERS (or has no installed counterpart yet) gets
# re-installed; a single `systemctl daemon-reload` is fired at the end
# if anything changed.
#
# Motivation (bug verified live 2026-06-06):
#   Master legacy auto-pulls the latest code at boot via main.py::try_git_pull.
#   The repo's *.service.template files updated (e.g. commit 3065d6c added
#   After=cloud-final.service), but install_service_template was NEVER
#   re-run, so /etc/systemd/system/<unit>.service stayed STALE. DD'ing
#   that legacy as a Golden Image then propagated the stale unit to every
#   freshly flashed Pi — race condition + wipe loop. The auto-reinstall
#   below closes that gap on every pull.
#
# Idempotent: cmp -s skips reinstall when bytes already match → no
# systemctl churn on a clean pull.
#
# Failure tolerant: each step is wrapped so a single bad template never
# aborts the whole pass (try_git_pull must keep going on error).
# ──────────────────────────────────────────────────────────────────
reinstall_changed_service_templates() {
    local REPO_DIR="${REPO_PATH:-${REPO:-}}"
    if [ -z "$REPO_DIR" ] || [ ! -d "$REPO_DIR/master/services" ]; then
        return 0
    fi
    # Mirror install_service_template's substitution variables exactly.
    local U H UD R
    U="${TARGET_USER:-$(whoami)}"
    H="${TARGET_HOME:-$(getent passwd "$U" 2>/dev/null | cut -d: -f6)}"
    [ -z "$H" ] && H="/home/$U"
    UD=$(id -u "$U" 2>/dev/null) || UD=1000
    R="${REPO_PATH:-$H/astromechos}"

    local changed=0 tpl basename installed rendered
    shopt -s nullglob
    for tpl in "$REPO_DIR/master/services"/*.service.template \
               "$REPO_DIR/master/services"/*.path.template; do
        [ -e "$tpl" ] || continue
        basename="$(basename "$tpl" .template)"
        installed="/etc/systemd/system/$basename"
        rendered="$(mktemp 2>/dev/null)" || continue
        # Render with the SAME sed expressions install_service_template uses.
        if ! sed -e "s|__USER__|$U|g" \
                 -e "s|__HOME__|$H|g" \
                 -e "s|__UID__|$UD|g" \
                 -e "s|__REPO_PATH__|$R|g" \
                 "$tpl" > "$rendered" 2>/dev/null; then
            rm -f "$rendered"
            continue
        fi
        if [ ! -f "$installed" ] || ! cmp -s "$rendered" "$installed"; then
            if install_service_template "$tpl" "$basename" 2>/dev/null; then
                changed=$((changed + 1))
                echo "[OK] re-installed systemd unit: $basename (template drift detected)"
            else
                echo "[WARN] failed to re-install $basename — leaving stale unit in place" >&2
            fi
        fi
        rm -f "$rendered"
    done
    shopt -u nullglob
    if [ "$changed" -gt 0 ]; then
        sudo systemctl daemon-reload 2>/dev/null || true
        echo "[OK] re-installed $changed systemd unit template(s) and ran daemon-reload"
    fi
    return 0
}

# ──────────────────────────────────────────────────────────────────
# write_local_cfg <section> <key> <value>
# Atomically write a key/value into local.cfg via configparser, so
# sections are created/preserved correctly and concurrent writes can't
# corrupt the file (uses tmp + os.replace under the hood).
# Used by firstboot_setup.sh to persist the values the AstromechOS
# Imager wrote into /boot/astromech_init.cfg.
# ──────────────────────────────────────────────────────────────────
write_local_cfg() {
    local section="$1" key="$2" value="$3"
    local cfg="${LOCAL_CFG:-}"
    if [ -z "$cfg" ]; then
        echo "[ERR] write_local_cfg: LOCAL_CFG env var not set" >&2
        return 1
    fi
    [ -f "$cfg" ] || { mkdir -p "$(dirname "$cfg")"; : > "$cfg"; }
    _python - "$cfg" "$section" "$key" "$value" << 'PYEOF'
import configparser, os, sys, tempfile
cfg_path, section, key, value = sys.argv[1:5]
c = configparser.ConfigParser()
try:
    c.read(cfg_path, encoding='utf-8')
except Exception:
    c = configparser.ConfigParser()
if not c.has_section(section):
    c.add_section(section)
c.set(section, key, value)
# Atomic write: tmp file in the same directory + os.replace
d = os.path.dirname(os.path.abspath(cfg_path)) or '.'
fd, tmp = tempfile.mkstemp(dir=d, prefix='.cfgtmp.')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        c.write(f)
    os.replace(tmp, cfg_path)
    # Mirror the chmod 0o600 pattern the project uses for cfg writes
    try: os.chmod(cfg_path, 0o600)
    except Exception: pass
    # Ownership fix (bug 2026-06-04): when firstboot_setup.sh runs us as
    # ROOT, os.replace leaves cfg_path owned root:root mode 0600, which
    # the astromech-uid systemd service cannot read. configparser.read
    # silently swallows EACCES -> cfg.get('master','repo_path') raises
    # NoOptionError -> master service crash-loops. Mirror the
    # _chown_to_parent_owner pattern from master/config/config_loader.py
    # (this is a copy of that fix because lib_config.sh ships its own
    # inline write_local_cfg rather than importing the Python one).
    # Read parent dir owner to stay username-agnostic per CLAUDE.md HARD
    # RULE (the C# Imager renames UID-1000 per device).
    try:
        ps = os.stat(d)
        os.chown(cfg_path, ps.st_uid, ps.st_gid)
    except (OSError, AttributeError):
        pass
except Exception:
    try: os.unlink(tmp)
    except Exception: pass
    raise
PYEOF
}

# ──────────────────────────────────────────────────────────────────
# dna_validate <url> [branch]
# Bash wrapper for shared/git_provenance.validate_paternity. Returns
# 0 if the URL is a legitimate fork of AstromechOS (its main branch
# descends from the official initial commit), non-zero otherwise.
# Prints the validator's reason to stderr in either case.
# Used by firstboot_setup.sh BEFORE switching origin to a candidate URL.
# ──────────────────────────────────────────────────────────────────
dna_validate() {
    local url="$1" branch="${2:-main}"
    if [ -z "$url" ]; then
        echo "[ERR] dna_validate: empty URL" >&2
        return 1
    fi
    : "${REPO:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
    _python - "$url" "$branch" "$REPO" << 'PYEOF'
import sys
url, branch, repo = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, repo)
try:
    from shared.git_provenance import validate_paternity
except Exception as e:
    print(f'[ERR] cannot import shared.git_provenance: {e}', file=sys.stderr)
    sys.exit(2)
ok, msg = validate_paternity(repo, url, branch)
print(msg, file=sys.stderr)
sys.exit(0 if ok else 1)
PYEOF
}
