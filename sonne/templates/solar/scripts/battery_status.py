"""
Battery Status Script for Solar Template

This script:
1. Simulates battery status or reads actual battery status if available
2. Provides this data to the Sonne template through variables
"""

import random
import time
from datetime import datetime, timedelta
import sys
import os

print("Battery status script loaded")

# Try to get real battery status if possible (limited platform support)
def get_real_battery_status():
    """Attempt to get real battery status from the system."""
    try:
        # Try to use psutil if available
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percentage": round(battery.percent),
                "charging": battery.power_plugged,
                "source": "system",
                "remaining_time": battery.secsleft if battery.secsleft != -1 else None,
                "timestamp": datetime.now().isoformat()
            }
    except (ImportError, AttributeError):
        pass
    
    # Try platform-specific methods
    try:
        import platform
        system = platform.system()
        
        if system == "Linux":
            # Try reading from /sys/class/power_supply/
            try:
                with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                    percentage = int(f.read().strip())
                with open("/sys/class/power_supply/BAT0/status", "r") as f:
                    status = f.read().strip()
                    charging = status == "Charging"
                return {
                    "percentage": percentage,
                    "charging": charging,
                    "source": "sysfs",
                    "timestamp": datetime.now().isoformat()
                }
            except (FileNotFoundError, IOError):
                pass
        
        elif system == "Darwin":  # macOS
            try:
                # Try to use subprocess to call system_profiler
                import subprocess
                result = subprocess.run(
                    ["system_profiler", "SPPowerDataType"], 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                output = result.stdout
                
                # Parse the output to extract battery information
                percentage = None
                charging = None
                
                for line in output.splitlines():
                    line = line.strip()
                    if "Charge Information" in line:
                        # Look for percentage in next lines
                        percentage_line = next((l for l in output.splitlines() if "Charge" in l and "%" in l), None)
                        if percentage_line:
                            percentage = int(percentage_line.split("%")[0].strip().split()[-1])
                    
                    if "Charging" in line:
                        charging = "Yes" in line
                
                if percentage is not None:
                    return {
                        "percentage": percentage,
                        "charging": charging if charging is not None else False,
                        "source": "system_profiler",
                        "timestamp": datetime.now().isoformat()
                    }
            except (ImportError, FileNotFoundError, subprocess.SubprocessError):
                pass
    
    except Exception:
        # Fall back to simulation
        pass
    
    return None

# Simulate a solar-powered battery
def simulate_battery_status():
    """Simulate a battery status for a solar-powered device."""
    # Get current time to simulate day/night cycle effects on solar charging
    now = datetime.now()
    
    # Determine if it's daytime (between 6 AM and A6 PM)
    is_daytime = 6 <= now.hour < 18
    
    # Base battery percentage - between 40% and 90%
    base_percentage = random.randint(40, 90)
    
    # Adjust based on time of day
    if is_daytime:
        # During daytime, battery tends to be higher and more likely to be charging
        percentage = min(100, base_percentage + random.randint(0, 20))
        charging = random.random() < 0.7  # 70% chance of charging during day
    else:
        # At night, battery tends to be lower and less likely to be charging
        percentage = max(10, base_percentage - random.randint(0, 30))
        charging = random.random() < 0.2  # 20% chance of charging at night
    
    # Determine estimated remaining time based on charging status
    if charging:
        # If charging, estimate time to full charge
        remaining_minutes = int((100 - percentage) * 2.4)  # Assume ~4 hours to charge from 0-100%
        remaining_time = remaining_minutes * 60 if remaining_minutes > 0 else None
    else:
        # If discharging, estimate time until empty
        remaining_minutes = int(percentage * 6)  # Assume ~10 hours of battery life from 100-0%
        remaining_time = remaining_minutes * 60 if remaining_minutes > 0 else None
    
    # Create a timestamp slightly in the past for realism
    timestamp = (datetime.now() - timedelta(minutes=random.randint(1, 5))).isoformat()
    
    return {
        "percentage": percentage,
        "charging": charging,
        "source": "simulation",
        "remaining_time": remaining_time,
        "timestamp": timestamp,
        "is_daytime": is_daytime
    }

# Write a temporary flag file to ensure we're executing
with open('/tmp/battery_script_executed.txt', 'w') as f:
    f.write(f"Executed at {datetime.now().isoformat()}")

# Main execution
try:
    # Get config to determine if simulation is enabled
    # We'll assume simulation is enabled for this example
    simulation_enabled = True
    battery_data = None
    
    if not simulation_enabled:
        # Try to get real battery data first
        battery_data = get_real_battery_status()
    
    # Fall back to simulation if real data is not available or simulation is forced
    if battery_data is None:
        battery_data = simulate_battery_status()
    
    # Add extra info for display
    battery_data["formatted_time"] = time.strftime("%H:%M:%S")
    if battery_data.get("remaining_time") is not None:
        remaining_hours = battery_data["remaining_time"] // 3600
        remaining_minutes = (battery_data["remaining_time"] % 3600) // 60
        battery_data["remaining_formatted"] = f"{remaining_hours}h {remaining_minutes}m"
    
    # Print debug info before setting variable
    print(f"Battery data generated: {battery_data}")
    
    # Set the variable for use in templates - directly in both global and site scope
    sonne_var("battery", battery_data)
    
    # Also explicitly set it as a global variable
    globals()['battery'] = battery_data
    
    # Create a temporary file with battery data for debugging
    import json
    with open('/tmp/battery_data.json', 'w') as f:
        json.dump(battery_data, f, indent=2)
    
except Exception as e:
    print(f"Error in battery status script: {e}")
    
    # If anything goes wrong, create a simple fallback battery status
    fallback_data = {
        "percentage": 75,
        "charging": True,
        "source": "fallback",
        "timestamp": datetime.now().isoformat(),
        "is_daytime": 6 <= datetime.now().hour < 18,
        "formatted_time": time.strftime("%H:%M:%S"),
        "remaining_formatted": "2h 30m"
    }
    
    print(f"Using fallback battery data: {fallback_data}")
    sonne_var("battery", fallback_data)
    
    # Also write the error to a file for debugging
    with open('/tmp/battery_script_error.txt', 'w') as f:
        f.write(f"Error at {datetime.now().isoformat()}: {e}")