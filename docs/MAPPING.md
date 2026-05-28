# AstromechOS — HAT Mapping & Calibration Architecture

> Canonical reference for the **HAT identity layer**, **config_mapping.json**,
> the **nested calibration storage**, the **Settings UI Re-Mapping** workflow,
> and the **anti-collision blindage**. Read this before touching any of
> `shared/hw_mapping.py`, the driver `_get_angle` chain, the calibration
> JSON files, or the Settings → HATs UI. Chantier G (G1→G6 + blindage,
> 2026-05-28), 9 commits `01218c4 → b2a6048`, 111 unit tests passing.

---

## The problem

Before this chantier, servo labels and per-channel calibration data
(`open`, `close`, `speed`) were stored **keyed by a flat name like
`Servo_S0`**:

```json
{ "Servo_S0": {"label": "Body_Panel_1", "open": 110, "close": 20, "speed": 10},
  "Servo_S1": {"label": "Body_Panel_2", ...} }
```

The flat index was derived at boot from the `[i2c_servo_hats]` cfg
order: HAT at the first cfg position got channels 0–15 = Servo_S0–S15;
HAT at the second cfg position got 16–31. **This made the mapping
brittle**: re-jumpering a HAT from `0x41` to `0x42` (or adding a new
HAT before the existing one) shifted every calibration to the wrong
physical servo. The operator's careful tuning could be wiped out by
a five-minute hardware change.

---

## The fix — HAT identity as the anchor

Calibration is now anchored to a **stable HAT identity** like
`Body_HAT_A`, `Dome_HAT_A`, or `Motor_HAT_A`. The identity carries
the calibration; the identity's `address` field can change freely
without disturbing the data.

```
config_mapping.json:
  Body_HAT_A  ↔ 0x41   ← operator can change this address at any time
                          via Settings → HATs, no other file moves.

servo_angles.json (nested by identity):
  Body_HAT_A:
    "0": {label, open, close, speed}   ← calibration anchored here
    "1": {...}
    ...
```

Even better, the EXTERNAL flat names (`Servo_S0..S15`, `Servo_M0..M15`)
referenced by `.chor` files, shortcuts, arms cfg, and every API
endpoint **stay flat and unchanged** — `shared/hw_mapping.py` provides
the bidirectional translation `flat_name <-> (identity, channel)`.
Zero breaking change to user data; the entire migration is invisible
to choreographies + shortcuts.

---

## 1. The `config_mapping.json` schema

`master/config/config_mapping.json` (gitignored, atomic write, chmod
0644). Same shape on the slave (`slave/config/config_mapping.json`).

```json
{
  "schema_version": 1,
  "host": "master",
  "updated_at": "2026-05-28T17:39:28Z",
  "synthesised": false,
  "hats": [
    {
      "id":           "Dome_HAT_A",
      "role":         "servo_dome",
      "address":      "0x40",
      "channels":     16,
      "alias_prefix": "Servo_M",
      "alias_base":   0
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `id` | Stable identity. Pattern `^[A-Z][A-Za-z0-9]+_HAT_[A-Z]$` — `Dome_HAT_A`, `Body_HAT_B`, `Motor_HAT_A`. **Never changes.** |
| `role` | `servo_dome` / `servo_body` / `motor_drive`. Used by the driver to pick the right channel namespace. |
| `address` | Current I2C address `0x40..0x77`. **This is the only field the operator changes when re-jumpering.** |
| `channels` | Always 16 for PCA9685. Reserved for future ICs. |
| `alias_prefix` | `Servo_M` / `Servo_S` / `null` (motor HAT has no servo aliases). |
| `alias_base` | First flat-name index this HAT covers — `Dome_HAT_B.alias_base = 16` so it exposes `Servo_M16..M31`. Preserves the existing flat namespace when a second HAT is added. |
| `synthesised` | `true` when the file was auto-built by `detect_hats.py`; `false` after the operator confirms via Settings UI. |

---

## 2. Module API — `shared/hw_mapping.py`

The single source of truth. Every consumer (drivers, servo_bp,
hats_bp, /status) calls these helpers — never re-implements the
priority logic, never re-builds the flat-name table.

```python
load_for(role)                           → Optional[dict]
synthesize_from_layout(role, cfg_paths)  → dict   (fallback when no file yet)
all_hats(mapping)                        → list[dict]  (sorted by alias_base)
hat_by_id(mapping, "Body_HAT_A")         → Optional[dict]
hat_by_address(mapping, "0x41")          → Optional[dict]
channels_for(mapping, "Body_HAT_A")      → int
flat_name(mapping, "Body_HAT_A", 3)      → "Servo_S3"   (external name)
identity_for(mapping, "Servo_S3")        → ("Body_HAT_A", 3)   (reverse)

