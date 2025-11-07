import socket
from sqlalchemy import text
from logger import get_logger
from sqlalchemy import text
from sqlalchemy.orm import Session
from config import engine


logger = get_logger(__name__)


logger = get_logger(__name__)
# Import the connection helper and settings from config
from config import get_db_connection, PROSERVER_IP, PROSERVER_PORT

# --- TCP/IP Functions (Unchanged) ---

def send_proserver_notification(building_name: str):
    """
    Sends a unified notification to the ProServer.
    Format: axe,{building_name}_{device_id}@
    """
    message = f"axe,{building_name}_Is_Armed@"
    logger.info(f"Attempting to send notification to ProServer: {message}")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((PROSERVER_IP, PROSERVER_PORT))
            s.sendall(message.encode())
    except Exception as e:
        logger.error(f"Failed to send notification to ProServer: {e}")




# def send_axe_message():
#     """
#     Sends a generic "axe" message when the panel is armed.
#     """
#     message = f"axe,{building_name}_{device_id}@"
#     logger.info(f"PANEL ARMED. Sending message to ProServer: {message}")
    
#     try:
#         with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#             s.connect((PROSERVER_IP, PROSERVER_PORT))
#             s.sendall(message.encode())
#     except Exception as e:
#         logger.error(f"Failed to send global armed notification to ProServer: {e}")

# --- UPDATED: DATABASE FUNCTIONS USING SQLALCHEMY ---

def send_armed_axe_message(building_id: int):
    """
    Checks if a specific building is in the 'AreaArmingStates.4' state.
    If it is, fetches the building name and sends the dynamic armed message.
    """
    
    # The new query you provided
    sql = text("""
        select bldBuildingName_TXT from Building_TBL 
        join Device_TBL on dvcBuilding_FRK = Building_PRK 
        where dvcCurrentState_TXT = 'AreaArmingStates.4' and dvcBuilding_FRK = :building_id
    """)
    
    building_name = None
    
    try:
        # Use the SQLAlchemy connection to run the query
        with get_db_connection() as db:
            result = db.execute(sql, {"building_id": building_id})
            row = result.fetchone() # We only expect one row
            
            if row:
                # Use the column name from your query
                building_name = row.bldBuildingName_TXT

    except Exception as e:
        logger.error(f"Failed to query for building name for Axe message: {e}")
        return # Don't proceed if DB query fails

    # Only send if the query returned a building name (i.e., state was 'AreaArmingStates.4')
    if building_name:
        # The new message format you specified
        message = f"axe,{building_name}_Is_Armed@"
        logger.info(f"Building {building_id} is 'AreaArmingStates.4'. Sending message: {message}")
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((PROSERVER_IP, PROSERVER_PORT))
                s.sendall(message.encode())
        except Exception as e:
            logger.error(f"Failed to send armed axe notification to ProServer: {e}")
    else:
        logger.info(f"Building {building_id} is not in 'AreaArmingStates.4'. No message sent.")

def get_proevents_for_building_from_db(building_id: int) -> list[dict]:
    """
    Connects to the ProServer DB and runs your query to get all
    devices, their IDs, their states, and the building name.
    """
    logger.info(f"Connecting to ProServer DB to get proevents for building {building_id}...")
    
    sql = text("""
        SELECT
            p.pevReactive_FRK,
            p.ProEvent_PRK,
            p.pevAlias_TXT,
            b.bldBuildingName_TXT
        FROM
            ProEvent_TBL AS p
        LEFT JOIN
            Building_TBL AS b ON p.pevBuilding_FRK = b.Building_PRK
        WHERE
            p.pevBuilding_FRK = :building_id;
    """)
    
    results = []

    try:
        with get_db_connection() as db:
            result = db.execute(sql, {"building_id": building_id})
            rows = result.fetchall()
            
            if not rows:
                logger.warning(f"No proevents found in ProEvent_TBL for building {building_id}")
                return []
                
            for row in rows:
                results.append({
                    "id": row.ProEvent_PRK,
                    "state": row.pevReactive_FRK,  # This is the 0 or 1
                    "name": row.pevAlias_TXT,
                    "building_name": row.bldBuildingName_TXT
                })
            
            db.commit()
        
        logger.info(f"Successfully fetched {len(results)} device states from DB for building {building_id}")
        return results
        
    except Exception as e:
        logger.error(f"Failed to query ProServer DB for proevents: {e}")
        raise

