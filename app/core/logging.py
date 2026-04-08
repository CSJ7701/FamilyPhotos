import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logger = logging.getLogger("FamilyHub")
logger.setLevel(logging.INFO)

# Create the Rotating File Handler
# maxBytes=5*1024*1024 (5MB)
# backupCount=5 (Keep app.log.1 through app.log.5)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5*1024*1024,
    backupCount=5
)

formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
