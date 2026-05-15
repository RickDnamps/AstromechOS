"""One-shot diagnostic: parse every .mp3 in slave/sounds and report
bitrate detection coverage + duration estimate sanity-check."""
import os, sys, glob

sys.path.insert(0, '/home/artoo/astromechos')
from master.api.audio_bp import _parse_mp3_bitrate, _estimate_duration_ms

SOUNDS = '/home/artoo/astromechos/slave/sounds'

files = sorted(glob.glob(os.path.join(SOUNDS, '*.mp3')))
print(f'Total .mp3 files: {len(files)}')

# Bitrate distribution across the whole library.
bitrate_counts = {}
unparsed = []
for path in files:
    br = _parse_mp3_bitrate(path)
    bitrate_counts[br] = bitrate_counts.get(br, 0) + 1
    if br is None:
        unparsed.append(os.path.basename(path))

print('\nBitrate distribution:')
for br, n in sorted(bitrate_counts.items(),
                    key=lambda x: (-1 if x[0] is None else x[0])):
    label = 'UNPARSED (fallback to 192)' if br is None else f'{br} kbps'
    pct = 100 * n / len(files)
    print(f'  {label:30s} {n:4d} files  ({pct:5.1f}%)')

if unparsed:
    print(f'\nUNPARSED files (first 10): {unparsed[:10]}')
else:
    print('\nALL files parsed -> 100% accurate estimates')

# Sample one file per detected bitrate, show estimate.
print('\nEstimate sample (one file per bitrate seen):')
print(f'  {"file":40s} {"size":>10s} {"bitrate":>9s} {"est":>7s}')
seen = set()
for path in files:
    br = _parse_mp3_bitrate(path)
    if br in seen:
        continue
    seen.add(br)
    size = os.path.getsize(path)
    est  = _estimate_duration_ms(path)
    print(f'  {os.path.basename(path):40s} {size:>9d}B {br or 0:>6d}kbps {est/1000:>6.1f}s')

# Birthday is our known-good ground truth: mpg123 -t says 0:39.
# Estimate must come out within ±2s of 39s.
path = os.path.join(SOUNDS, 'birthday.mp3')
if os.path.exists(path):
    est_s = _estimate_duration_ms(path) / 1000.0
    print(f'\nbirthday.mp3 ground-truth check:')
    print(f'  mpg123 -t actual: 39.0 s')
    print(f'  our estimate:     {est_s:.1f} s')
    print(f'  ' + ('PASS' if abs(est_s - 39) <= 2 else 'FAIL'))
