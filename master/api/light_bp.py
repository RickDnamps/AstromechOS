"""Light sequences listing.

Read-only endpoint that enumerates custom light-sequence files (*.lseq) so the
choreo editor can offer them as light-track options alongside the built-in
T-code animations (/teeces/animations). The frontend (loadLightSequences +
choreoEditor light-mode load) calls GET /light/list and expects
{"sequences": [<name>, ...]}; before this route existed it 404'd on every
Lights-tab / choreo-editor load.

LAN-open like the other list/read endpoints (/teeces/animations, /choreo/list):
it exposes only sanitized basenames, never paths, and mutates nothing.
"""
import os
import re
import glob

from flask import Blueprint, jsonify

light_bp = Blueprint('light', __name__)

# master/light_sequences/ — sits next to this file's parent (master/).
_LSEQ_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'light_sequences')

# Defensive: only surface names built from a safe charset so a hand-placed file
# with HTML/shell metacharacters never reaches the UI as an injection sink.
_SAFE_NAME = re.compile(r'^[\w \-.]+$')


@light_bp.route('/light/list', methods=['GET'])
def light_list():
    """Return {'sequences': [<name without .lseq>, ...]} sorted; [] if none."""
    names = []
    try:
        if os.path.isdir(_LSEQ_DIR):
            for path in glob.glob(os.path.join(_LSEQ_DIR, '*.lseq')):
                stem = os.path.splitext(os.path.basename(path))[0]
                if stem and _SAFE_NAME.match(stem):
                    names.append(stem)
    except OSError:
        names = []
    return jsonify({'sequences': sorted(names)})
