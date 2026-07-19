"""RTOS plugin package.

Provides the RTOSPlugin base class and resource type definitions.
"""

from .base import RTOSPlugin, ResourceType, RESOURCE_TYPE_MAP, normalize_resource_type

__all__ = ['RTOSPlugin', 'ResourceType', 'RESOURCE_TYPE_MAP', 'normalize_resource_type']
