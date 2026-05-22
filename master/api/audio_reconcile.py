"""Pure reconciliation logic for sounds_index.json against the set of .mp3
stems that actually exist on the Slave. No I/O, no Flask, no paramiko — kept
dependency-free so it is unit-testable in isolation.

A 'stem' is a filename without its .mp3 extension. Index shape:
{'categories': {category_name: [stem, ...]}, 'total': int}.
"""
from __future__ import annotations
import copy


def reconcile_index(index: dict, present_stems, others_cat: str = 'others'):
    """Return (new_index, report) reconciling `index` against `present_stems`.

    - Ghosts (indexed stem with no file) removed from every category.
    - Orphans (file with no index entry) appended to `others_cat`, sorted.
    - Multi-category membership preserved for present stems.
    - Top-level 'total' recomputed = number of (category, stem) pairs.
    - Idempotent. Does not mutate `index`.
    """
    present = set(present_stems)
    new_index = copy.deepcopy(index) if isinstance(index, dict) else {}
    cats = new_index.setdefault('categories', {})

    removed_set = set()
    for cat_name, stems in list(cats.items()):
        if not isinstance(stems, list):
            cats[cat_name] = []
            continue
        kept = []
        for s in stems:
            if s in present:
                kept.append(s)
            else:
                removed_set.add(s)
        cats[cat_name] = kept

    indexed = {s for stems in cats.values() for s in stems}
    orphans = sorted(present - indexed)
    if orphans:
        bucket = cats.setdefault(others_cat, [])
        for s in orphans:
            if s not in bucket:
                bucket.append(s)
        bucket.sort()

    new_index['total'] = sum(len(v) for v in cats.values())
    return new_index, {'removed': sorted(removed_set), 'added_to_others': orphans}


def should_abort_reconcile(present_stems, index: dict, force: bool = False) -> bool:
    """Anti-wipe guard: refuse to reconcile against an empty file set when the
    index still holds sounds (Slave dir probably temporarily unavailable),
    unless force=True. The orchestration MUST also abort when the SFTP listing
    itself failed — that I/O concern is handled by the caller, not here."""
    if force:
        return False
    has_files = len(set(present_stems)) > 0
    cats = index.get('categories', {}) if isinstance(index, dict) else {}
    has_index = any(isinstance(v, list) and v for v in cats.values())
    return (not has_files) and has_index
