"""
ProServer Service - FIXED VERSION
==================================
Handles communication with the ProServer database and TCP/IP notifications.

TERMINOLOGY CLARIFICATION:
- ProEvent Reactive State: 0 = ARMED/REACTIVE (responds to events)
- ProEvent Non-Reactive State: 1 = DISARMED/NON-REACTIVE (does not respond to events)
- Panel State: AreaArmingStates.4 = ARMED, AreaArmingStates.2 = DISARMED
"""

import socket
from sqlalchemy import text
from sqlalchemy.orm import Session
from logger import get_logger
from config import get_db_connection, engine, PROSERVER_IP, PROSERVER_PORT
from query_config import get_query

logger = get_logger(__name__)


# --- TCP/IP NOTIFICATION FUNCTIONS ---

def send_proserver_notification(building_name: str):
    """
    Sends a unified notification to the ProServer.
    Format: axe,{building_name}_Is_Armed@
    """
    message = f"axe,{building_name}_Is_Armed@"
    logger.info(f"Sending notification to ProServer: {message}")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((PROSERVER_IP, PROSERVER_PORT))
            s.sendall(message.encode())
            logger.info(f"✅ Notification sent successfully: {message}")
    except Exception as e:
        logger.error(f"❌ Failed to send notification to ProServer: {e}")


def send_armed_axe_message(building_id: int):
    """
    Checks if a building panel is in ARMED state (AreaArmingStates.4).
    If yes, sends armed AXE alert to ProServer.
    """
    query_sql = get_query('building_name')
    
    if not query_sql:
        logger.error("❌ Query 'building_name' not found in configuration!")
        return
    
    sql = text(query_sql)
    building_name = None
    
    try:
        with get_db_connection() as db:
            result = db.execute(sql, {"building_id": building_id})
            row = result.fetchone()
            
            if row:
                building_name = row.bldBuildingName_TXT

    except Exception as e:
        logger.error(f"❌ Failed to query building name for AXE message: {e}")
        return

    # Only send if building is in ARMED state (AreaArmingStates.4)
    if building_name:
        message = f"axe,{building_name}_Is_Armed@"
        logger.info(f"[Building {building_id}] Panel is ARMED (AreaArmingStates.4). Sending: {message}")
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((PROSERVER_IP, PROSERVER_PORT))
                s.sendall(message.encode())
                logger.info(f"✅ Armed AXE notification sent: {message}")
        except Exception as e:
            logger.error(f"❌ Failed to send armed AXE notification: {e}")
    else:
        logger.debug(f"[Building {building_id}] Panel not in ARMED state (AreaArmingStates.4). No message sent.")


def send_disarmed_axe_message(building_id: int):
    """
    Sends a 'disarmed' AXE alert to ProServer at schedule start time.
    Message format: axe,<building_name>_Is_Disarmed@
    """
    try:
        with get_db_connection() as session:
            result = session.execute(
                text("SELECT bldBuildingName_TXT FROM Building_TBL WHERE Building_PRK = :building_id"),
                {"building_id": building_id}
            )
            row = result.fetchone()

        if not row or not row[0]:
            logger.warning(f"[Building {building_id}] Building name not found for disarmed alert.")
            return

        building_name = row[0]
        message = f"axe,{building_name}_Is_Disarmed@"
        logger.info(f"[Building {building_id}] Panel DISARMED (AreaArmingStates.2). Sending: {message}")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((PROSERVER_IP, PROSERVER_PORT))
            s.sendall(message.encode())
            logger.info(f"✅ Disarmed AXE notification sent: {message}")

    except Exception as e:
        logger.error(f"❌ Failed to send disarmed AXE notification: {e}")


# --- DATABASE QUERY FUNCTIONS ---

def get_proevents_for_building_from_db(building_id: int) -> list[dict]:
    """
    Fetches all ProEvents for a building from ProServer database.
    
    Returns:
        list[dict]: ProEvents with fields:
            - id: ProEvent_PRK
            - state: pevReactive_FRK (0=reactive/armed, 1=non-reactive/disarmed)
            - name: pevAlias_TXT
            - building_name: bldBuildingName_TXT
    """
    logger.info(f"[Building {building_id}] Fetching ProEvents from ProServer database...")
    
    query_sql = get_query('proevents')
    
    if not query_sql:
        logger.error("❌ Query 'proevents' not found in configuration!")
        return []
    
    sql = text(query_sql)
    results = []

    try:
        with get_db_connection() as db:
            result = db.execute(sql, {"building_id": building_id})
            rows = result.fetchall()
            
            if not rows:
                logger.warning(f"[Building {building_id}] No ProEvents found in ProEvent_TBL")
                return []
                
            for row in rows:
                # pevReactive_FRK: 0 = REACTIVE (armed), 1 = NON-REACTIVE (disarmed)
                results.append({
                    "id": row.ProEvent_PRK,
                    "state": row.pevReactive_FRK,
                    "name": row.pevAlias_TXT,
                    "building_name": row.bldBuildingName_TXT
                })
            
            db.commit()
        
        logger.info(f"✅ [Building {building_id}] Fetched {len(results)} ProEvents from database")
        return results
        
    except Exception as e:
        logger.error(f"❌ Failed to query ProEvents from database: {e}")
        raise


