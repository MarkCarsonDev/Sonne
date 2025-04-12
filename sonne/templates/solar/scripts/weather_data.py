"""
Weather Data Script for Solar Template using Open-Meteo with Logging

This script:
1. Fetches weather data from the Open-Meteo API for the configured location (requires no API key)
2. Provides this data to the Sonne template through variables
3. Falls back to simulated data if API is unavailable
"""

import json
import random
import time
import logging
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

# Default location (Long Beach, CA)
DEFAULT_LOCATION = {
    "name": "Long Beach, CA",
    "latitude": 33.7743,
    "longitude": -117.938,
    "units": "imperial"  # metric or imperial
}

# Mapping for Open-Meteo weather codes to icon symbols
OPEN_METEO_ICONS = {
    0: "☀️",      # Clear sky
    1: "⛅",      # Mainly clear
    2: "⛅",      # Partly cloudy
    3: "☁️",      # Overcast
    45: "🌫️",    # Fog
    48: "🌫️",    # Depositing rime fog
    51: "🌦️",    # Light drizzle
    53: "🌧️",    # Moderate drizzle
    55: "🌧️",    # Dense drizzle
    56: "🌧️❄️",  # Light freezing drizzle
    57: "🌧️❄️",  # Dense freezing drizzle
    61: "🌦️",    # Slight rain
    63: "🌧️",    # Moderate rain
    65: "🌧️",    # Heavy rain
    66: "🌧️❄️",  # Light freezing rain
    67: "🌧️❄️",  # Heavy freezing rain
    71: "❄️",     # Slight snow fall
    73: "❄️",     # Moderate snow fall
    75: "❄️",     # Heavy snow fall
    77: "❄️",     # Snow grains
    80: "🌦️",    # Slight rain showers
    81: "🌧️",    # Moderate rain showers
    82: "⛈️",     # Violent rain showers
    85: "❄️",     # Slight snow showers
    86: "❄️",     # Heavy snow showers
    95: "⛈️",     # Thunderstorm
    96: "⛈️",     # Thunderstorm with slight hail
    99: "⛈️"      # Thunderstorm with heavy hail
}

# Mapping for Open-Meteo weather codes to description text
OPEN_METEO_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

def fetch_weather_data(location=None):
    """Fetch weather data from the Open-Meteo API."""
    if location is None:
        location = DEFAULT_LOCATION

    latitude = location.get("latitude", DEFAULT_LOCATION["latitude"])
    longitude = location.get("longitude", DEFAULT_LOCATION["longitude"])
    units = location.get("units", DEFAULT_LOCATION["units"])

    # Open-Meteo accepts a temperature_unit parameter ("celsius" or "fahrenheit")
    temperature_unit = "fahrenheit" if units == "imperial" else "celsius"

    # Build the API URL for both current weather and a daily forecast
    base_url = "https://api.open-meteo.com/v1/forecast?"
    params = (
        f"latitude={latitude}&longitude={longitude}&current_weather=true"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min"
        f"&temperature_unit={temperature_unit}&timezone=auto"
    )
    url = base_url + params
    logging.debug("Constructed URL: %s", url)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 Sonne Static Site Generator/0.2.0"
        }
        request = Request(url, headers=headers)
        logging.info("Fetching weather data from Open-Meteo API...")
        with urlopen(request, timeout=5) as response:
            response_data = response.read().decode('utf-8')
            data = json.loads(response_data)
            logging.debug("API response received: %s", data)

        # Process current weather from Open-Meteo
        current = data.get("current_weather", {})
        weathercode = current.get("weathercode", 0)
        description = OPEN_METEO_DESCRIPTIONS.get(weathercode, "Unknown")
        icon_text = OPEN_METEO_ICONS.get(weathercode, "🌡️")
        current_weather = {
            "location": location.get("name", "Unknown Location"),
            "temperature": round(current.get("temperature", 0)),
            "feels_like": round(current.get("temperature", 0)),  # No separate feels_like provided
            "description": description,
            "icon": weathercode,  # Numeric code from Open-Meteo
            "icon_text": icon_text,
            "humidity": None,  # Open-Meteo current weather does not provide humidity
            "wind_speed": current.get("windspeed", 0),
            "timestamp": current.get("time", datetime.now().isoformat()),
            "source": "open-meteo"
        }
        logging.info("Processed current weather: %s", current_weather)

        # Process daily forecast
        daily = data.get("daily", {})
        times = daily.get("time", [])
        weathercodes = daily.get("weathercode", [])
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])

        forecasts = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        forecast_indices = [idx for idx, day in enumerate(times) if day > today_str][:3]
        logging.debug("Forecast indices (next 3 days): %s", forecast_indices)

        for idx in forecast_indices:
            day_date = datetime.strptime(times[idx], "%Y-%m-%d")
            avg_temp = (temps_max[idx] + temps_min[idx]) / 2 if idx < len(temps_max) and idx < len(temps_min) else 0
            weathercode_day = weathercodes[idx] if idx < len(weathercodes) else 0
            forecast = {
                "date": day_date.strftime("%m/%d"),
                "day_name": day_date.strftime("%a"),
                "temperature": round(avg_temp),
                "description": OPEN_METEO_DESCRIPTIONS.get(weathercode_day, "Unknown"),
                "icon": weathercode_day,
                "icon_text": OPEN_METEO_ICONS.get(weathercode_day, "🌡️")
            }
            forecasts.append(forecast)
            logging.debug("Processed forecast for %s: %s", times[idx], forecast)

        return {"current": current_weather, "forecast": forecasts}

    except (URLError, json.JSONDecodeError, KeyError, Exception) as e:
        logging.error("Error fetching weather data: %s", e)
        return None

