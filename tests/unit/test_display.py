import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from display.base import ResourceMetadata
from display.data_adapter import DataAdapter
from plugins.rtos.base import RTOSPlugin
from plugins.module.base import ModulePlugin
from typing import Dict, List, Any, Optional


class MockOSPlugin(RTOSPlugin):
    def __init__(self):
        super().__init__(
            name='mock_os',
            version='1.0',
            os_name='mock',
            os_version='v1p0p0'
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'tasks': [
                {'address': 0x1000, 'name': 'task1', 'state': 0, 'priority': 1},
                {'address': 0x2000, 'name': 'task2', 'state': 1, 'priority': 2},
            ],
            'mutexes': [
                {'address': 0x3000, 'name': 'mutex1', 'owner': 0},
            ],
        }
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        if resource_type == 'tasks':
            return {'address': address, 'name': f'task_{address}', 'detail': 'test'}
        return None


class TestResourceMetadata(unittest.TestCase):
    def test_defaults(self):
        meta = ResourceMetadata('tasks', 'Tasks')
        self.assertEqual(meta.resource_type, 'tasks')
        self.assertEqual(meta.label, 'Tasks')
        self.assertEqual(meta.icon, '[Resource]')
        self.assertEqual(meta.primary_key, 'address')
        self.assertEqual(meta.fields, [])
    
    def test_custom_fields(self):
        fields = [{'name': 'name', 'label': 'Name', 'type': 'string'}]
        meta = ResourceMetadata('tasks', 'Tasks', icon='[Tasks]', primary_key='id', fields=fields)
        self.assertEqual(meta.icon, '[Tasks]')
        self.assertEqual(meta.primary_key, 'id')
        self.assertEqual(len(meta.fields), 1)
        self.assertEqual(meta.fields[0]['name'], 'name')


class TestDataAdapter(unittest.TestCase):
    def setUp(self):
        mock_plugin = MockOSPlugin()
        
        self.context = {
            'profile': {},
            'plugins': [mock_plugin],
            'results': {
                'mock_os': {
                    'tasks': [
                        {'address': 0x1000, 'name': 'task1', 'state': 0, 'priority': 1},
                        {'address': 0x2000, 'name': 'task2', 'state': 1, 'priority': 2},
                    ],
                    'mutexes': [
                        {'address': 0x3000, 'name': 'mutex1', 'owner': 0},
                    ],
                }
            }
        }
    
    def test_get_all_resource_types(self):
        adapter = DataAdapter(self.context)
        types = adapter.get_all_resource_types()
        self.assertIn('tasks', types)
        self.assertIn('mutexes', types)
    
    def test_get_resource_data(self):
        adapter = DataAdapter(self.context)
        tasks = adapter.get_resource_data('tasks')
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['name'], 'task1')
    
    def test_get_resource_metadata(self):
        adapter = DataAdapter(self.context)
        meta = adapter.get_resource_metadata('tasks')
        self.assertIsNotNone(meta)
        self.assertEqual(meta.resource_type, 'tasks')
        self.assertEqual(meta.label, 'Tasks')
    
    def test_get_detail(self):
        adapter = DataAdapter(self.context)
        detail = adapter.get_detail('tasks', 0x1000)
        self.assertIsNotNone(detail)
        self.assertEqual(detail['address'], 0x1000)
    
    def test_refresh_all(self):
        adapter = DataAdapter(self.context)
        _ = adapter.get_resource_data('tasks')
        self.assertTrue(adapter.is_cache_valid())
        adapter.refresh()
        self.assertFalse(adapter.is_cache_valid())
    
    def test_refresh_single(self):
        adapter = DataAdapter(self.context)
        _ = adapter.get_resource_data('tasks')
        _ = adapter.get_resource_data('mutexes')
        adapter.refresh('tasks')
        self.assertNotIn('tasks', adapter._cached_data)
        self.assertIn('mutexes', adapter._cached_data)
    
    def test_cache_ttl(self):
        adapter = DataAdapter(self.context, cache_ttl=0)
        _ = adapter.get_resource_data('tasks')
        self.assertFalse(adapter.is_cache_valid())


if __name__ == '__main__':
    unittest.main()
