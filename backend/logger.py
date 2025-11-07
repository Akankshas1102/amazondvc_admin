import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from threading import Lock

class StreamToLogger:
    """
    Redirects stdout/stderr (like print statements) into the logger.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''  # Buffer for incomplete lines

    def isatty(self):
        return False

    def write(self, buf):
        """
        Handles 'write' calls from print() or errors.
        Buffers until newline, then logs the line.
        """
        self.linebuf += buf
        if '\n' in self.linebuf:
            lines = self.linebuf.split('\n')
            for line in lines[:-1]:
                message = line.strip()
                if message:
                    self.logger.log(self.log_level, message)
            self.linebuf = lines[-1]

    def flush(self):
        """
        Logs any remaining partial line when flushed.
        """
        message = self.linebuf.strip()
        if message:
            self.logger.log(self.log_level, message)
        self.linebuf = ''


# Global lock for thread-safe logging
_log_lock = Lock()


def get_logger(name):
    """
    Creates and returns a thread-safe logger that logs to both console and file.
    The log file is stored under backend/logs/app.log.
    """
    logger = logging.getLogger(name)

    if not logger.hasHandlers():
        # ✅ Ensure logs directory exists
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)

        # ✅ Use correct path for log file
        log_file = os.path.join(log_dir, "app.log")

        # ✅ File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            delay=True,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # ✅ Console handler for live logs
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # ✅ Wrap handler emit with a thread-safe lock
        class ThreadSafeHandler(logging.Handler):
            def emit(self, record):
                with _log_lock:
                    file_handler.emit(record)

        safe_handler = ThreadSafeHandler()
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        logger.setLevel(logging.DEBUG)

    return logger


def redirect_prints_to_logging(logger):
    """
    Redirects print() and uncaught exceptions to the provided logger.
    """
    stdout_logger = StreamToLogger(logger, log_level=logging.INFO)
    sys.stdout = stdout_logger

    stderr_logger = StreamToLogger(logger, log_level=logging.ERROR)
    sys.stderr = stderr_logger
