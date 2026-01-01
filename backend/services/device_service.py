"""
Device Service - FIXED VERSION
===============================
Handles ProEvent data retrieval with correct terminology.

TERMINOLOGY:
- ProEvents (not "devices") - these are reactive event triggers
- Reactive State: 0 = ARMED/REACTIVE (responds to events)
- Non-Reactive State: 1 = DISARMED/NON-REACTIVE (ignores events)
"""

from logger import get_logger
from services import proserver_service

logger = get_logger(__name__)


def get_distinct_buildings() -> list[dict]:
    """
    Fetches list of distinct buildings from the ProServer database.
    
    Returns:
        list[dict]: Buildings with fields:
            - id: Building ID
            - name: Building name
    """
    try:
        logger.debug("Fetching distinct buildings from database...")
        buildings = proserver_service.get_all_distinct_buildings_from_db()
        logger.info(f"✅ Retrieved {len(buildings)} distinct buildings")
        return buildings
    except Exception as e:
        logger.error(f"❌ Error getting distinct buildings: {e}")
        return []


def get_devices(building_id: int, search: str | None = None, limit: int = 1000, offset: int = 0) -> list[dict]:
    """
    Fetches ProEvents for a specific building from ProServer database.
    
    Note: Function name kept as 'get_devices' for backward compatibility,
    but these are ProEvents, not physical devices.
    
    Args:
        building_id: Building ID
        search: Optional search filter (not currently implemented)
        limit: Maximum number of results
        offset: Offset for pagination (not currently implemented)
    
    Returns:
        list[dict]: ProEvents with fields:
            - id: ProEvent ID (ProEvent_PRK)
            - name: ProEvent alias (pevAlias_TXT)
            - building_id: Building ID
            - reactive_state: 0 = ARMED/REACTIVE, 1 = DISARMED/NON-REACTIVE
    """
    try:
        logger.debug(f"[Building {building_id}] Fetching ProEvents from database...")
        
        # Fetch ProEvents from ProServer database
        proevents = proserver_service.get_proevents_for_building_from_db(building_id)
        
        if not proevents:
            logger.warning(f"[Building {building_id}] No ProEvents found in database")
            return []
        
        # Transform to expected format with correct field names
        proevent_list = [
            {
                "id": p["id"],
                "name": p["name"],
                "building_id": building_id,
                "reactive_state": p["state"]  # 0 = REACTIVE/ARMED, 1 = NON-REACTIVE/DISARMED
            }
            for p in proevents
        ]
        
        logger.info(f"✅ [Building {building_id}] Retrieved {len(proevent_list)} ProEvents")
        
        # TODO: Implement search/limit/offset filtering if needed
        # For now, returning all results
        
        return proevent_list
        
    except Exception as e:
        logger.error(f"❌ Error getting ProEvents for building {building_id}: {e}")
        return []