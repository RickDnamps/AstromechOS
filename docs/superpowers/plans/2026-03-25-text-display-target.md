# Text Display Target (FLD / RLD / Both) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Display target selector (FLD / RLD / Both) to every `teeces,text` step in the Light Editor and the Sequence Editor unified lights form.

**Architecture:** The `text` sub-command of `teeces` gains an optional 4th CSV field (`fld`/`rld`/`both`, default `fld`) for backward compatibility. `TeecesController` gets a new `rld_text()` method. `ScriptEngine._cmd_teeces` dispatches the correct method(s). The REST `/teeces/text` endpoint accepts an optional `display` field. The JS LightEditor and SequenceEditor forms both show the new dropdown.

**Tech Stack:** Python 3.10, Flask, pyserial (JawaLite), Vanilla JS (no framework)

---

## File Map

| File | Change |
|------|--------|
| `master/teeces_controller.py` | Add `rld_text(text)` method → `2M<text>\r` |
| `master/script_engine.py` | `_cmd_teeces` text branch — dispatch by display target |
| `master/api/teeces_bp.py` | `POST /teeces/text` — add optional `display` param |
| `master/static/js/app.js` | LightEditor palette/label/form + SequenceEditor display field |
| `android/app/src/main/assets/js/app.js` | Sync from master |

---

## Task 1: Backend — `rld_text()` + updated `/teeces/text` endpoint

**Files:**
- Modify: `master/teeces_controller.py` (after `fld_text` method, ~line 140)
- Modify: `master/api/teeces_bp.py` (`/teeces/text` route, ~line 84)
- Modify: `master/script_engine.py` (`_cmd_teeces` text branch, ~line 382)

- [ ] **Step 1: Add `rld_text()` to TeecesController**

  In `master/teeces_controller.py`, after the `fld_text` method (line ~143):
  ```python
  def rld_text(self, text: str) -> bool:
      """Texte défilant sur Rear Logic Display. Max ~20 chars."""
      text = text[:20].upper()
      return self.send_command(f"2M{text}\r")
  ```

- [ ] **Step 2: Update `_cmd_teeces` text branch in ScriptEngine**

  In `master/script_engine.py`, replace lines ~382-383:
  ```python
  elif action == 'text':
      self._teeces.fld_text(row[2] if len(row) > 2 else '')
  ```
  With:
  ```python
  elif action == 'text':
      text    = row[2] if len(row) > 2 else ''
      display = row[3].lower() if len(row) > 3 else 'fld'
      if display == 'rld':
          self._teeces.rld_text(text)
      elif display == 'both':
          self._teeces.fld_text(text)
          self._teeces.rld_text(text)
      else:
          self._teeces.fld_text(text)
  ```

- [ ] **Step 3: Update `/teeces/text` REST endpoint**

  In `master/api/teeces_bp.py`, replace the existing `/text` route body (uses module-level `reg` import, `get_json(silent=True)` pattern — match the rest of the file):
  ```python
  @teeces_bp.post('/text')
  def teeces_text():
      """Affiche un texte sur FLD, RLD, ou les deux. Body: {"text": "HELLO", "display": "fld"}"""
      body    = request.get_json(silent=True) or {}
      text    = body.get('text', '').strip()[:20]
      display = body.get('display', 'fld').lower()
      if reg.teeces:
          if display == 'rld':
              reg.teeces.rld_text(text)
          elif display == 'both':
              reg.teeces.fld_text(text)
              reg.teeces.rld_text(text)
          else:
              reg.teeces.fld_text(text)
      return jsonify({'status': 'ok', 'text': text, 'display': display})
  ```

- [ ] **Step 4: Commit**
  ```bash
  git add master/teeces_controller.py master/script_engine.py master/api/teeces_bp.py
  git commit -m "Feat: text display target FLD/RLD/Both — backend"
  ```

---

## Task 2: Light Editor JS — palette rename + step label + form update

