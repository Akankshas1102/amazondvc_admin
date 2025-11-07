# backend/services/device_service.py

from logger import get_logger
from services import proserver_service # Import the real service

logger = get_logger(__name__)

def get_distinct_buildings() -> list[dict]:
    """
    Fetches a list of distinct buildings from the ProServer DB.
    """
    try:
        # Call the new function we'll add to proserver_service
        buildings = proserver_service.get_all_distinct_buildings_from_db()
        return buildings
    except Exception as e:
        logger.error(f"Error getting distinct buildings: {e}")
        return []

def get_devices(building_id: int, search: str | None = None, limit: int = 1000, offset: int = 0) -> list[dict]:
    """
    Fetches devices for a specific building from the ProServer DB, retaining the state.
    
    FIX: The 'device_list' now includes the 'reactive_state' to avoid the error in proevent_service.
    """
    try:
        # This function gets the raw list from ProServer DB
        devices = proserver_service.get_proevents_for_building_from_db(building_id)
        
        # We now keep the necessary fields, including the state (which is 'state' from proserver_service)
        device_list = [
            # IMPORTANT: 'state' from proserver_service is the pevReactive_FRK (0 or 1)
            # Renamed 'state' to 'reactive_state' for consistency with proevent_service.
            {"id": d["id"], "name": d["name"], "building_id": building_id, "reactive_state": d["state"]}
            for d in devices
        ]
        
        # TODO: Implement search/limit/offset if needed
        return device_list
        
    except Exception as e:
        logger.error(f"Error getting devices for building {building_id}: {e}")
        return []