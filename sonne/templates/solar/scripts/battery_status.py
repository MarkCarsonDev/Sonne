"""Solar template data script: exposes a ``battery`` variable to templates.

With ``solar.battery_simulation: false`` in sonne.yaml the build machine's
battery is read (via psutil, or sysfs on Linux). Otherwise, or when no battery
can be read, a solar-charged battery is simulated from the time of day.
"""

import random
from datetime import datetime
from pathlib import Path

from sonne.core.config import Config
from sonne.script_api import sonne_var

DAYLIGHT_HOURS = range(6, 18)
MINUTES_TO_CHARGE_ONE_PERCENT = 2.4  # about 4 hours from empty to full
MINUTES_OF_USE_PER_PERCENT = 6  # about 10 hours from full to empty
LINUX_BATTERY_DIR = Path("/sys/class/power_supply/BAT0")


def main():
    now = datetime.now()
    battery = None if simulation_enabled() else read_system_battery()
    battery = battery or simulate_solar_battery(now)
    battery["is_daytime"] = now.hour in DAYLIGHT_HOURS
    battery["timestamp"] = now.isoformat()
    battery["formatted_time"] = now.strftime("%H:%M:%S")
    if battery["remaining_time"]:
        battery["remaining_formatted"] = format_duration(battery["remaining_time"])
    sonne_var("battery", battery)


def simulation_enabled():
    site_config = Config(base_dir=str(Path(__file__).parent.parent))
    return site_config.get("solar", "battery_simulation", default=True)


def read_system_battery():
    """Return the build machine's battery state, or None if it can't be read."""
    return read_psutil_battery() or read_linux_battery()


def read_psutil_battery():
    try:
        import psutil
    except ImportError:
        return None
    battery = psutil.sensors_battery()
    if battery is None:
        return None
    seconds_left = battery.secsleft if battery.secsleft >= 0 else None
    return {
        "percentage": round(battery.percent),
        "charging": battery.power_plugged,
        "remaining_time": seconds_left,
        "source": "system",
    }


def read_linux_battery():
    try:
        percentage = int((LINUX_BATTERY_DIR / "capacity").read_text().strip())
        status = (LINUX_BATTERY_DIR / "status").read_text().strip()
    except (OSError, ValueError):
        return None
    return {
        "percentage": percentage,
        "charging": status == "Charging",
        "remaining_time": None,
        "source": "sysfs",
    }


def simulate_solar_battery(now):
    """Simulate a battery that tends to be charged and charging in daylight."""
    base_percentage = random.randint(40, 90)
    if now.hour in DAYLIGHT_HOURS:
        percentage = min(100, base_percentage + random.randint(0, 20))
        charging = random.random() < 0.7
    else:
        percentage = max(10, base_percentage - random.randint(0, 30))
        charging = random.random() < 0.2
    return {
        "percentage": percentage,
        "charging": charging,
        "remaining_time": estimate_seconds_remaining(percentage, charging),
        "source": "simulation",
    }


def estimate_seconds_remaining(percentage, charging):
    """Seconds until full when charging, or until empty when discharging."""
    if charging:
        minutes = int((100 - percentage) * MINUTES_TO_CHARGE_ONE_PERCENT)
    else:
        minutes = int(percentage * MINUTES_OF_USE_PER_PERCENT)
    return minutes * 60 or None


def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    return f"{hours}h {remainder // 60}m"


main()