**Files:**
- Modify: `master/static/js/app.js`
  - `_initPalette()` text item — rename label + update default args (~line 2296-2310)
  - `_stepLabel()` text branch (~line 2466)
  - `_renderStepForm()` text branch (~line 2544-2545)
  - `_renderStepForm()` OK handler text branch (~line 2613)

- [ ] **Step 1: Rename palette item and update default args**

  In `_initPalette()`, find the FLD Text block (~line 2295-2310).

  Change:
  ```js
  txtItem.dataset.args = JSON.stringify(['text', 'HELLO']);
  txtItem.textContent = '💬 FLD Text';
  ...
  this._addStep('teeces', ['text', 'HELLO']);
  ```
  To:
  ```js
  txtItem.dataset.args = JSON.stringify(['text', 'HELLO', 'fld']);
  txtItem.textContent = '💬 Text';
  ...
  this._addStep('teeces', ['text', 'HELLO', 'fld']);
  ```

- [ ] **Step 2: Update `_stepLabel()` text branch**

  Find line ~2466:
  ```js
  if (action === 'text')  return `💬 "${step.args[1] || ''}"`;
  ```
  Replace with:
  ```js
  if (action === 'text') {
    const disp = (step.args[2] || 'fld').toUpperCase();
    return `💬 [${disp}] "${step.args[1] || ''}"`;
  }
  ```

- [ ] **Step 3: Update `_renderStepForm()` text branch to 2 fields**

  Find the `action === 'text'` branch (~line 2544):
  ```js
  } else if (action === 'text') {
    fields = [{ label:'FLD Text (max 20)', value: args[1]||'', type:'text', placeholder:'HELLO' }];
  ```
  Replace with:
  ```js
  } else if (action === 'text') {
    const curDisp = args[2] || 'fld';
    fields = [
      { label: 'Display', value: curDisp,
        options: ['fld:FLD (Front)', 'rld:RLD (Rear)', 'both:FLD + RLD'] },
      { label: 'Text (max 20)', value: args[1]||'', type:'text', placeholder:'HELLO' },
    ];
  ```

  > Note: The `"N:label"` option format is already supported by the existing LightEditor options renderer (splits on `:`, uses first part as `opt.value`).

- [ ] **Step 4: Update OK handler text branch**

  Find the OK handler text branch (~line 2613):
  ```js
  else if (a === 'text') newArgs = ['text', inputs[0].value.substring(0, 20).toUpperCase()];
  ```
  Replace with:
  ```js
  else if (a === 'text') newArgs = ['text', inputs[1].value.substring(0, 20).toUpperCase(), inputs[0].value];
  ```

  > `inputs[0]` = Display dropdown, `inputs[1]` = text input (order matches fields array from Step 3).

- [ ] **Step 5: Commit**
  ```bash
  git add master/static/js/app.js
  git commit -m "Feat: text display target FLD/RLD/Both — Light Editor UI"
  ```

---

## Task 3: Sequence Editor — add display field to unified lights form

**Files:**
- Modify: `master/static/js/app.js`
  - `_stepFields()` `teeces`/`lseq` case — add 4th field + update `teeces:text` label (~line 3484)
  - `_renderStepForm()` lights show/hide listener — toggle display wrap (~line 3148)
  - `_renderStepForm()` lights OK handler — read display value (~line 3177)
  - `_renderStep()` desc for teeces text (~line 2985)

- [ ] **Step 1: Update `_renderStep` desc for teeces text (show target)**

  Find (~line 2989):
  ```js
  else if (_a === 'text')   _descText = `💬 "${step.args[1] || ''}"`;
  ```
  Replace with:
  ```js
  else if (_a === 'text') { const _d = (step.args[2]||'fld').toUpperCase(); _descText = `💬 [${_d}] "${step.args[1]||''}"` ; }
  ```

- [ ] **Step 2: Update `lightOpts` label for text in `_stepFields`**

  Find (~line 3496):
  ```js
  lightOpts.push({ val: 'teeces:text', lbl: '💬 FLD Text…' });
  ```
  Replace with:
  ```js
  lightOpts.push({ val: 'teeces:text', lbl: '💬 Text…' });
  ```

