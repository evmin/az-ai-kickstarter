import json

from typing import Annotated, TypedDict
from semantic_kernel.functions import kernel_function
    
class Weather:
    """ 
    The class acts as an facade for the weather operations.
    """
    
    class WeatherResponse(TypedDict):
        city: str
        conditions: str
        temperature: int
        humidity: int
        wind_speed: int
    
    @kernel_function(
        name="get_current_weather",
        description="Returns current weather data for a given city. Temperature is in Celcius, humidity in percentage and wind speed in km/h.")
    def get_current_weather(self,
                            city: Annotated[str,"The city to get the weather for"]) -> Annotated[WeatherResponse, 
                                                                                                 "The current weather conditions as a JSON object:  {\"city\": city, \"conditions\": \"sunny\", \"temperature\": 20, \"humidity\": 20, \"wind_speed\": 20}"]:
        response = { 
                    "city": city, 
                    "conditions": "foggy",
                    "temperature": 25, 
                    "humidity": 90, 
                    "wind_speed": 10 
                    }
        return json.dumps(response) if response else None
