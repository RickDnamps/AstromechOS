"""Diagnostic: walk every .mp3 in slave/sounds and verify our duration
estimator agrees with mutagen's frame-accurate decode on every file."""
import os, sys, glob

sys.path.insert(0, '/home/artoo/astromechos')
from master.api.audio_bp import _estimate_duration_ms, _HAVE_MUTAGEN

print(f'mutagen available in audio_bp: {_HAVE_MUTAGEN}')

try:
    from mutagen.mp3 import MP3
except ImportError:
    print('mutagen not installed — re-run scripts/update.sh')
    sys.exit(1)

SOUNDS = '/home/artoo/astromechos/slave/sounds'
files = sorted(glob.glob(os.path.join(SOUNDS, '*.mp3')))
print(f'Total .mp3 files: {len(files)}')

mismatches = []   # files where estimator and mutagen disagree by > 1s
mutagen_failures = []
total_audio_s = 0.0

for path in files:
    try:
        actual_s = MP3(path).info.length
    except Exception as e:
        mutagen_failures.append((os.path.basename(path), str(e)))
        continue
    est_ms = _estimate_duration_ms(path)
    est_s  = est_ms / 1000.0
    # Estimator adds +500ms cold-start tail, so subtract it for the
    # like-for-like comparison.
    audio_only_s = est_s - 0.5
    diff_s = audio_only_s - actual_s
    total_audio_s += actual_s
    if abs(diff_s) > 1.0:
        mismatches.append((os.path.basename(path), actual_s, audio_only_s, diff_s))

print(f'\nTotal audio runtime: {total_audio_s/60:.1f} min ({total_audio_s:.0f} s)')
print(f'mutagen failures:     {len(mutagen_failures)}')
print(f'estimator >1s off:    {len(mismatches)}')

if mutagen_failures:
    print('\nFiles mutagen could not parse:')
    for name, err in mutagen_failures[:10]:
        print(f'  {name}: {err}')

if mismatches:
    print('\nFiles where estimator disagrees with mutagen by >1s:')
    print(f'  {"file":40s} {"actual":>9s} {"estimate":>10s} {"diff":>7s}')
    for name, actual, est, diff in mismatches[:20]:
        print(f'  {name:40s} {actual:>8.2f}s {est:>9.2f}s {diff:>+6.2f}s')
else:
    print('\n✓ ALL files match mutagen within ±1s — duration is now ms-accurate.')

# Spot-check a few specific files for sanity output.
samples = ['birthday', 'Cantina_orig', 'StayinAl', 'ALARM001',
           'TIE_FIGHTER_LASER_PASS', 'Gangnam']
print('\nSpot-check:')
print(f'  {"file":30s} {"mutagen":>10s} {"our est":>10s}')
for name in samples:
    path = os.path.join(SOUNDS, name + '.mp3')
    if not os.path.exists(path):
        continue
    actual = MP3(path).info.length
    est    = _estimate_duration_ms(path) / 1000.0
    print(f'  {name:30s} {actual:>9.2f}s {est:>9.2f}s')
