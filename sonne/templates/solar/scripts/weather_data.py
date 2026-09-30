"""Solar template data script: exposes ``current_weather`` and
``forecast`` (the next three days) to templates.

Weather comes from Open-Meteo (no API key needed) for the location under
``site.weather`` in sonne.yaml. When the API can't be reached, simulated
weather is used so offline builds still work.
"""

import json
import logging
import random
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sonne import __version__
from sonne.script_api import sonne_config, sonne_var

logger = logging.getLogger("sonne")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 5
FORECAST_DAYS = 3
DEFAULT_LOCATION = {
    "location": "Long Beach, CA",
    "latitude": 33.77,
    "longitude": -118.19,
    "units": "metric",
}

# Open-Meteo WMO weather code -> (description, icon)
WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "⛅"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌧️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Light freezing drizzle", "🌧️❄️"),
    57: ("Dense freezing drizzle", "🌧️❄️"),
    61: ("Slight rain", "🌦️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Light freezing rain", "🌧️❄️"),
    67: ("Heavy freezing rain", "🌧️❄️"),
    71: ("Slight snow fall", "❄️"),
    73: ("Moderate snow fall", "❄️"),
    75: ("Heavy snow fall", "❄️"),
    77: ("Snow grains", "❄️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),
    85: ("Slight snow showers", "❄️"),
    86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}
UNKNOWN_WEATHER = ("Unknown", "🌡️")

# Weather codes the simulation picks from, with how far each shifts the
# temperature away from the location's typical value (in degrees Celsius).
SIMULATED_CONDITIONS = {0: 3, 2: 1, 3: 0, 45: -1, 61: -2, 63: -1, 71: -4, 95: -2}
TYPICAL_TEMPERATURE_CELSIUS = 25


def main():
    location = weather_location()
    try:
        current, forecast = fetch_open_meteo(location)
    except (URLError, OSError, ValueError, KeyError, IndexError) as error:
        logger.warning(f"Weather API unavailable ({error}); using simulated weather")
        current, forecast = simulate_weather(location)
    sonne_var("current_weather", current)
    sonne_var("forecast", forecast)


def weather_location():
    return {**DEFAULT_LOCATION, **sonne_config("site", "weather", default={})}


def fetch_open_meteo(location):
    """Return (current, forecast) from the Open-Meteo API; raises on failure."""
    query = urlencode(
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current_weather": "true",
            "daily": "weathercode,temperature_2m_max,temperature_2m_min",
            "temperature_unit": "celsius" if is_metric(location) else "fahrenheit",
            "timezone": "auto",
        }
    )
    request = Request(f"{OPEN_METEO_URL}?{query}", headers={"User-Agent": f"Sonne/{__version__}"})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))

    now = data["current_weather"]
    current = describe(now["weathercode"], now["temperature"], location)
    current["wind_speed"] = now.get("windspeed")
    current["source"] = "open-meteo"
    return current, daily_forecast(data["daily"], location)


def daily_forecast(daily, location):
    """Forecast entries for the days after today, averaging each day's high and low."""
    today = datetime.now().strftime("%Y-%m-%d")
    forecast = []
    for index, day in enumerate(daily["time"]):
        if len(forecast) == FORECAST_DAYS:
            break
        if day <= today:
            continue
        average = (daily["temperature_2m_max"][index] + daily["temperature_2m_min"][index]) / 2
        entry = describe(daily["weathercode"][index], average, location)
        forecast.append({**entry, **day_labels(datetime.strptime(day, "%Y-%m-%d"))})
    return forecast


def simulate_weather(location):
    """Random but plausible (current, forecast) for when the API is unreachable."""
    current = describe(*simulated_reading(spread=3), location, from_celsius=True)
    current["wind_speed"] = random.randint(1, 15)
    current["source"] = "simulation"
    forecast = [
        {
            **describe(*simulated_reading(spread=5), location, from_celsius=True),
            **day_labels(datetime.now() + timedelta(days=days_ahead)),
        }
        for days_ahead in range(1, FORECAST_DAYS + 1)
    ]
    return current, forecast


def simulated_reading(spread):
    """A random (weather code, temperature in Celsius) pair."""
    code, shift = random.choice(list(SIMULATED_CONDITIONS.items()))
    return code, TYPICAL_TEMPERATURE_CELSIUS + shift + random.randint(-spread, spread)


def describe(code, temperature, location, from_celsius=False):
    """The fields every weather entry shares, with the temperature in the site's unit."""
    if from_celsius and not is_metric(location):
        temperature = temperature * 9 / 5 + 32
    description, icon = WEATHER_CODES.get(code, UNKNOWN_WEATHER)
    return {
        "location": location["location"],
        "temperature": round(temperature),
        "unit_symbol": "C" if is_metric(location) else "F",
        "description": description,
        "icon": code,
        "icon_text": icon,
        "timestamp": datetime.now().isoformat(),
    }


def day_labels(day):
    return {"date": day.strftime("%m/%d"), "day_name": day.strftime("%a")}


def is_metric(location):
    return location["units"] == "metric"


main()
