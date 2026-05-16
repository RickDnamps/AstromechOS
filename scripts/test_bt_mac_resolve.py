"""One-shot test for _resolve_device_mac on the Pi.
   Probes evdev devices + simulates resolution with empty uniq."""
import sys
sys.path.insert(0, '/home/artoo/astromechos')

print("=== EVDEV PROBE ===")
try:
    from evdev import InputDevice, list_devices
    for p in list_devices():
        try:
            d = InputDevice(p)
            print(f"{p}: name={d.name!r} uniq={d.uniq!r} phys={d.phys!r}")
        except Exception as e:
            print(f"{p}: ERR {e}")
except Exception as e:
    print(f"evdev not available: {e}")

print("\n=== _resolve_device_mac UNIT TEST ===")
from master.drivers.bt_controller_driver import BTControllerDriver

class FakeDev:
    """Simulates an NVIDIA Shield: empty uniq, real name."""
    name = "NVIDIA Controller v01.04"
    uniq = ""
    phys = ""

class FakeDevWithUniq:
    name = "DUALSHOCK 4"
    uniq = "AA:BB:CC:DD:EE:FF"
    phys = ""

print("Case 1 (NVIDIA empty uniq, fallback to bluetoothctl):")
print("  resolved =", BTControllerDriver._resolve_device_mac(FakeDev()))

print("Case 2 (PS4 with uniq, direct):")
print("  resolved =", BTControllerDriver._resolve_device_mac(FakeDevWithUniq()))

print("Case 3 (no name, no uniq):")
class Empty:
    name = ""
    uniq = ""
    phys = ""
print("  resolved =", BTControllerDriver._resolve_device_mac(Empty()))
