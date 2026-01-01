"""
Scheduler Service - FIXED VERSION
==================================
Runs periodic background tasks with correct logging and terminology.

TERMINOLOGY:
- ProEvents: Reactive event triggers (not "devices")
- Reactive State: 0 = ARMED/REACTIVE
- Non-Reactive State: 1 = DISARMED/NON-REACTIVE
- Panel States: AreaArmingStates.4 = ARMED, AreaArmingStates.2 = DISARMED
"""

import schedule
import time
import threading
from logger import get_logger
from services import proevent_service
import traceback

logger = get_logger(__name__)


def scheduled_job():
    """
    Main scheduler job that runs every minute.
    
    Phase 1: Check scheduled times and send alerts if panel is disarmed
    Phase 2: Monitor panel state changes and update ProEvent reactive states
    """
    logger.info("="*70)
    logger.info("🔄 SCHEDULER: Starting scheduled job execution")
    logger.info("="*70)

    try:
        # Phase 1: Scheduled Time Checks
        logger.info("📅 PHASE 1: Checking scheduled times and sending alerts if needed...")
        proevent_service.check_and_manage_scheduled_states()
        logger.info("✅ PHASE 1: Completed successfully")
        logger.info("-"*70)

        # Phase 2: Panel State Monitoring and ProEvent Management
        logger.info("🔍 PHASE 2: Monitoring panel state changes and managing ProEvents...")
        proevent_service.manage_proevents_on_panel_state_change()
        logger.info("✅ PHASE 2: Completed successfully")
        
        logger.info("="*70)
        logger.info("✅ SCHEDULER: Scheduled job completed successfully")
        logger.info("="*70)
        
    except Exception as e:
        logger.error("="*70)
        logger.error(f"❌ SCHEDULER: Error in scheduled job: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error("="*70)


def run_scheduler():
    """
    Runs the scheduler loop in a separate thread.
    Executes scheduled_job every 1 minute.
    """
    logger.info("🚀 SCHEDULER: Thread started")
    schedule.every(1).minutes.do(scheduled_job)
    logger.info("⏰ SCHEDULER: Job registered to run every 1 minute")

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"❌ SCHEDULER: Error in scheduler loop: {e}", exc_info=True)
            time.sleep(5)  # Wait before retrying


def start_scheduler():
    """
    Starts the scheduler in a background daemon thread.
    """
    logger.info("🔧 SCHEDULER: Starting scheduler in background thread...")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True, name="SchedulerThread")
    scheduler_thread.start()
    logger.info("✅ SCHEDULER: Background thread started successfully")