def simulate_weather_data(location=None):
    """Generate simulated weather data for demonstration purposes."""
    if location is None:
        location = DEFAULT_LOCATION

    location_name = location.get("name", DEFAULT_LOCATION["name"])
    weather_types = [
        {"description": "clear sky", "icon": 0, "temp_adjust": 5},
        {"description": "few clouds", "icon": 2, "temp_adjust": 2},
        {"description": "scattered clouds", "icon": 3, "temp_adjust": 0},
        {"description": "broken clouds", "icon": 3, "temp_adjust": -1},
        {"description": "shower rain", "icon": 61, "temp_adjust": -3},
        {"description": "rain", "icon": 63, "temp_adjust": -2},
        {"description": "thunderstorm", "icon": 95, "temp_adjust": -4},
        {"description": "snow", "icon": 71, "temp_adjust": -8},
        {"description": "mist", "icon": 45, "temp_adjust": -2}
    ]
    current_weather_type = random.choice(weather_types)
    base_temp = 25 if location.get("units") == "metric" else 77
    current_temp = base_temp + current_weather_type["temp_adjust"] + random.randint(-3, 3)

    current_weather = {
        "location": location_name,
        "temperature": current_temp,
        "feels_like": current_temp + random.randint(-2, 2),
        "description": current_weather_type["description"],
        "icon": current_weather_type["icon"],
        "icon_text": OPEN_METEO_ICONS.get(current_weather_type["icon"], "🌡️"),
        "humidity": random.randint(30, 90),
        "wind_speed": random.randint(1, 15),
        "timestamp": datetime.now().isoformat(),
        "source": "simulation"
    }
    logging.info("Using simulated current weather: %s", current_weather)

    forecasts = []
    for i in range(1, 4):
        day_date = datetime.now() + timedelta(days=i)
        day_weather_type = random.choice(weather_types)
        day_temp = base_temp + day_weather_type["temp_adjust"] + random.randint(-5, 5)
        forecast = {
            "date": day_date.strftime("%m/%d"),
            "day_name": day_date.strftime("%a"),
            "temperature": day_temp,
            "description": day_weather_type["description"],
            "icon": day_weather_type["icon"],
            "icon_text": OPEN_METEO_ICONS.get(day_weather_type["icon"], "🌡️")
        }
        forecasts.append(forecast)
        logging.debug("Using simulated forecast for %s: %s", day_date.strftime("%Y-%m-%d"), forecast)

    return {"current": current_weather, "forecast": forecasts}

# Main execution
try:
    location = DEFAULT_LOCATION
    logging.info("Starting weather data fetch for %s", location.get("name"))

    # Attempt to fetch real weather data from Open-Meteo
    weather_data = fetch_weather_data(location)
    if weather_data is None:
        logging.warning("Real weather data unavailable. Falling back to simulated data.")
        weather_data = simulate_weather_data(location)
    else:
        logging.info("Real weather data successfully retrieved.")

    # Set the variables for use in templates
    sonne_var("weather", weather_data["current"])
    sonne_var("forecast", weather_data["forecast"])
    logging.info("Weather and forecast variables set successfully.")

except Exception as e:
    logging.error("Error in main execution: %s", e)
    # If any error occurs, create simple fallback weather data
    fallback_data = {
        "current": {
            "location": DEFAULT_LOCATION["name"],
            "temperature": 22 if DEFAULT_LOCATION["units"] == "metric" else 72,
            "description": "sunny",
            "icon_text": "☀️",
            "source": "fallback"
        },
        "forecast": [
            {
                "date": (datetime.now() + timedelta(days=1)).strftime("%m/%d"),
                "day_name": (datetime.now() + timedelta(days=1)).strftime("%a"),
                "temperature": 23 if DEFAULT_LOCATION["units"] == "metric" else 73,
                "description": "sunny",
                "icon_text": "☀️"
            },
            {
                "date": (datetime.now() + timedelta(days=2)).strftime("%m/%d"),
                "day_name": (datetime.now() + timedelta(days=2)).strftime("%a"),
                "temperature": 24 if DEFAULT_LOCATION["units"] == "metric" else 75,
                "description": "partly cloudy",
                "icon_text": "⛅"
            },
            {
                "date": (datetime.now() + timedelta(days=3)).strftime("%m/%d"),
                "day_name": (datetime.now() + timedelta(days=3)).strftime("%a"),
                "temperature": 21 if DEFAULT_LOCATION["units"] == "metric" else 70,
                "description": "cloudy",
                "icon_text": "☁️"
            }
        ]
    }
    sonne_var("weather", fallback_data["current"])
    sonne_var("forecast", fallback_data["forecast"])
    logging.info("Fallback weather variables set.")