# Calibration format helpers (Phase G3):
is_nested_format(d)                      → bool
flat_calibration_to_nested(flat, mapping)→ dict   (migration on read)
nested_calibration_to_flat(nested, map)  → dict   (back-compat for GET API)
normalise_calibration(raw, mapping)      → dict   (accepts either, returns nested)
```

Validation is strict: `_normalise_addr` rejects anything outside
`0x40..0x77`; `_valid_hat` enforces the id regex, role taxonomy,
and channel count; malformed entries in a mapping are silently
dropped (logged at debug level) so a corrupt file never panics
the driver.

---

## 3. The 6 phases — what each commit landed

| # | Commit | Phase | Delivered |
|---|---|---|---|
| G1 | `01218c4` | Foundation | `shared/hw_mapping.py` + 22 tests. Schema validators + lookup helpers. No consumers yet, pure additive. |
| G2 | `42b994a` | Auto-synthesis | `detect_hats.py --write-mapping`: when `config_mapping.json` is absent, it's synthesised from the legacy `[i2c_servo_hats]` cfg, written atomically (tmp + os.replace + chmod 0o644). Never overwrites an operator-edited file. |
| G3 | `42b994a` | Driver refactor | `_load_dome_angles` + `_load_servo_angles` normalise legacy FLAT JSON to NESTED-by-identity in memory via `normalise_calibration`. `_get_angle('Servo_M3', ...)` resolves via `identity_for` → `angles[identity][str(ch)][key]`. `servo_bp._update_angles_file` reads either format, writes nested. Backwards compat: `.chor`/`shortcuts`/`arms` unchanged. |
| G4 | `8dbf2c7` | Backup integration | `master/config/config_mapping.json` + slave equivalent added to `BACKUP_FILESET`. New `validate_mapping_against_layout(mapping_path, layout_path)` compares restored mapping vs live `hw_layout.json` and emits warnings per address mismatch. Attached to restore job via `job.update(mapping_warnings=[...])`. Latent bug fix: `backup_core.py` was missing `import json` — caught by `sys.settrace` exception event. |
| G5 | `32ffcda` + fix `e297da3` | Calibration UI fail-safe | `/servo/settings` enriched with per-HAT `identity` + `available`. Calibration cards greyed-out + `HARDWARE NOT FOUND` banner when the HAT isn't on the live scan. Backend `_update_angles_file` builds offline-identity set + raises `HardwareOfflineError` (HTTP 503) so a stale UI / forged POST can't silently corrupt offline HATs. Critical type-mismatch fix: `detected_addresses` returns `set[int]`, compare as int (not as `f'0x{n:02x}'` string). |
| G6 | `5def329` + blindage `b2a6048` | Re-Mapping endpoint + UI | `POST /hats/remap` (@require_admin): atomic-write of `config_mapping.json` with full server-side validation (host enum, identity exists, address `0x40..0x77`, address-uniqueness within side). In-process driver `_mapping` reload + `.reload()`. UI re-map editor under Settings → HATs with dropdowns sourced from live `/hats/layout` detected addresses (no fictional 0x40..0x77 list). Inline collision detection with red highlight + pulsing red banner `Collision d'adresse détectée` + disabled SAVE button. |

Total chantier: 111 unit tests across 5 suites, 0 regression.

---

## 4. The operator workflow — re-jumpering a HAT

**Goal**: move `Body_HAT_A` from I2C `0x41` to I2C `0x42` (perhaps to
make room for a second body HAT). **Outcome**: every label, every
open/close angle, every speed setting on Body_HAT_A's 16 channels
stays exactly where it was. No `.chor` rewrite. No re-tuning.

```
┌────────────────────────────────────────────────────────────────┐
│  Power OFF the robot                                           │
│  Solder the A1 jumper on the body PCA9685 board (0x41 → 0x42)  │
│  Power back ON                                                 │
└────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────┐
│  Settings → HATs → 🔄 RESCAN HARDWARE                          │
│    → detect_hats.py rewrites slave/config/hw_layout.json       │
│    → Detected addresses now include 0x42 (no longer 0x41)      │
└────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────┐
│  Settings → HATs → RE-MAP HAT IDENTITIES (slave)               │
│    → Dropdown for Body_HAT_A now lists only 0x40 + 0x42        │
│      (filtered to LIVE detected addresses).                    │
│    → Pick 0x42 from the dropdown.                              │
│    → 💾 SAVE MAPPING (SLAVE)                                   │
└────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────┐
│  POST /hats/remap → atomic write + driver hot-reload.          │
│  servo_angles.json never touched. Every label preserved.       │
│  Body_HAT_A still rendered in the Calibration panel; the rows  │
│  now drive PWM at the new I2C address.                         │
└────────────────────────────────────────────────────────────────┘
```