- [ ] **Step 3: Add display field to `_stepFields` lights return**

  Find the return statement in the `teeces`/`lseq` case (~line 3519):
  ```js
  let curVal = 'teeces:random', subText = '', curPsi = '1';
  ```
  Change the `let` line and the return to add `curDisplay`:
  ```js
  let curVal = 'teeces:random', subText = '', curPsi = '1', curDisplay = 'fld';
  ```

  In the `a0 === 'text'` branch (~line 3513), also capture display:
  ```js
  else if (a0 === 'text') { curVal = 'teeces:text'; subText = args[1]||''; curDisplay = args[2]||'fld'; }
  ```

  Then update the return array to add a 4th field:
  ```js
  return [
    { label: 'Light', value: curVal, options: lightOpts },
    { label: 'Text / Value', value: subText, placeholder: 'HELLO',
      hidden: curVal !== 'teeces:text' && curVal !== 'teeces:raw' },
    { label: 'PSI Mode', value: curPsiOpt, options: psiOpts,
      hidden: curVal !== 'teeces:psi' },
    { label: 'Display', value: curDisplay,
      options: ['fld:FLD (Front)', 'rld:RLD (Rear)', 'both:FLD + RLD'],
      hidden: curVal !== 'teeces:text' },
  ];
  ```

- [ ] **Step 4: Update show/hide listener to toggle display wrap**

  Find the `updateLightSubs` function (~line 3148):
  ```js
  const updateLightSubs = () => {
    const v = inputs[0].value;
    wraps[1].style.display = (v === 'teeces:text' || v === 'teeces:raw') ? '' : 'none';
    wraps[2].style.display = v === 'teeces:psi' ? '' : 'none';
  };
  ```
  Replace with:
  ```js
  const updateLightSubs = () => {
    const v = inputs[0].value;
    wraps[1].style.display = (v === 'teeces:text' || v === 'teeces:raw') ? '' : 'none';
    wraps[2].style.display = v === 'teeces:psi' ? '' : 'none';
    if (wraps[3]) wraps[3].style.display = v === 'teeces:text' ? '' : 'none';
  };
  ```

- [ ] **Step 5: Update OK handler to save display with text**

  Find the `v === 'teeces:text'` branch in the OK handler (~line 3177):
  ```js
  } else if (v === 'teeces:text') {
    this._sequence[idx].cmd  = 'teeces';
    this._sequence[idx].args = ['text', (inputs[1].value||'').toUpperCase().slice(0,20)];
  ```
  Replace with:
  ```js
  } else if (v === 'teeces:text') {
    this._sequence[idx].cmd  = 'teeces';
    const _disp = inputs[3]?.value || 'fld';
    this._sequence[idx].args = ['text', (inputs[1].value||'').toUpperCase().slice(0,20), _disp];
  ```

- [ ] **Step 6: Commit**
  ```bash
  git add master/static/js/app.js
  git commit -m "Feat: text display target FLD/RLD/Both — Sequence Editor unified form"
  ```

---

## Task 4: Sync Android assets + deploy

**Files:**
- Modify: `android/app/src/main/assets/js/app.js` (copy from master)

- [ ] **Step 1: Copy app.js to Android assets**
  ```bash
  cp master/static/js/app.js android/app/src/main/assets/js/app.js
  ```

- [ ] **Step 2: Commit + push**
  ```bash
  git add android/app/src/main/assets/js/app.js
  git commit -m "ci: sync Android assets — text display target"
  git push
  ```

- [ ] **Step 3: Deploy to Master Pi**
  ```python
  import paramiko, sys, io
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
  stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
  for line in stdout: print(line, end='')
  c.close()
  ```

---

## Backward Compatibility

Existing `.lseq` files with `teeces,text,HELLO` (no 4th field) default to `fld` throughout — no migration needed.
