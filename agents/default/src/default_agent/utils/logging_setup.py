import logging
from uvicorn.config import LOGGING_CONFIG


def setup_logging():
    format_prefix = "%(levelname)s | %(name)s |"
    format = "{} %(message)s".format(format_prefix)

    logging.basicConfig(format=format, level=logging.INFO)

    LOGGING_CONFIG["formatters"]["default"]["fmt"] = format
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        '{} %(client_addr)s - "%(request_line)s" %(status_code)s'.format(format_prefix)
    )
