# backend/services/scheduler_service.py

import schedule
import time
import threading
from logger import get_logger
from services import proevent_service
import traceback  # Import the traceback module

logger = get_logger(__name__)

def scheduled_job():
    """
    Main scheduler job that runs every minute.
    Phase 1: Check if building panel is disarmed at start time -> Send AXE alert.
    Phase 2: Detect panel ARM/DISARM transitions -> Toggle ProEvent reactive states.
    """
    from services import proevent_service
    import logging

    logging.info("Scheduler running: Managing scheduled states...")

    # Phase 1 – Scheduled AXE alert
    proevent_service.check_and_manage_scheduled_states()

    # Phase 2 – Continuous monitoring and ProEvent toggling
    proevent_service.manage_proevents_on_panel_state_change()


def run_scheduler():
    """
    Runs the scheduler in a separate thread.
    """
    schedule.every(1).minutes.do(scheduled_job)

    while True:
        schedule.run_pending()
        time.sleep(1)

def start_scheduler():
    """
    Starts the scheduler in a background thread.
    """
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    logger.info("Scheduler started.")