import logging
import os
import glob
import time
from logging.handlers import TimedRotatingFileHandler

class LevelFilter(logging.Filter):
    def __init__(self, level):
        super().__init__()
        self.level = level
    def filter(self, record):
        return record.levelno == self.level



# Use TimedRotatingFileHandler for time-based rotation and compression
class FlushTimedRotatingFileHandler(TimedRotatingFileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()
    def doRollover(self):
        super().doRollover()
        # Compress the most recent rotated log file in a separate thread to avoid blocking
        import shutil
        import threading
        def compress_logs():
            if self.backupCount > 0:
                log_dir, base = os.path.split(self.baseFilename)
                rotated_files = sorted(glob.glob(f"{self.baseFilename}.*"), reverse=True)
                for f in rotated_files[:self.backupCount]:
                    if not f.endswith('.gz') and os.path.isfile(f):
                        try:
                            shutil.make_archive(f, 'gztar', root_dir=log_dir, base_dir=os.path.basename(f))
                            os.remove(f)
                        except Exception:
                            pass # Ignore errors during compression
        threading.Thread(target=compress_logs).start()

_LOGGER = None

def get_logger(level='debug'):
    global _LOGGER
    if _LOGGER:
        return _LOGGER

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    main_log_file = os.path.join(log_dir, 'daly_bms.log')
    info_log_file = os.path.join(log_dir, 'daly_bms.info.log')
    warning_log_file = os.path.join(log_dir, 'daly_bms.warning.log')
    error_log_file = os.path.join(log_dir, 'daly_bms.error.log')

    logger = logging.getLogger('daly_bms')
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()



    # Log rotation settings
    when = 'midnight'  # Rotate at midnight
    interval = 1
    backup_count = 30  # Keep 30 days of logs
    retention_days = 30

    # Info-level log file
    fh_info = FlushTimedRotatingFileHandler(info_log_file, when=when, interval=interval, backupCount=backup_count, delay=False, encoding='utf-8')
    fh_info.setLevel(logging.INFO)
    fh_info.addFilter(LevelFilter(logging.INFO))
    fh_info.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(fh_info)

    fh_all = FlushTimedRotatingFileHandler(main_log_file, when=when, interval=interval, backupCount=backup_count, delay=False, encoding='utf-8')
    fh_all.setLevel(logging.INFO)
    fh_all.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(fh_all)

    fh_warn = FlushTimedRotatingFileHandler(warning_log_file, when=when, interval=interval, backupCount=backup_count, delay=False, encoding='utf-8')
    fh_warn.setLevel(logging.WARNING)
    fh_warn.addFilter(LevelFilter(logging.WARNING))
    fh_warn.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(fh_warn)

    fh_err = FlushTimedRotatingFileHandler(error_log_file, when=when, interval=interval, backupCount=backup_count, delay=False, encoding='utf-8')
    fh_err.setLevel(logging.ERROR)
    fh_err.addFilter(LevelFilter(logging.ERROR))
    fh_err.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(fh_err)

    # Log retention: delete logs older than retention_days
    now = time.time()
    for log_file in [main_log_file, info_log_file, warning_log_file, error_log_file]:
        for f in glob.glob(f"{log_file}*"):
            if os.path.isfile(f) and (now - os.path.getmtime(f)) > (retention_days * 86400):
                os.remove(f)

    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(sh)

    logger.propagate = False
    _LOGGER = logger
    return logger