#!/usr/bin/env python3
"""
scr_to_chor.py — Convert legacy .scr sequences to .chor choreography format.

Usage:
    python tools/scr_to_chor.py [--scr-dir master/sequences] [--out-dir master/choreographies]

Mapping:
    sound,file         → audio track PLAY block
    sleep,N            → advances time cursor by N seconds
    sleep,random,a,b   → advances by (a+b)/2 seconds
    teeces,*           → lights track block (duration = until next teeces command)
    servo,name,action  → dome_servos or body_servos track
    dome,turn,speed    → dome track
    dome,stop          → dome track (power=0)
    dome,random,on/off → marker on timeline
    motion,L,R,dur_ms  → propulsion track
    script,name        → marker on timeline
    lseq,name          → marker on timeline
"""

import json
import os
import sys
import re
from datetime import date

SCR_DIR = os.path.join(os.path.dirname(__file__), '..', 'master', 'sequences')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'master', 'choreographies')


def parse_sleep(args: list) -> float:
    """Return duration in seconds for a sleep command."""
    if not args:
        return 0.0
    if args[0].lower() == 'random' or args[0].lower() == 'fixed':
        # sleep,random,min,max  or  sleep,fixed,N
        vals = [float(x) for x in args[1:] if x.replace('.', '', 1).isdigit() or (x.startswith('-') and x[1:].replace('.', '', 1).isdigit())]
        if len(vals) >= 2:
            return (vals[0] + vals[1]) / 2.0
        elif len(vals) == 1:
            return vals[0]
        return 0.5
    try:
        return float(args[0])
    except ValueError:
        return 0.0


def servo_track(servo_name: str) -> str:
    """Determine which track a servo belongs to."""
    name = servo_name.lower()
    if name.startswith('body_') or name.startswith('arm_'):
        return 'body_servos'
    return 'dome_servos'