**Anti-collision blindage**: if the operator accidentally picks an
address that's already assigned to another identity on the same side
(e.g. `0x40` for both Motor_HAT_A and Body_HAT_A), both rows turn red
and the SAVE button greys out. A red pulsing banner appears at the
top of the section:

> ⚠ Collision d'adresse détectée — two identities cannot bind to the
> same physical address.

The check fires on every dropdown change AND at panel-open so the
operator immediately sees the state of their existing saved mapping.

---

## 5. Backup / Restore semantics

`config_mapping.json` is included in the `.bck` archive
(`backup_core.BACKUP_FILESET`). On restore, `_run_restore` calls
`validate_mapping_against_layout` against both sides BEFORE files
move, attaching the warning list to the restore job. The operator
sees a clear message per HAT whose mapped address doesn't match the
live scan:

```
HAT identity Body_HAT_A (servo_body) expected at 0x41 per restored
config_mapping.json, but the live I2C scan detected ['0x40','0x42'].
The driver will boot DEGRADED for this HAT. Use Settings → HATs to
re-assign the address without losing calibration.
```

The restore still succeeds — calibration data is preserved by HAT
identity, not address — so the operator just clicks RESCAN HARDWARE
then re-maps via the UI workflow above.

---

## 6. The defense-in-depth chain

Three independent layers guarantee mapping integrity:

| Layer | Role | Failure mode |
|---|---|---|
| **UI dropdown filtering** | Dropdown choices come from live `/hats/layout`. Operator literally cannot select an address that isn't on the bus. | Stale UI → falls through to layer 2. |
| **UI collision check** | `_checkRemapCollisions` runs on every dropdown change; duplicates highlight red + disable SAVE button. | Malicious client bypasses the disabled button → falls through to layer 3. |
| **Backend `/hats/remap` validation** | Server-side `seen_addrs` check refuses any submission where two identities point at the same address. Returns HTTP 400 with `"address 0xNN assigned to more than one HAT; each physical address must be unique"`. | No bypass — atomic write only happens after every rule passes. |

Address range, identity existence, and host enum checks share the
same atomic refusal: **either every check passes and the file is
written, or no write happens at all.**

---

## 7. Files touched by the G chantier

```
shared/hw_mapping.py                                  ← NEW (244 LOC)
master/config/config_mapping.json.example             ← NEW (schema doc)
slave/config/config_mapping.json.example              ← NEW
scripts/detect_hats.py                                ← + _maybe_write_mapping
scripts/test_hw_mapping.py                            ← NEW (32 tests)
scripts/test_backup_mapping_validation.py             ← NEW (11 tests)
scripts/test_hats_remap.py                            ← NEW (12 tests)
master/drivers/dome_servo_driver.py                   ← _load_dome_angles +
                                                        _get_angle identity-aware
slave/drivers/body_servo_driver.py                    ← mirror
master/api/servo_bp.py                                ← /servo/settings enriched,
                                                        _update_angles_file
                                                        nested-keyed,
                                                        HardwareOfflineError
master/api/hats_bp.py                                 ← POST /hats/remap
master/api/backup_core.py                             ← + import json,
                                                        + validate_mapping_against_layout,
                                                        + config_mapping in
                                                          BACKUP_FILESET
master/api/backup_bp.py                               ← restore validation hook
master/templates/index.html                           ← hats-remap-wrapper div
android/app/src/main/assets/index.html                ← mirror
master/static/js/app.js                               ← renderRemapEditor +
                                                        _checkRemapCollisions
                                                        + saveRemap
master/static/css/style.css                           ← .hat-block-offline,
                                                        .hat-remap-*
```

---

## 8. Related references

- `shared/hw_mapping.py` — module docstring is the authoritative spec.
- `scripts/test_hw_mapping.py`, `test_hats_remap.py`,
  `test_backup_mapping_validation.py` — runnable specifications.
- `bd memories astromech-chantier-g-industrialisation-mapping-2026-05-28`
- The previous deploy/security work (DNA paternity + Imager) is the
  foundation this builds on — see
  **[DEPLOY_SECURITY.md](DEPLOY_SECURITY.md) §3.5 / §4.5**.
- The MOTD chantier exposes mapping live to every SSH login —
  **[MOTD section](#)** below for the per-node hardware display.
