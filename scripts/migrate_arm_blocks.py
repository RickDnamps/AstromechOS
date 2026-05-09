#!/usr/bin/env python3
# ============================================================
#  AstromechOS — Open control platform for astromech builders
#  Copyright (C) 2026 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
# ============================================================
"""
One-shot migration: arm_servos events with a single 'duration' field get
split into the new per-segment fields used by the timeline inspector.

Before:  {"track": "arm_servos", "duration": 1.2, "arm": 1, "action": "open", ...}
After:   {"track": "arm_servos", "panel_duration": 1.2, "arm_duration": 1.2,
          "delay": 0.5, "arm": 1, "action": "open", ...}

Idempotent — events that already have panel_duration / arm_duration / delay
are left alone. Re-run safely after a deploy or a Pi sync.

Usage:
    python3 scripts/migrate_arm_blocks.py [<choreographies_dir>]

Default dir: <repo>/master/choreographies
"""
import json
import os
import sys
from pathlib import Path

DEFAULT_DELAY = 0.5


def migrate_event(ev: dict) -> bool:
    """Returns True if the event was modified."""
    if 'panel_duration' in ev or 'arm_duration' in ev or 'delay' in ev:
        return False
    if 'duration' not in ev:
        return False
    seed = ev.pop('duration')
    try:
        seed_val = max(0.1, float(seed))
    except (TypeError, ValueError):
        seed_val = 1.0
    ev['panel_duration'] = seed_val
    ev['arm_duration']   = seed_val
    ev['delay']          = DEFAULT_DELAY
    return True


def migrate_file(path: Path) -> int:
    """Returns the number of arm events migrated in this file."""
    with path.open(encoding='utf-8') as f:
        chor = json.load(f)
    arms = chor.get('tracks', {}).get('arm_servos', [])
    if not arms:
        return 0
    n_changed = sum(1 for ev in arms if migrate_event(ev))
    if n_changed:
        with path.open('w', encoding='utf-8') as f:
            json.dump(chor, f, ensure_ascii=False, indent=2)
            f.write('\n')
    return n_changed


def main():
    if len(sys.argv) > 1:
        chor_dir = Path(sys.argv[1])
    else:
        repo = Path(__file__).resolve().parent.parent
        chor_dir = repo / 'master' / 'choreographies'

    if not chor_dir.is_dir():
        print(f'Choreography directory not found: {chor_dir}', file=sys.stderr)
        sys.exit(1)

    files_touched = 0
    events_touched = 0
    for path in sorted(chor_dir.glob('*.chor')):
        n = migrate_file(path)
        if n:
            files_touched += 1
            events_touched += n
            print(f'  migrated {n:2d} arm event(s) in {path.name}')

    print(f'\nDone — {events_touched} arm event(s) migrated across {files_touched} file(s) in {chor_dir}')


if __name__ == '__main__':
    main()
