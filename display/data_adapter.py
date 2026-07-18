from typing import Dict, List, Any, Optional


class DataAdapter:
    def __init__(self, plugin_manager, context: Dict[str, Any]):
        self.plugin_manager = plugin_manager
        self.context = context
        self.rtos_data = {}
        self.test_point_data = {}
    
    def _get_os_plugin(self):
        profile = self.context.get('profile', {})
        os_config = profile.get('os', {})
        os_name = os_config.get('name')
        os_version = os_config.get('version')
        
        if os_name and os_version:
            return self.plugin_manager.get_os_plugin(os_name, os_version)
        
        if os_name:
            for plugin in self.plugin_manager.os_plugins.values():
                if plugin.os_name == os_name:
                    return plugin
        
        for plugin in self.plugin_manager.os_plugins.values():
            return plugin
        return None
    
    def _get_test_point_plugin(self):
        return self.plugin_manager.module_plugins.get('test_point')
    
    def get_rtos_data(self) -> Dict[str, Any]:
        if self.rtos_data:
            return self.rtos_data
        
        os_plugin = self._get_os_plugin()
        if os_plugin:
            try:
                self.rtos_data = os_plugin.execute(self.context)
            except Exception as e:
                print(f"Error getting RTOS data: {e}")
        
        return self.rtos_data
    
    def get_test_points(self) -> List[Dict[str, Any]]:
        if self.test_point_data:
            return self.test_point_data.get('test_points', [])
        
        tp_plugin = self._get_test_point_plugin()
        if tp_plugin:
            try:
                self.test_point_data = tp_plugin.execute(self.context)
            except Exception as e:
                print(f"Error getting test point data: {e}")
        
        return self.test_point_data.get('test_points', [])
    
    def get_trace_buffer(self) -> List[Dict[str, Any]]:
        if self.test_point_data:
            return self.test_point_data.get('trace_buffer', [])
        
        tp_plugin = self._get_test_point_plugin()
        if tp_plugin:
            try:
                self.test_point_data = tp_plugin.execute(self.context)
            except Exception as e:
                print(f"Error getting trace buffer: {e}")
        
        return self.test_point_data.get('trace_buffer', [])
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        os_plugin = self._get_os_plugin()
        if os_plugin and hasattr(os_plugin, 'get_detail'):
            try:
                return os_plugin.get_detail(resource_type, address)
            except Exception as e:
                print(f"Error getting detail: {e}")
        
        tp_plugin = self._get_test_point_plugin()
        if tp_plugin and hasattr(tp_plugin, 'get_detail'):
            try:
                return tp_plugin.get_detail(resource_type, address)
            except Exception as e:
                print(f"Error getting test point detail: {e}")
        
        return None
    
    def refresh(self):
        self.rtos_data = {}
        self.test_point_data = {}