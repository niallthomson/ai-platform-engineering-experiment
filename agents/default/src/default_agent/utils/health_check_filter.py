import logging


class HealthCheckFilter(logging.Filter):
    """Logging filter that excludes health check and ping endpoint messages.
    
    Prevents log noise from health check endpoints by filtering out log records
    containing '/health' or '/ping' paths.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out log records containing health check or ping endpoints.
        
        Args:
            record: The log record to evaluate.
            
        Returns:
            False if the message contains '/health' or '/ping', True otherwise.
        """
        return record.getMessage().find("/health") == -1 and record.getMessage().find("/ping") == -1
