import logging
from strands.experimental.tools import ToolProvider
from strands.types.tools import AgentTool
from typing import Sequence, Any

logger = logging.getLogger(__name__)

class ForgivingToolProvider(ToolProvider):
    """Wrapper around ToolProvider that gracefully handles tool loading failures.
    
    Prevents agent instantiation failures when tools (especially MCP tools) are unavailable.
    Returns an empty tool list instead of propagating exceptions during load_tools().
    """
    
    def __init__(self, inner: ToolProvider) -> None:
        """Initialize with an inner ToolProvider to wrap.
        
        Args:
            inner: The ToolProvider instance to wrap
        """
        super().__init__()
        self.inner = inner

    async def load_tools(self, **kwargs: Any) -> Sequence["AgentTool"]:
        """Load tools from the inner provider, returning empty list on failure.
        
        Args:
            **kwargs: Arguments passed to the inner provider's load_tools method
            
        Returns:
            Sequence of AgentTool instances, or empty list if loading fails
        """
        try:
            return await self.inner.load_tools(**kwargs)
        except Exception as e:
            logger.error(f"Failed to load tools: {e}")
            return []

    def add_consumer(self, consumer_id: Any, **kwargs: Any) -> None:
        self.inner.add_consumer(consumer_id, **kwargs)

    def remove_consumer(self, consumer_id: Any, **kwargs: Any) -> None:
        self.inner.remove_consumer(consumer_id, **kwargs)