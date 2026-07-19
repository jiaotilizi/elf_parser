from enum import Enum


class ResourceType(str, Enum):
    """RTOS 资源类型枚举（统一使用复数形式）。
    
    所有插件应使用此枚举而非硬编码字符串，确保单复数一致。
    枚举值为复数形式，与 DataAdapter.DEFAULT_METADATA 的 key 对齐。
    """
    TASKS = 'tasks'
    MUTEXES = 'mutexes'
    SEMAPHORES = 'semaphores'
    QUEUES = 'queues'
    EVENTS = 'events'
    TIMERS = 'timers'
    BLOCK_POOLS = 'block_pools'
    BYTE_POOLS = 'byte_pools'
    
    # 模块插件资源类型
    TEST_POINTS = 'test_points'
    ASSERT_INFO = 'assert_info'


RESOURCE_TYPE_MAP = {
    # 兼容旧的单数形式（向后兼容）
    'task': ResourceType.TASKS,
    'mutex': ResourceType.MUTEXES,
    'semaphore': ResourceType.SEMAPHORES,
    'queue': ResourceType.QUEUES,
    'event': ResourceType.EVENTS,
    'timer': ResourceType.TIMERS,
    'block_pool': ResourceType.BLOCK_POOLS,
    'byte_pool': ResourceType.BYTE_POOLS,
    'test_point': ResourceType.TEST_POINTS,
}


def normalize_resource_type(resource_type: str) -> str:
    """将资源类型统一为标准复数形式。
    
    Args:
        resource_type: 资源类型字符串（支持单数或复数）
        
    Returns:
        标准化后的复数形式资源类型
    """
    if not resource_type:
        return resource_type
    # 先尝试精确匹配
    try:
        return ResourceType(resource_type).value
    except ValueError:
        # 尝试单数到复数的映射
        return RESOURCE_TYPE_MAP.get(resource_type, resource_type)