def set_proevent_reactive_state_bulk(target_states: list[dict]) -> bool:
    """
    Updates ProEvent reactive states in bulk in ProServer database.
    
    Args:
        target_states: List of {"id": proevent_id, "state": reactive_state}
                      where state: 0 = REACTIVE (armed), 1 = NON-REACTIVE (disarmed)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not target_states:
        logger.debug("No target states provided to set_proevent_reactive_state_bulk. Skipping.")
        return True

    reactive_count = sum(1 for s in target_states if s['state'] == 0)
    non_reactive_count = len(target_states) - reactive_count
    
    logger.info(f"Updating {len(target_states)} ProEvent states in ProServer database: "
               f"{reactive_count} to REACTIVE (0), {non_reactive_count} to NON-REACTIVE (1)")
    
    sql = text("""
        UPDATE ProEvent_TBL 
        SET pevReactive_FRK = :state 
        WHERE ProEvent_PRK = :proevent_id
    """)
    
    data_to_update = [
        {"state": item['state'], "proevent_id": item['id']} 
        for item in target_states
    ]
    
    try:
        with get_db_connection() as db:
            db.execute(sql, data_to_update)
            db.commit()
            
        logger.info(f"✅ Successfully updated {len(data_to_update)} ProEvent states in ProServer database")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to bulk update ProEvent states in database: {e}")
        return False


def get_all_live_building_arm_states() -> dict:
    """
    Returns current panel arm/disarm state for all buildings.
    
    Panel States:
    - AreaArmingStates.4 = ARMED
    - AreaArmingStates.2 = DISARMED
    - All other states = ARMED (default)
    
    Returns:
        dict: {building_id: is_armed} where is_armed is True for ARMED, False for DISARMED
    """
    try:
        logger.debug("Fetching all building panel states from ProServer database...")

        query_sql = get_query('panel_devices')
        
        if not query_sql:
            logger.error("❌ Query 'panel_devices' not found in configuration!")
            return {}

        with Session(engine) as session:
            query = text(query_sql)
            rows = session.execute(query).fetchall()

        result = {}
        armed_count = 0
        disarmed_count = 0
        
        for building_id, state_txt in rows:
            if not building_id:
                continue

            state_str = (state_txt or "").strip()

            # AreaArmingStates.2 = DISARMED, all others = ARMED
            if "AreaArmingStates.2" in state_str:
                is_armed = False
                disarmed_count += 1
            else:
                is_armed = True
                armed_count += 1

            result[int(building_id)] = is_armed

        logger.info(f"✅ Fetched panel states for {len(result)} buildings: "
                   f"{armed_count} ARMED (AreaArmingStates.4), "
                   f"{disarmed_count} DISARMED (AreaArmingStates.2)")
        return result

    except Exception as e:
        logger.error(f"❌ Failed to fetch building panel states: {e}")
        return {}


def get_all_distinct_buildings_from_db() -> list[dict]:
    """
    Fetches list of all unique buildings from Building_TBL.
    
    Returns:
        list[dict]: Buildings with fields:
            - id: Building_PRK
            - name: bldBuildingName_TXT
    """
    logger.info("Fetching all distinct buildings from ProServer database...")
    
    query_sql = get_query('buildings')
    
    if not query_sql:
        logger.error("❌ Query 'buildings' not found in configuration!")
        return []
    
    sql = text(query_sql)
    results = []

    try:
        with get_db_connection() as db:
            result = db.execute(sql)
            rows = result.fetchall()
            
            if not rows:
                logger.warning("No buildings found in Building_TBL.")
                return []
                
            for row in rows:
                results.append({
                    "id": row.Building_PRK,
                    "name": row.bldBuildingName_TXT
                })
            
            db.commit()
        
        logger.info(f"✅ Fetched {len(results)} distinct buildings from database")
        return results
        
    except Exception as e:
        logger.error(f"❌ Failed to query buildings from database: {e}")
        return []