def convert_scr(path: str, name: str) -> dict:
    """Convert a single .scr file to a .chor dict."""
    tracks = {
        'audio':       [],
        'lights':      [],
        'dome':        [],
        'dome_servos': [],
        'body_servos': [],
        'arm_servos':  [],
        'propulsion':  [],
        'markers':     [],
    }

    t = 0.0                    # time cursor (seconds)
    pending_lights = None      # last lights block — needs duration set at next lights cmd
    audio_ch = 0               # alternate audio channels for overlapping sounds

    with open(path, encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            cmd = parts[0].lower()
            args = parts[1:]

            # ── Sleep ─────────────────────────────────────────────────────────
            if cmd == 'sleep':
                dur = parse_sleep(args)
                t = round(t + dur, 4)

            # ── Sound ─────────────────────────────────────────────────────────
            elif cmd == 'sound':
                if args and args[0].upper() == 'STOP':
                    tracks['audio'].append({'t': t, 'action': 'stop', 'duration': 0.2, 'ch': 0})
                    tracks['audio'].append({'t': t, 'action': 'stop', 'duration': 0.2, 'ch': 1})
                elif args and args[0].upper() == 'RANDOM':
                    category = args[1] if len(args) > 1 else 'happy'
                    file_ref = f'RANDOM:{category}'
                    tracks['audio'].append({
                        't': t, 'action': 'play', 'file': file_ref,
                        'volume': 85, 'duration': 5, 'ch': 0,
                    })
                else:
                    file_ref = args[0] if args else ''
                    tracks['audio'].append({
                        't': t, 'action': 'play', 'file': file_ref,
                        'volume': 85, 'duration': 5, 'ch': 0,
                    })

            # ── Teeces / Lights ───────────────────────────────────────────────
            elif cmd == 'teeces':
                # Close duration of previous lights block
                if pending_lights is not None:
                    pending_lights['duration'] = max(0.5, round(t - pending_lights['t'], 4))
                    pending_lights = None

                mode_arg = args[0].lower() if args else 'random'

                if mode_arg == 'off':
                    ev = {'t': t, 'mode': 'off', 'duration': 2.0}
                elif mode_arg == 'leia':
                    ev = {'t': t, 'mode': 'leia', 'duration': 4.0}
                elif mode_arg == 'random':
                    ev = {'t': t, 'mode': 'random', 'duration': 4.0}
                elif mode_arg == 'text':
                    text = args[1] if len(args) > 1 else ''
                    ev = {'t': t, 'mode': 'text', 'text': text.upper()[:20],
                          'display': 'fld_top', 'duration': 3.0}
                elif mode_arg == 'psi':
                    psi_mode = args[1] if len(args) > 1 else '1'
                    # Map numeric psi mode to sequence name
                    _PSI_MAP = {'1': 'normal', '2': 'flash', '3': 'alarm',
                                '4': 'failure', '5': 'redalert', '6': 'leia'}
                    ev = {'t': t, 'mode': 'psi', 'target': 'both',
                          'sequence': _PSI_MAP.get(str(psi_mode), 'normal'), 'duration': 3.0}
                elif mode_arg == 'anim':
                    code = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
                    ev = {'t': t, 'mode': f't{code}', 'duration': 4.0}
                elif mode_arg == 'raw':
                    raw_cmd = args[1] if len(args) > 1 else ''
                    ev = {'t': t, 'mode': 'random', 'duration': 2.0,
                          '_raw': raw_cmd}  # best-effort
                else:
                    ev = {'t': t, 'mode': 'random', 'duration': 4.0}

                tracks['lights'].append(ev)
                if mode_arg not in ('off',):
                    pending_lights = ev

            # ── Servo ─────────────────────────────────────────────────────────
            elif cmd == 'servo':
                servo_name = args[0] if args else 'dome_panel_1'
                action = args[1].lower() if len(args) > 1 else 'open'
                duration = 1.0  # default movement duration

                # servo,name,open/close[,angle,speed]
                # servo,name,angle,duration_ms  (numeric second arg)
                if len(args) >= 2 and args[1].lstrip('-').replace('.', '', 1).isdigit():
                    # numeric action = positional servo with duration
                    action = 'open'
                    duration = max(0.2, float(args[1]) / 1000.0) if float(args[1]) > 2 else float(args[1])

                ev = {'t': t, 'servo': servo_name, 'action': action, 'duration': duration}
                if len(args) >= 3 and args[2].isdigit():
                    ev['angle'] = int(args[2])
                if len(args) >= 4 and args[3].isdigit():
                    ev['speed'] = int(args[3])

                track_key = servo_track(servo_name)
                if servo_name.lower() == 'all':
                    # Place in dome_servos as "all" — player handles it
                    track_key = 'dome_servos'
                tracks[track_key].append(ev)

            # ── Dome motor ────────────────────────────────────────────────────
            elif cmd == 'dome':
                sub = args[0].lower() if args else 'stop'
                if sub == 'turn':
                    speed = float(args[1]) if len(args) > 1 else 0.5
                    tracks['dome'].append({
                        't': t, 'power': round(speed * 100, 1),
                        'duration': 1000, 'accel': 0.3, 'easing': 'linear',
                    })
                elif sub == 'stop' or sub == 'center':
                    tracks['dome'].append({
                        't': t, 'power': 0.0,
                        'duration': 200, 'accel': 0.5, 'easing': 'linear',
                    })
                elif sub == 'random':
                    state = args[1].lower() if len(args) > 1 else 'on'
                    tracks['markers'].append({'t': t, 'label': f'dome random {state}'})

            # ── Motion / Propulsion ───────────────────────────────────────────
            elif cmd == 'motion':
                if args and args[0].lower() == 'stop':
                    tracks['propulsion'].append({'t': t, 'left': 0.0, 'right': 0.0, 'duration': 0.5})
                elif len(args) >= 2:
                    try:
                        left  = float(args[0])
                        right = float(args[1])
                        dur_s = float(args[2]) / 1000.0 if len(args) > 2 else 1.0
                        tracks['propulsion'].append({'t': t, 'left': left, 'right': right, 'duration': dur_s})
                    except ValueError:
                        pass

            # ── Sub-script reference → marker ─────────────────────────────────
            elif cmd == 'script':
                sub_name = args[0] if args else '?'
                tracks['markers'].append({'t': t, 'label': f'[script: {sub_name}]'})

            # ── Light sequence reference → marker ─────────────────────────────
            elif cmd == 'lseq':
                lseq_name = args[0] if args else '?'
                tracks['markers'].append({'t': t, 'label': f'[lseq: {lseq_name}]'})

            elif cmd == 'wait_light':
                pass  # no equivalent — safe to ignore

    # Close last pending lights block
    if pending_lights is not None:
        pending_lights['duration'] = max(0.5, round(t - pending_lights['t'], 4))

    # Remove empty tracks
    tracks = {k: v for k, v in tracks.items() if v}

    total_duration = max(t + 2.0, 5.0)

    return {
        'meta': {
            'name':     name,
            'version':  '1.0',
            'duration': round(total_duration, 2),
            'bpm':      0,
            'created':  date.today().isoformat(),
            'author':   'scr_to_chor converter',
            'source':   f'{name}.scr',
        },
        'tracks': tracks,
    }


def main():
    scr_dir = SCR_DIR
    out_dir = OUT_DIR

    # Allow CLI overrides
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == '--scr-dir' and i + 1 < len(args):
            scr_dir = args[i + 1]
        if a == '--out-dir' and i + 1 < len(args):
            out_dir = args[i + 1]

    os.makedirs(out_dir, exist_ok=True)

    scr_files = sorted(f for f in os.listdir(scr_dir) if f.endswith('.scr'))
    if not scr_files:
        print(f'No .scr files found in {scr_dir}')
        return

    ok = 0
    for filename in scr_files:
        name = filename[:-4]
        src  = os.path.join(scr_dir, filename)
        dst  = os.path.join(out_dir, name + '.chor')

        # Skip if .chor already exists (don't overwrite hand-crafted choreos)
        if os.path.exists(dst):
            with open(dst) as f:
                existing = json.load(f)
            if existing.get('meta', {}).get('source') != f'{name}.scr':
                print(f'  SKIP  {name}.chor  (hand-crafted, not overwriting)')
                continue

        try:
            chor = convert_scr(src, name)
            with open(dst, 'w') as f:
                json.dump(chor, f, indent=2)
            n_events = sum(len(v) for v in chor['tracks'].values())
            print(f'  OK    {name}.chor  ({n_events} events, {chor["meta"]["duration"]}s)')
            ok += 1
        except Exception as e:
            print(f'  ERROR {name}.scr: {e}')

    print(f'\n{ok}/{len(scr_files)} converted → {out_dir}')


if __name__ == '__main__':
    main()
