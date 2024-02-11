from typing import Dict, Any
import requests
import requests_cache
from ..IScroller import IScroller
from datetime import datetime

class WeatherScroller(IScroller):
    """
    The WeatherScroller class generates weather information based on the user's configuration.
    It retrieves weather data from an API and formats it into pages that can be displayed on a Stream Deck device.
    """

    url = "https://api.open-meteo.com/v1/forecast"
    cache_time = 120  # seconds
    cache_name = "streamdeck_cache"

    def __init__(self, app: Any, config: Dict[str, Any], font: str) -> None:
        """
        Initializes the WeatherScroller instance.

        Args:
            app (Any): The application instance.
            config (Dict[str, Any]): The configuration settings.
            font (str): The font to be used for displaying weather information.
        """
        super().__init__(app, config, font)
        self._pages: list[str] = []
        self._page_counter: int = 0

    def generate(self) -> bytes:
        """
        Generates weather information based on the user's configuration.

        Returns:
            bytes: The generated weather information.
        """
        self._page_counter = 0
        self._pages.clear()

        if self._config["mode"] == "daily":
            return self._generate_daily()
        else:
            return self._generate_now()

    def deactivate(self):
        """
        Deactivates the scroller.
        Currently does nothing.
        """
        pass

    def _generate_now(self) -> bytes:
        """
        Retrieves current weather data from the API and formats it into pages.

        Returns:
            bytes: The generated weather information.
        """
        params = {
            "latitude": self._config["latitude"],
            "longitude": self._config["longitude"],
            "current": "temperature_2m,relative_humidity_2m,is_day,precipitation,cloud_cover,surface_pressure,wind_speed_10m,wind_direction_10m",
            "timezone": self._config["location"],
            "forecast_days": 1
        }

        with requests_cache.CachedSession(WeatherScroller.cache_name, expire_after=WeatherScroller.cache_time) as s:
            response = s.get(WeatherScroller.url, params=params)
            response_json = response.json()
            current = response_json.get("current")
            units = response_json.get("current_units")

            current_temperature_2m = current.get("temperature_2m")
            current_relative_humidity_2m = current.get("relative_humidity_2m")
            current_surface_pressure = current.get("surface_pressure")

            current_precipitation = current.get("precipitation")
            current_cloud_cover = current.get("cloud_cover")

            current_wind_speed_10m = current.get("wind_speed_10m")
            current_wind_direction_10m = current.get("wind_direction_10m")

            self._pages.append(
                f"Humidity: {current_relative_humidity_2m} {units.get('relative_humidity_2m')}\n"
                f"Pressure: {current_surface_pressure} {units.get('surface_pressure')}\n"
                f"Cloud cover: {current_cloud_cover} {units.get('cloud_cover')}"
            )

            self._pages.append(
                f"Temperature: {current_temperature_2m} {units.get('temperature_2m')}\n"
                f"Precipitation: {current_precipitation} {units.get('precipitation')}\n"
                f"Wind: {current_wind_speed_10m} {units.get('wind_speed_10m')} "
                f"({self._degreesToCardinal(current_wind_direction_10m)})"
            )

        if self.has_next:
            return self.next()
        return None

    def _generate_daily(self) -> bytes:
        """
        Retrieves daily weather data from the API and formats it into pages.

        Returns:
            bytes: The generated weather information.
        """
        params = {
            "latitude": self._config["latitude"],
            "longitude": self._config["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,daylight_duration,uv_index_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant",
            "timezone": self._config["location"],
            "forecast_days": 1
        }

        with requests_cache.CachedSession(WeatherScroller.cache_name, expire_after=WeatherScroller.cache_time) as s:
            response = s.get(WeatherScroller.url, params=params)
            response_json = response.json()
            daily = response_json.get("daily")
            units = response_json.get("daily_units")

            daily_temperature_2m_max = daily.get("temperature_2m_max")[0]
            daily_temperature_2m_min = daily.get("temperature_2m_min")[0]

            daily_sunrise = daily.get("sunrise")[0]
            daily_sunrise_time = datetime.fromisoformat(daily_sunrise).strftime("%H:%M")

            daily_sunset = daily.get("sunset")[0]
            daily_sunset_time = datetime.fromisoformat(daily_sunset).strftime("%H:%M")

            daily_daylight_duration: float = float(daily.get("daylight_duration")[0]) / 60 / 60
            daily_uv_index_max = daily.get("uv_index_max")[0]

            daily_precipitation_sum: float = daily.get("precipitation_sum")[0]
            daily_precipitation_probability_max: int = daily.get("precipitation_probability_max")[0]

            daily_wind_speed_10m_max: float = daily.get("wind_speed_10m_max")[0]
            daily_wind_direction_10m_dominant: int = daily.get("wind_direction_10m_dominant")[0]

            self._pages.append(f"Sunrise: {daily_sunrise_time}\nSunset: {daily_sunset_time}")
            self._pages.append(
                f"Temperature\n[ {daily_temperature_2m_min} <---> {daily_temperature_2m_max}{units.get('temperature_2m_min')} ]"
            )
            self._pages.append(
                f"{daily_daylight_duration:.1f} hours daylight\nUV index: {daily_uv_index_max}"
            )
            self._pages.append(
                f"Precipitation\n{daily_precipitation_sum}{units.get('precipitation_sum')} "
                f"({daily_precipitation_probability_max}{units.get('precipitation_probability_max')} chance)"
            )
            self._pages.append(
                f"Wind speed\n{daily_wind_speed_10m_max} {units.get('wind_speed_10m_max')} "
                f"({self._degreesToCardinal(daily_wind_direction_10m_dominant)})"
            )

        if self.has_next:
            return self.next()
        return None

    def _degreesToCardinal(self, d: float) -> str:
        """
        Converts wind direction in degrees to cardinal direction.

        Args:
            d (float): The wind direction in degrees.

        Returns:
            str: The wind direction in cardinal direction.
        """
        dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        ix = round(d / (360. / len(dirs)))
        return dirs[ix % len(dirs)]