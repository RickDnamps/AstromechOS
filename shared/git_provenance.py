"""shared/git_provenance.py — DNA-style paternity check for the AstromechOS
Git repository.

Before we let the operator (or the AstromechOS Imager) switch the `origin`
remote to an arbitrary URL, we verify TWO things:

  1. ``validate_remote_exists(url)``
        `git ls-remote <url>` succeeds — the URL resolves, is reachable,
        and is actually a Git repository (refs/heads listing non-empty).

  2. ``validate_paternity(repo_path, url, branch)``
        Fetches the candidate branch into FETCH_HEAD and asserts that the
        frozen initial commit of the official AstromechOS repo
        (OFFICIAL_INITIAL_COMMIT) is an ancestor of FETCH_HEAD via
        `git merge-base --is-ancestor`. This blocks anyone from pointing
        the robot at a totally unrelated repo (WordPress, malware, …)
        because such a repo will not share that lineage.

If EITHER check fails, the caller MUST abort the change and keep `origin`
pointed at the official URL. Never half-swap the remote.

The anchor SHA + the official URL are HARD-CODED constants of the code,
not cfg values — otherwise an attacker who can write the cfg could
substitute them and neutralise the paternity check.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

# ─────────────────────────────────────────────────────────────────
# Frozen lineage anchors — DO NOT make these cfg-configurable.
#
# OFFICIAL_INITIAL_COMMIT is the OLDEST commit reachable from the current
# `main` branch of the official RickDnamps/AstromechOS repo. It is NOT
# necessarily the chronological first-ever commit — the original commit
# `f01a9be5...` (2026-03-14) was orphaned by a history rewrite on
# 2026-05-22 and now only exists on archived `claude/*` work branches.
# The anchor below is the TRUE root of main's ancestry chain today, so
# every legitimate fork of the live repo has it.
#
# If `main` is ever rebased again, this constant MUST be updated to the
# new root — otherwise the validator will (correctly!) reject every
# fork including the operator's own. The bd memory
# `astromech-git-dna-paternity-check` carries the recovery procedure.
# ─────────────────────────────────────────────────────────────────
OFFICIAL_INITIAL_COMMIT = 'f7a2d1ef62714ded6ad4ba0600fc398ac7f2a6a0'
OFFICIAL_REPO_URL       = 'https://github.com/RickDnamps/AstromechOS.git'

# URL schemes the validator accepts. `file://` is included so local-loopback
# tests + dev workflows work; production use would normally be https/git@.
_SAFE_URL_PREFIXES = ('https://', 'http://', 'git@', 'ssh://', 'file://')

# Branch-name allowlist (mirrors the _SAFE_BRANCH_RE in deploy_controller.py
# + settings_bp.py — alnum, dot, slash, underscore, hyphen; no leading '-').
_SAFE_BRANCH_RE = re.compile(r'^[A-Za-z0-9._/\-]+$')


# ─────────────────────────────────────────────────────────────────
# Subprocess helper
# ─────────────────────────────────────────────────────────────────
def _git(repo_path: str | None, args: list[str], timeout: float = 30.0,
         env: dict | None = None) -> subprocess.CompletedProcess:
    """Invoke `git [-C <repo_path>] <args>` with captured output."""
    cmd = ['git']
    if repo_path:
        cmd += ['-C', str(repo_path)]
    cmd += args
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        env=env if env is not None else os.environ,
    )


def _no_prompt_env() -> dict:
    """`git` env with GIT_TERMINAL_PROMPT=0 — prevents the validator from
    blocking on a credentials prompt for a private repo."""
    env = dict(os.environ)
    env['GIT_TERMINAL_PROMPT'] = '0'
    return env


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────
def validate_remote_exists(url: str, timeout: float = 10.0) -> Tuple[bool, str]:
    """`git ls-remote --heads <url>` — the cheapest "is this a Git repo I
    can reach" check (no clone, no fetch, just refs/heads).

    Returns ``(ok, reason)``."""
    if not url or not isinstance(url, str):
        return False, 'empty URL'
    if not url.startswith(_SAFE_URL_PREFIXES):
        allowed = ', '.join(_SAFE_URL_PREFIXES)
        return False, f'unsupported URL scheme (allowed: {allowed})'
    if not shutil.which('git'):
        return False, 'git binary not found in PATH'
    try:
        r = subprocess.run(
            ['git', 'ls-remote', '--heads', url],
            capture_output=True, text=True, timeout=timeout, env=_no_prompt_env(),
        )
        if r.returncode != 0:
            err = (r.stderr or '').strip().splitlines()
            tail = err[-1] if err else 'git ls-remote failed (no stderr)'
            return False, f'git ls-remote failed: {tail}'
        if not r.stdout.strip():
            return False, 'remote has no branches (not a Git repository?)'
        return True, 'remote reachable'
    except subprocess.TimeoutExpired:
        return False, f'git ls-remote timed out (>{timeout:g}s)'
    except Exception as e:
        return False, f'git ls-remote error: {e}'


def _ensure_anchor_present_locally(repo_path: str, timeout: float = 30.0,
                                   env: dict | None = None) -> Tuple[bool, str]:
    """Make sure OFFICIAL_INITIAL_COMMIT is in the local repo's object store.

    Calls `git cat-file -e <ANCHOR>` first; if missing, tries to fetch it
    from the official remote (first by SHA, then by main branch). Returns
    ``(ok, reason)`` — ok=True means the anchor is now in the local objects."""
    env = env or _no_prompt_env()
    have = _git(repo_path, ['cat-file', '-e', OFFICIAL_INITIAL_COMMIT], timeout=5.0)
    if have.returncode == 0:
        return True, 'anchor present'
    # Try direct SHA fetch (modern git + GitHub allowReachableSHA1InWant).
    r2 = _git(repo_path,
              ['fetch', '--no-tags', '--depth=1',
               OFFICIAL_REPO_URL, OFFICIAL_INITIAL_COMMIT],
              timeout=timeout, env=env)
    if r2.returncode == 0:
        have2 = _git(repo_path, ['cat-file', '-e', OFFICIAL_INITIAL_COMMIT], timeout=5.0)
        if have2.returncode == 0:
            return True, 'anchor fetched by SHA'
    # Fallback: full fetch of main from the official remote. Same reason as
    # the candidate fetch above — `--depth` would graft history and the
    # anchor SHA wouldn't be reachable.
    r3 = _git(repo_path,
              ['fetch', '--no-tags',
               OFFICIAL_REPO_URL, 'main'],
              timeout=timeout, env=env)
    if r3.returncode != 0:
        tail = ((r3.stderr or '').strip().splitlines() or [''])[-1]
        return False, f'cannot fetch official remote: {tail}'
    have3 = _git(repo_path, ['cat-file', '-e', OFFICIAL_INITIAL_COMMIT], timeout=5.0)
    if have3.returncode == 0:
        return True, 'anchor reached via main fetch'
    return False, 'anchor not reachable even after fetching official main'


def validate_paternity(repo_path: str, url: str, branch: str = 'main',
                       timeout: float = 30.0) -> Tuple[bool, str]:
    """Verify the candidate ``<url>``'s ``<branch>`` descends from the
    official AstromechOS initial commit.

    Steps (all side-effect-free w.r.t. ``origin`` — only writes FETCH_HEAD):
      1. ``validate_remote_exists(url)``
      2. ``git fetch --no-tags --depth=200 <url> <branch>``
      3. Ensure OFFICIAL_INITIAL_COMMIT is in local objects (fetch from
         official URL if not).
      4. ``git merge-base --is-ancestor OFFICIAL_INITIAL_COMMIT FETCH_HEAD``

    Returns ``(ok, reason)``. Does NOT mutate ``origin``."""
    if not isinstance(repo_path, str) or not repo_path:
        return False, 'empty repo_path'
    repo = Path(repo_path)
    if not repo.is_dir():
        return False, f'repo_path is not a directory: {repo_path}'
    if not (repo / '.git').exists():
        return False, f'not a git repo: {repo_path}'
    if not branch or branch.startswith('-') or not _SAFE_BRANCH_RE.match(branch):
        return False, f'unsafe / invalid branch name: {branch!r}'

    ok, reason = validate_remote_exists(url, timeout=min(timeout, 10.0))
    if not ok:
        return False, reason

    env = _no_prompt_env()

    # 1. Fetch candidate branch into FETCH_HEAD — no merge, no tracking.
    # NOTE: no --depth here. A shallow fetch grafts history at the
    # boundary, so `merge-base --is-ancestor` can't see past it and the
    # anchor (commit #1 of ~1300+) becomes unreachable from FETCH_HEAD —
    # the validator would (incorrectly) reject every legitimate fork.
    # The full fetch is bounded by repo size; on the LAN/GitHub this is
    # a few seconds for an AstromechOS-sized project.
    r = _git(repo_path,
             ['fetch', '--no-tags', url, branch],
             timeout=timeout, env=env)
    if r.returncode != 0:
        tail = ((r.stderr or '').strip().splitlines() or [''])[-1]
        return False, f'git fetch <url> {branch} failed: {tail}'

    # 2. Ensure anchor is in local objects.
    ok, why = _ensure_anchor_present_locally(repo_path, timeout=timeout, env=env)
    if not ok:
        return False, f'cannot verify DNA: {why}'

    # 3. Ancestor test.
    is_anc = _git(repo_path,
                  ['merge-base', '--is-ancestor',
                   OFFICIAL_INITIAL_COMMIT, 'FETCH_HEAD'],
                  timeout=10.0)
    if is_anc.returncode == 0:
        return True, ('DNA OK: candidate descends from the official AstromechOS '
                      f'lineage (anchor {OFFICIAL_INITIAL_COMMIT[:12]}) at '
                      f'branch {branch!r}')
    if is_anc.returncode == 1:
        return False, ('DNA FAIL: the official AstromechOS initial commit '
                       f'({OFFICIAL_INITIAL_COMMIT[:12]}) is NOT in the candidate '
                       f'repo\'s history at branch {branch!r}. Looks like an '
                       'unrelated repository.')
    tail = ((is_anc.stderr or '').strip() or 'unknown error')
    return False, f'merge-base --is-ancestor errored: {tail}'


def validate_repo_url(repo_path: str, url: str, branch: str = 'main',
                      timeout: float = 30.0) -> Tuple[bool, str]:
    """High-level composite check — single call consumers should use.
    Currently identical to ``validate_paternity`` (which itself runs
    ``validate_remote_exists`` first). Kept as a stable public name in
    case more checks are added later (signature verification, mirror
    consistency, …)."""
    return validate_paternity(repo_path, url, branch, timeout=timeout)