def set_proevent_reactive_state_bulk(target_states: list[dict]) -> bool:
    """
    Connects to the ProServer DB and updates device states in bulk.
    'target_states' is a list: [{'id': 1001, 'state': 0}, {'id': 1002, 'state': 1}, ...]
    """
    if not target_states:
        logger.info("No target states provided to set_proevent_reactive_state_bulk. Skipping.")
        return True

    logger.info(f"Connecting to ProServer DB to set {len(target_states)} device states...")
    
    sql = text("""
        UPDATE ProEvent_TBL 
        SET pevReactive_FRK = :state 
        WHERE ProEvent_PRK = :device_id
    """)
    
    # Format data for SQLAlchemy executemany
    data_to_update = [
        {"state": item['state'], "device_id": item['id']} 
        for item in target_states
    ]
    
    try:
        with get_db_connection() as db:
            db.execute(sql, data_to_update)
            db.commit()
            
        logger.info(f"Successfully updated {len(data_to_update)} device states in ProServer DB.")
        return True
        
    except Exception as e:
        logger.error(f"Failed to bulk update states in ProServer DB: {e}")
        return False
    


def get_all_live_building_arm_states():
    """
    Returns a dictionary of {building_id: bool}
      True  = ARMED
      False = DISARMED

    Each building has exactly one panel device (dvcDeviceType_FRK = 138).
    We read its dvcCurrentState_TXT and decide:
      - If AreaArmingStates.2 → DISARMED
      - Everything else → ARMED
    """
    try:
        logger.info("Connecting to ProServer DB to get all building panel states...")

        with Session(engine) as session:
            query = text("""
                SELECT dvcBuilding_FRK, dvcCurrentState_TXT
                FROM Device_TBL
                WHERE dvcDeviceType_FRK = 138
            """)
            rows = session.execute(query).fetchall()


        result = {}
        for building_id, state_txt in rows:
            if not building_id:
                continue

            state_str = (state_txt or "").strip()

            # 🔹 Only AreaArmingStates.2 is DISARMED; everything else = ARMED
            if "AreaArmingStates.2" in state_str:
                is_armed = False
            else:
                is_armed = True

            result[int(building_id)] = is_armed

        logger.info(f"Successfully fetched {len(result)} building panel states.")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch live building panel states: {e}")
        return {}
    
    
def get_all_distinct_buildings_from_db() -> list[dict]:
    """
    Fetches a list of all unique buildings from the Device_TBL.
    """
    logger.info("Connecting to ProServer DB to get distinct buildings...")
    
    sql = text("""
        select Building_PRK, bldBuildingName_TXT
        from
        Building_TBL
    """)
    
    results = []

    try:
        with get_db_connection() as db:
            result = db.execute(sql)
            rows = result.fetchall()
            
            if not rows:
                logger.warning("No buildings found in Device_TBL.")
                return []
                
            for row in rows:
                results.append({
                    "id": row.Building_PRK,
                    "name": row.bldBuildingName_TXT
                })
            
            db.commit()
        
        logger.info(f"Successfully fetched {len(results)} distinct buildings.")
        return results
        
    except Exception as e:
        logger.error(f"Failed to query ProServer DB for distinct buildings: {e}")
        return []
    
def send_disarmed_axe_message(building_id: int):
    """
    Sends a 'disarmed' AXE alert to ProServer at schedule start time.
    Message format: axe,<building_name>_Is_Disarmed@
    """
    try:
        # ✅ FIX: use text() for SQLAlchemy
        with get_db_connection() as session:
            result = session.execute(
                text("SELECT bldBuildingName_TXT FROM Building_TBL WHERE Building_PRK = :building_id"),
                {"building_id": building_id}
            )
            row = result.fetchone()

        if not row or not row[0]:
            logger.warning(f"Building {building_id}: name not found for disarmed alert.")
            return

        building_name = row[0]
        message = f"axe,{building_name}_Is_Disarmed@"
        logger.info(f"[Building {building_id}] Panel DISARMED. Sending message: {message}")

        # ✅ Send to ProServer socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((PROSERVER_IP, PROSERVER_PORT))
            s.sendall(message.encode())

    except Exception as e:
        logger.error(f"Failed to send disarmed AXE notification to ProServer: {e}")
