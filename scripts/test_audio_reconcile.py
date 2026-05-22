"""Unit tests for the pure audio-index reconciliation logic."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from master.api.audio_reconcile import reconcile_index, should_abort_reconcile


def test_removes_ghost_entries():
    idx = {'categories': {'happy': ['A', 'GHOST'], 'sad': ['B']}}
    new, rep = reconcile_index(idx, {'A', 'B'})
    assert 'GHOST' not in new['categories']['happy']
    assert new['categories']['happy'] == ['A']
    assert rep['removed'] == ['GHOST']


def test_adds_orphans_to_others():
    idx = {'categories': {'happy': ['A']}}
    new, rep = reconcile_index(idx, {'A', 'ORPHAN1', 'ORPHAN2'})
    assert new['categories']['others'] == ['ORPHAN1', 'ORPHAN2']
    assert rep['added_to_others'] == ['ORPHAN1', 'ORPHAN2']


def test_preserves_multicategory_membership():
    idx = {'categories': {'scream': ['S1'], 'special': ['S1']}}
    new, _ = reconcile_index(idx, {'S1'})
    assert new['categories']['scream'] == ['S1']
    assert new['categories']['special'] == ['S1']


def test_no_change_when_consistent():
    idx = {'categories': {'happy': ['A', 'B']}}
    new, rep = reconcile_index(idx, {'A', 'B'})
    assert rep['removed'] == [] and rep['added_to_others'] == []


def test_idempotent():
    idx = {'categories': {'happy': ['A', 'GHOST']}}
    once, _ = reconcile_index(idx, {'A', 'NEW'})
    twice, rep2 = reconcile_index(once, {'A', 'NEW'})
    assert once == twice
    assert rep2['removed'] == [] and rep2['added_to_others'] == []


def test_recomputes_total():
    idx = {'categories': {'happy': ['A'], 'sad': ['B', 'C']}, 'total': 999}
    new, _ = reconcile_index(idx, {'A', 'B', 'C'})
    assert new['total'] == 3


def test_does_not_mutate_input():
    idx = {'categories': {'happy': ['A', 'GHOST']}}
    reconcile_index(idx, {'A'})
    assert idx['categories']['happy'] == ['A', 'GHOST']


def test_handles_non_list_category():
    idx = {'categories': {'happy': None}}
    new, _ = reconcile_index(idx, {'A'})
    assert new['categories']['others'] == ['A']


def test_abort_guard_empty_files_nonempty_index():
    idx = {'categories': {'happy': ['A']}}
    assert should_abort_reconcile(set(), idx, force=False) is True
    assert should_abort_reconcile(set(), idx, force=True) is False
    assert should_abort_reconcile({'A'}, idx, force=False) is False
    assert should_abort_reconcile(set(), {'categories': {}}, force=False) is False
