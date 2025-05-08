import datetime
import logging
import os
from datetime import date
from cachetools import cached, TTLCache

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

import dateutil
import requests
from dateutil.parser import parse

from src.train_bot.utils.date_utils import next_weekday
from train_stations import TRAIN_STATIONS
from load_env import init_env

# Initialize environment variables
init_env()

RAIL_API_ENDPOINT = 'https://israelrail.azurefd.net/rjpa-prod/api/v1/timetable/searchTrainLuzForDateTime?fromStation={from_station}&toStation={to_station}&date' \
                    '={day}&hour={hour}&scheduleType=1&systemType=1&language"id"="hebrew"'
RAIL_API_KEY = os.environ['RAIL_TOKEN']

# Initialize cache with 10 second TTL
timetable_cache = TTLCache(maxsize=100, ttl=10)

def get_cache_stats():
    """Get statistics about the cache usage."""
    return {
        "size": timetable_cache.currsize,
        "maxsize": timetable_cache.maxsize,
        "ttl": timetable_cache.ttl,
        "hits": getattr(timetable_cache, "hits", 0),
        "misses": getattr(timetable_cache, "misses", 0)
    }


def get_train_times(departure_station, arrival_station, day_num=None):
    logger.info(f"Getting train times from {departure_station} to {arrival_station} for day_num: {day_num}")
    try:
        # Calculate the date based on day number
        day = date.today() if day_num is None else next_weekday(date.today(), day_num)
        logger.debug(f"Calculated date for query: {day}")
        
        # Hard-coded hour for API call - might need a different approach
        current_hour = '16:30'
        logger.debug(f"Using fixed hour for API query: {current_hour}")
        
        # Get the timetable from the API
        logger.info(f"Calling timetable API for {departure_station}->{arrival_station} on {day}")
        res = get_timetable(departure_station, arrival_station, day, current_hour)
        
        # Validate API response
        if 'result' not in res or 'travels' not in res['result']:
            logger.error(f"Invalid API response structure in get_train_times: {res}")
            raise Exception(f"Invalid API response: missing 'result' or 'travels' keys")
        
        # Process and transform the data
        logger.debug(f"Processing {len(res['result']['travels'])} travel options from API")
        train_times = []
        
        for travel in res['result']['travels']:
            try:
                departure_time = travel['departureTime']
                arrival_time = travel['arrivalTime']
                switches = len(travel['trains']) - 1
                train_times.append((departure_time, arrival_time, switches))
            except KeyError as ke:
                logger.warning(f"Skipping travel option due to missing key: {str(ke)}")
                continue
        
        logger.info(f"Found {len(train_times)} trains for route {departure_station} to {arrival_station}")
        return train_times
        
    except Exception as e:
        logger.error(f"Error in get_train_times: {str(e)}", exc_info=e)
        raise Exception(f"Failed to get train times: {str(e)}")


@cached(cache=timetable_cache)
def get_timetable(departure_station, arrival_station, day, hour):
    """Get timetable from API with caching (10 second TTL)."""
    # Log that this is a cache miss, since we're executing the function
    logger.debug(f"Cache miss for timetable: {departure_station}->{arrival_station} on {day} at {hour}")
    print("CACHE MISS *****************")
    try:
        uri = RAIL_API_ENDPOINT.format(from_station=departure_station, to_station=arrival_station, day=day,
                                    hour=hour)
        logger.info(f"Making API request to: {uri.split('?')[0]} with params for stations {departure_station}->{arrival_station}")
        
        headers = {
            "Accept": "application/json",
            "Ocp-Apim-Subscription-Key": RAIL_API_KEY,
        }
        
        logger.debug(f"API request headers: {headers}")
        response = requests.get(uri, headers=headers)
        
        status_code = response.status_code
        logger.debug(f"API response status code: {status_code}")
        
        if status_code != 200:
            logger.error(f"API error response: {response.text}")
            raise Exception(f"API returned error status code: {status_code}")
            
        # Try to parse JSON response
        try:
            res = response.json()
            logger.debug(f"API response successfully parsed as JSON")
            return res
        except ValueError as json_error:
            logger.error(f"Failed to parse API response as JSON: {str(json_error)}")
            logger.error(f"API raw response: {response.text[:500]}...")
            raise Exception(f"Invalid JSON response from API: {str(json_error)}")
            
    except requests.exceptions.RequestException as req_ex:
        logger.error(f"Request exception when calling API: {str(req_ex)}", exc_info=req_ex)
        raise Exception(f"Network error when calling train API: {str(req_ex)}")
    except Exception as ex:
        logger.error(f"Unexpected error in get_timetable: {str(ex)}", exc_info=ex)
        raise


