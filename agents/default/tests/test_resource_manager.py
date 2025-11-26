import pytest
from unittest.mock import AsyncMock
from default_agent.utils.resource_manager import ResourceManager


@pytest.mark.anyio
async def test_register_resource():
    manager = ResourceManager()
    cleanup = AsyncMock()
    
    manager.register("test_resource", cleanup)
    
    assert len(manager._resources) == 1
    assert manager._resources[0][0] == "test_resource"


@pytest.mark.anyio
async def test_cleanup_all_calls_registered_resources():
    manager = ResourceManager()
    cleanup1 = AsyncMock()
    cleanup2 = AsyncMock()
    
    manager.register("resource1", cleanup1)
    manager.register("resource2", cleanup2)
    
    await manager.cleanup_all()
    
    cleanup1.assert_awaited_once()
    cleanup2.assert_awaited_once()


@pytest.mark.anyio
async def test_cleanup_all_reverse_order():
    manager = ResourceManager()
    call_order = []
    
    async def cleanup1():
        call_order.append("resource1")
    
    async def cleanup2():
        call_order.append("resource2")
    
    manager.register("resource1", cleanup1)
    manager.register("resource2", cleanup2)
    
    await manager.cleanup_all()
    
    assert call_order == ["resource2", "resource1"]


@pytest.mark.anyio
async def test_cleanup_all_handles_exceptions():
    manager = ResourceManager()
    cleanup1 = AsyncMock(side_effect=Exception("cleanup failed"))
    cleanup2 = AsyncMock()
    
    manager.register("resource1", cleanup1)
    manager.register("resource2", cleanup2)
    
    await manager.cleanup_all()
    
    cleanup1.assert_awaited_once()
    cleanup2.assert_awaited_once()
