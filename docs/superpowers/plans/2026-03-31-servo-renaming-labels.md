# Servo Renaming & Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `dome_panel_N`/`body_panel_N` servo IDs with hardware-based `Servo_MN`/`Servo_SN` names, add editable label field per servo, display labels in CHOREO timeline, fix servo tab layout.

**Architecture:** ID is the physical channel key (`Servo_M0` = Master HAT ch 0). Label is a user-editable display string stored alongside angles in JSON config. Drivers, API, and .scr sequences use the hardware ID. UI shows label everywhere.

**Tech Stack:** Python (Flask, json), JavaScript (ServoPanel class), CSS grid, JSON config files.

---

### Task 1: Migrate JSON config files

**Files:**
- Modify: `master/config/dome_angles.json`
- Modify: `slave/config/servo_angles.json`

- [ ] Replace keys `dome_panel_N` → `Servo_M{N-1}`, add `label` field pre-filled with `Dome_Panel_N`
- [ ] Replace keys `body_panel_N` → `Servo_S{N-1}`, add `label` field pre-filled with `Body_Panel_N`

---

### Task 2: Migrate Python drivers

**Files:**
- Modify: `master/drivers/dome_servo_driver.py`
- Modify: `slave/drivers/body_servo_driver.py`
- Modify: `master/drivers/body_servo_driver.py`

- [ ] Update SERVO_MAP in dome driver: `dome_panel_N` → `Servo_M{N-1}`
- [ ] Update SERVO_MAP in slave body driver: `body_panel_N` → `Servo_S{N-1}`
- [ ] Update KNOWN_SERVOS in master body driver

---

### Task 3: Migrate servo_bp.py

**Files:**
- Modify: `master/api/servo_bp.py`

- [ ] Update DOME_SERVOS / BODY_SERVOS lists
- [ ] Update `_read_panels_cfg()` to read labels from JSON files
- [ ] Update `_update_angles_file()` to preserve/save label field
- [ ] Update `servo_settings_save()` to accept label in payload

---

### Task 4: Migrate script_engine.py

**Files:**
- Modify: `master/script_engine.py`

- [ ] Replace `name.startswith('dome_panel_')` → `name.startswith('Servo_M')` (2 occurrences)

---

### Task 5: Migrate .scr sequence files

**Files:**
- Modify: all `master/sequences/*.scr`

- [ ] Bulk replace `dome_panel_11`→`Servo_M10`, `dome_panel_10`→`Servo_M9`, ..., `dome_panel_1`→`Servo_M0`
- [ ] Bulk replace `body_panel_11`→`Servo_S10`, ..., `body_panel_1`→`Servo_S0`

---

### Task 6: Update app.js

**Files:**
- Modify: `master/static/js/app.js`

- [ ] Update DOME_SERVOS/BODY_SERVOS arrays
- [ ] Update ServoPanel.render() — add label input, show `Servo_M0` ID
- [ ] Update ServoPanel.updateInputs() — sync label field
- [ ] Update ServoPanel.saveAngles() — include label in payload
- [ ] Update ServoPanel.open/close toasts to use label
- [ ] Update testServoSettings to use `Servo_M0`
- [ ] Update choreo `_blockLabel` — show label from `_servoSettings`
- [ ] Update choreo inspector servo filter prefix (`dome_` → `Servo_M`, `body_` → `Servo_S`)
- [ ] Update inspector dropdown options to show label

---

### Task 7: Update HTML + CSS

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/css/style.css`

- [ ] Add `style="grid-template-columns: 1fr 1fr"` to servo tab systems-grid
- [ ] Update `.servo-name` width (22px → 70px) for `Servo_M10` display
- [ ] Add `.servo-label-in` CSS class for editable label input

---

### Task 8: Sync Android assets + deploy

- [ ] `cp master/static/js/app.js android/.../js/app.js`
- [ ] `cp master/static/css/style.css android/.../css/style.css`
- [ ] commit + push + deploy via paramiko