class TrainTimes:
    def __init__(self, original_departure, original_arrival, delay_in_minutes, switch_stations):
        self.original_departure = original_departure
        self.original_arrival = original_arrival
        self.delay_in_minutes = delay_in_minutes
        self.switch_stations = switch_stations

    def get_updated_departure(self):
        return parse(self.original_departure) + datetime.timedelta(minutes=self.delay_in_minutes)

    def get_updated_arrival(self):
        return parse(self.original_arrival) + datetime.timedelta(minutes=self.delay_in_minutes)


class TrainNotFoundError(BaseException):
    pass


def get_delay_from_api(from_station, to_station, hour) -> TrainTimes:
    logger.info("Checking for delays for train from {} to {} at {} today".format(from_station, to_station, hour))
    try:
        day = dateutil.parser.isoparse(hour).date()
        logger.debug(f"Parsed date: {day} from hour: {hour}")
        
        # Format in specific train '2023-09-17T21:55:00'
        # Format in sub:
        logger.debug(f"Calling get_timetable API for from_station: {from_station}, to_station: {to_station}, day: {day}")
        timetable = get_timetable(from_station, to_station, day, '07:00')
        
        # Log timetable API response structure
        logger.debug(f"Timetable API response keys: {list(timetable.keys())}")
        if 'result' in timetable:
            logger.debug(f"Result keys: {list(timetable['result'].keys())}")
            if 'travels' in timetable['result']:
                logger.debug(f"Found {len(timetable['result']['travels'])} travel options")
        
        # Check if we got a valid response with travels
        if 'result' not in timetable or 'travels' not in timetable['result']:
            logger.error(f"Invalid API response structure: {timetable}")
            raise Exception(f"Invalid API response: missing expected 'result' or 'travels' keys")
        
        for travel in timetable['result']['travels']:
            scheduled_departure = travel['departureTime']
            logger.debug(f"Comparing scheduled departure: {scheduled_departure} with requested hour: {hour}")
            
            if scheduled_departure != hour:
                continue
                
            logger.debug(f"Found matching departure time. Extracting train details.")
            switch_stations = extract_switch_stations(travel['trains'])
            
            # Check if 'trains' exists and has elements
            if not travel.get('trains'):
                logger.error(f"No 'trains' data in travel: {travel}")
                raise Exception("No train data found in the travel information")
            
            train_position = travel['trains'][0].get('trainPosition')
            original_departure = travel['departureTime']
            original_arrival = travel['arrivalTime']

            if train_position is None:
                logger.info(f"No position info for train departing at {scheduled_departure}, it is probably on time")
                return TrainTimes(original_departure, original_arrival, 0, switch_stations)

            # Check if calcDiffMinutes exists in train_position
            if 'calcDiffMinutes' not in train_position:
                logger.warning(f"No delay information (calcDiffMinutes) in train_position: {train_position}")
                return TrainTimes(original_departure, original_arrival, 0, switch_stations)
                
            train_delay = train_position['calcDiffMinutes']
            logger.info(f"Found train with delay of {train_delay} minutes")

            train_times = TrainTimes(hour, original_arrival, train_delay, switch_stations)
            logger.debug('Original Departure: {origDep}, delay: {delay}, updated departure: {updated_departure}'.format(
                origDep=scheduled_departure, delay=train_delay, updated_departure=train_times.get_updated_departure()))

            return train_times
            
        # No matching train found
        logger.warning(f"No train found at {hour} in the timetable response")
        raise TrainNotFoundError("Train not found in API response")
        
    except TrainNotFoundError:
        logger.warning(f"Train not found for {from_station} to {to_station} at {hour}")
        raise
    except Exception as e:
        logger.error(f"Error in get_delay_from_api: {str(e)}", exc_info=e)
        raise Exception(f"API error while getting train delay: {str(e)}")


def extract_switch_stations(trains):
    if len(trains) == 1:
        return None
    return [station_id_to_name(train['destinationStation']) for train in trains[:-1]]


def station_id_to_name(station_id, escape=True):
    raw_name = next(filter(lambda s: s['id'] == str(station_id), TRAIN_STATIONS))['english']
    if escape:
        return raw_name.replace('-', '\-')
    return raw_name
