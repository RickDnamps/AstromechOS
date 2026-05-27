"""Unit tests for the SHOW-track expand/flatten logic (choreo_bp._flatten_show
+ _resolve_chor_path + the schema acceptance of a 'show' track).

Runs standalone. Monkeypatches choreo_bp._CHOREO_DIR to a temp dir so it never
touches real choreographies. (Import requires master.* deps — run on the Pi or
any env where master.registry imports.)
"""
import os
import sys
import json
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from master.api import choreo_bp as C


def _chor(name, tracks, dur):
    return {'meta': {'name': name, 'duration': dur, 'version': 1}, 'tracks': tracks}


def _write(d, name, chor):
    with open(os.path.join(d, name + '.chor'), 'w', encoding='utf-8') as f:
        json.dump(chor, f)


def run():
    d = tempfile.mkdtemp(prefix='show_test_')
    orig = C._CHOREO_DIR
    C._CHOREO_DIR = d
    failed = 0
    try:
        _write(d, 'child', _chor('child', {
            'audio':   [{'t': 0, 'action': 'play', 'file': 'BEEP', 'duration': 1}],
            'dome':    [{'t': 1, 'power': 0.5, 'duration': 500}],
            'markers': [{'t': 0.5, 'label': 'x'}],
        }, 3))
        parent = _chor('parent', {
            'lights': [{'t': 0, 'mode': 'on', 'duration': 1}],
            'show':   [{'t': 5, 'choreo': 'child'}],
        }, 8)

        def check(label, cond):
            nonlocal failed
            print(("  PASS " if cond else "  FAIL ") + label)
            if not cond:
                failed += 1

        out = C._flatten_show(parent)
        check("show track stripped", 'show' not in out['tracks'])
        au = out['tracks'].get('audio', [])
        check("child audio offset 0->5", len(au) == 1 and abs(au[0]['t'] - 5.0) < 1e-6)
        dm = out['tracks'].get('dome', [])
        check("child dome offset 1->6", len(dm) == 1 and abs(dm[0]['t'] - 6.0) < 1e-6)
        check("child markers NOT merged", not out['tracks'].get('markers'))
        check("parent lights preserved", len(out['tracks'].get('lights', [])) == 1)
        check("duration covers tail (>=8)", out['meta']['duration'] >= 8.0)
        check("parent not mutated (still has show)", 'show' in parent['tracks'])

        # self-reference → skipped, terminates
        sr = _chor('selfref', {'show': [{'t': 0, 'choreo': 'selfref'}]}, 2)
        check("self-ref terminates + strips", 'show' not in C._flatten_show(sr)['tracks'])

        # cycle a->b->a → terminates
        _write(d, 'cyca', _chor('cyca', {'show': [{'t': 0, 'choreo': 'cycb'}]}, 2))
        _write(d, 'cycb', _chor('cycb', {'show': [{'t': 0, 'choreo': 'cyca'}]}, 2))
        with open(os.path.join(d, 'cyca.chor'), encoding='utf-8') as f:
            ca = json.load(f)
        check("cycle a<->b terminates", 'show' not in C._flatten_show(ca)['tracks'])

        # missing ref → skipped, no crash
        check("missing ref skipped",
              'show' not in C._flatten_show(_chor('m', {'show': [{'t': 0, 'choreo': 'nope'}]}, 1))['tracks'])

        # path traversal blocked
        check("resolve rejects traversal", C._resolve_chor_path('../etc/passwd') is None)
        check("resolve rejects slash", C._resolve_chor_path('a/b') is None)
        check("resolve accepts plain name", C._resolve_chor_path('child') is not None)
        trav = C._flatten_show(_chor('t', {'show': [{'t': 0, 'choreo': '../child'}]}, 1))
        check("traversal ref does not load", not trav['tracks'].get('audio'))

        # nested show (grandchild) expands with summed offset
        _write(d, 'mid', _chor('mid', {'show': [{'t': 2, 'choreo': 'child'}]}, 6))
        gp = _chor('gp', {'show': [{'t': 10, 'choreo': 'mid'}]}, 20)
        og = C._flatten_show(gp)
        gau = og['tracks'].get('audio', [])
        check("nested offset 0+2+10=12", len(gau) == 1 and abs(gau[0]['t'] - 12.0) < 1e-6)

        # schema: accept valid show, reject bad choreo name
        okv, _ = C._validate_chor_schema(parent)
        check("schema accepts valid show", okv)
        badv, _ = C._validate_chor_schema(_chor('b', {'show': [{'t': 0, 'choreo': '../x'}]}, 1))
        check("schema rejects bad show ref", not badv)

        # _choreo_movement_flags: aggregate (uses_prop, uses_dome) over show refs
        _write(d, 'drive1', _chor('drive1', {'propulsion': [{'t': 0, 'left': 0.5, 'right': 0.5, 'duration': 1}]}, 2))
        _write(d, 'domer',  _chor('domer',  {'dome': [{'t': 0, 'power': 0.5, 'duration': 500}]}, 2))
        _write(d, 'showprop',   _chor('showprop',   {'show': [{'t': 0, 'choreo': 'drive1'}]}, 2))
        _write(d, 'shownested', _chor('shownested', {'show': [{'t': 0, 'choreo': 'showprop'}]}, 2))
        _write(d, 'showdome',   _chor('showdome',   {'show': [{'t': 0, 'choreo': 'domer'}]}, 2))
        check("flags: direct propulsion", C._choreo_movement_flags('drive1') == (True, False))
        check("flags: direct dome", C._choreo_movement_flags('domer') == (False, True))
        check("flags: show->propulsion", C._choreo_movement_flags('showprop') == (True, False))
        check("flags: nested show->show->prop", C._choreo_movement_flags('shownested') == (True, False))
        check("flags: show->dome", C._choreo_movement_flags('showdome') == (False, True))
        check("flags: missing ref -> (F,F)", C._choreo_movement_flags('nope') == (False, False))
        check("flags: cycle a<->b terminates -> (F,F)", C._choreo_movement_flags('cyca') == (False, False))

        # _cascade_show_refs: rename rewrites the ref; delete drops the block
        _write(d, 'shp', _chor('shp', {'show': [{'t': 0, 'choreo': 'target1'}, {'t': 5, 'choreo': 'other'}]}, 8))
        C._cascade_show_refs('target1', 'target2')
        with open(os.path.join(d, 'shp.chor'), encoding='utf-8') as f:
            refs = [b.get('choreo') for b in json.load(f)['tracks']['show']]
        check("cascade rename rewrites ref", refs == ['target2', 'other'])
        C._cascade_show_refs('target2', None)
        with open(os.path.join(d, 'shp.chor'), encoding='utf-8') as f:
            refs2 = [b.get('choreo') for b in json.load(f)['tracks']['show']]
        check("cascade delete drops block", refs2 == ['other'])
        # _already_locked path (choreo_delete passes True) must not deadlock
        C._cascade_show_refs('other', None, _already_locked=True)
        with open(os.path.join(d, 'shp.chor'), encoding='utf-8') as f:
            refs3 = [b.get('choreo') for b in json.load(f)['tracks']['show']]
        check("cascade delete (_already_locked) drops", refs3 == [])

        # audit #1: an empty (unconfigured) show ref must NOT block the save
        okempty, _ = C._validate_chor_schema(_chor('e', {'show': [{'t': 0, 'choreo': ''}]}, 1))
        check("schema allows empty show ref", okempty)
        # audit #2: global load budget caps total ref expansions
        _write(d, 'ca', _chor('ca', {'audio': [{'t': 0, 'action': 'play', 'file': 'A', 'duration': 1}]}, 2))
        _write(d, 'cb', _chor('cb', {'audio': [{'t': 0, 'action': 'play', 'file': 'B', 'duration': 1}]}, 2))
        budtest = _chor('budtest', {'show': [{'t': 0, 'choreo': 'ca'}, {'t': 1, 'choreo': 'cb'}]}, 3)
        ob = C._flatten_show(budtest, _budget=[1])   # budget of 1 → only the first ref loads
        check("budget caps ref loads", len(ob['tracks'].get('audio', [])) == 1)

        print("\n%s" % ("ALL SHOW-flatten tests PASSED" if not failed else f"{failed} TEST(S) FAILED"))
        return 1 if failed else 0
    finally:
        C._CHOREO_DIR = orig
        shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(run())
