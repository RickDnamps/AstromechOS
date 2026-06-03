"""Regression tests for write_cfg_atomic / rotate_backup ownership preservation.

Bug fixed 2026-06-03: firstboot_setup.sh runs as ROOT, calls write_cfg_atomic()
which left local.cfg owned root:root mode 0600 — unreadable by the
astromech-uid systemd service. configparser.read silently swallowed EACCES,
then cfg.get('master','repo_path') raised NoOptionError and the master
service crash-looped (observed 325 restarts on a test Pi).

Fix is in master/config/config_loader.py::_chown_to_parent_owner which is
invoked at the end of write_cfg_atomic() and after each backup file produced
by rotate_backup(). Username-agnostic (reads parent dir owner instead of
hardcoding 'astromech') per the CLAUDE.md HARD RULE.
"""
import configparser
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from master.config.config_loader import (  # noqa: E402
    write_cfg_atomic,
    rotate_backup,
    _chown_to_parent_owner,
)


posix_only = pytest.mark.skipif(
    os.name == 'nt', reason='POSIX ownership semantics only'
)


@posix_only
def test_write_cfg_atomic_preserves_parent_dir_owner(tmp_path):
    """The written file must inherit its parent directory's uid/gid.

    Without this, a root-run firstboot leaves local.cfg owned root:root and
    the astromech-uid service can't read it.
    """
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    parent_uid = cfg_dir.stat().st_uid
    parent_gid = cfg_dir.stat().st_gid

    cfg = configparser.ConfigParser()
    cfg['section'] = {'key': 'value'}
    out = cfg_dir / "local.cfg"
    write_cfg_atomic(cfg, str(out))

    assert out.exists()
    assert out.stat().st_uid == parent_uid, (
        f"file uid={out.stat().st_uid}, expected parent uid={parent_uid} - "
        "regression: file ownership not preserved → service user can't read"
    )
    assert out.stat().st_gid == parent_gid
    # 0600 mode preserved (security invariant — passwords live in this file).
    assert (out.stat().st_mode & 0o777) == 0o600


@posix_only
def test_write_cfg_atomic_idempotent_no_chown_when_self_owner(tmp_path):
    """Repeated writes by the eventual owner must not raise.

    Normal post-boot mutation path: the service runs as the same user that
    owns the parent dir, so chown(self → self) is a harmless no-op.
    """
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    cfg = configparser.ConfigParser()
    cfg['x'] = {'y': 'z'}
    out = cfg_dir / "local.cfg"
    # Write twice — second call must not raise.
    write_cfg_atomic(cfg, str(out))
    write_cfg_atomic(cfg, str(out))
    assert out.exists()
    # Backup of the first write should also have parent dir ownership.
    bak1 = cfg_dir / "local.cfg.bak1"
    assert bak1.exists()
    assert bak1.stat().st_uid == cfg_dir.stat().st_uid
    assert bak1.stat().st_gid == cfg_dir.stat().st_gid


@posix_only
def test_rotate_backup_preserves_parent_dir_owner(tmp_path):
    """Each .bak* file created by rotate_backup must inherit parent ownership.

    shutil.copy2 creates the destination with the CURRENT process's ownership
    — a root-run firstboot would otherwise leave .bak1 root:root and a later
    operator restore from .bak1 would surface the same unreadable file.
    """
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    parent_uid = cfg_dir.stat().st_uid
    parent_gid = cfg_dir.stat().st_gid

    # Seed an existing file so rotate_backup actually does work.
    target = cfg_dir / "local.cfg"
    target.write_text("[seed]\nk = v\n", encoding='utf-8')
    os.chmod(str(target), 0o600)

    rotate_backup(str(target))

    bak1 = cfg_dir / "local.cfg.bak1"
    assert bak1.exists()
    assert bak1.stat().st_uid == parent_uid
    assert bak1.stat().st_gid == parent_gid
    assert (bak1.stat().st_mode & 0o777) == 0o600


@posix_only
def test_rotate_backup_chowns_rotated_generations(tmp_path):
    """When .bak1 → .bak2 rotation happens, the rotated file is re-chowned.

    Defense-in-depth: if an earlier rotation under root left an old
    generation stuck owned root:root, the next rotation cycle should heal it.
    """
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    target = cfg_dir / "local.cfg"
    target.write_text("[seed]\nk = 1\n", encoding='utf-8')
    # First rotation: creates .bak1.
    rotate_backup(str(target))
    # Mutate + second rotation: shifts .bak1 → .bak2, creates new .bak1.
    target.write_text("[seed]\nk = 2\n", encoding='utf-8')
    rotate_backup(str(target))

    bak1 = cfg_dir / "local.cfg.bak1"
    bak2 = cfg_dir / "local.cfg.bak2"
    assert bak1.exists() and bak2.exists()
    parent_uid = cfg_dir.stat().st_uid
    parent_gid = cfg_dir.stat().st_gid
    for bak in (bak1, bak2):
        assert bak.stat().st_uid == parent_uid, f"{bak.name} uid leaked"
        assert bak.stat().st_gid == parent_gid, f"{bak.name} gid leaked"


def test_chown_to_parent_owner_swallows_errors_on_missing_path(tmp_path):
    """Helper must never raise — it's best-effort by contract.

    Cross-platform test: even on Windows (where os.chown is absent), the
    helper must return cleanly. Pointed at a non-existent file path it
    should still not surface the OSError.
    """
    ghost = tmp_path / "does_not_exist.cfg"
    # Must not raise.
    _chown_to_parent_owner(str(ghost))


def test_write_cfg_atomic_writes_content_correctly(tmp_path):
    """Sanity check: the chown addition must not break the actual write.

    Cross-platform — verifies content round-trips regardless of ownership
    semantics (so we catch any future regression to the write path itself).
    """
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    cfg = configparser.ConfigParser()
    cfg['master'] = {'repo_path': '/home/x/astromechos'}
    cfg['github'] = {'repo_url': 'https://example.invalid/r.git'}
    out = cfg_dir / "local.cfg"
    write_cfg_atomic(cfg, str(out))

    reread = configparser.ConfigParser()
    reread.read(str(out), encoding='utf-8')
    assert reread.get('master', 'repo_path') == '/home/x/astromechos'
    assert reread.get('github', 'repo_url') == 'https://example.invalid/r.git'
