
import logging
from app.core.config import get_settings

def setup_logging():
    settings = get_settings()

    logging.basicConfig(
        level = settings.LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    logger = logging.getLogger("familyphotos")
    logger.setLevel(settings.LOG_LEVEL)

    logger.info("Logging initialized")
    return logger
