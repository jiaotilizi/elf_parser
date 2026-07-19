import os
import sys
import importlib
import logging
from typing import Dict, List, Optional, Type, Any, Callable

from .exceptions import PluginError

logger = logging.getLogger(__name__)


class Plugin:
    def __init__(self, name: str, version: str, description: str = ""):
        self.name = name
        self.version = version
        self.description = description
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def get_required_symbols(self) -> List[str]:
        return []
    
    def get_required_structs(self) -> List[str]:
        return []


class OSPlugin(Plugin):
    def __init__(self, name: str, version: str, os_name: str, os_version: str, description: str = ""):
        super().__init__(name, version, description)
        self.os_name = os_name
        self.os_version = os_version
        self._context = None
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self._context = context
        return True
    
    def _walk_created_list(self, 
                          symbol_name: str, 
                          struct_name: str, 
                          next_field_name: str,
                          parse_func: Callable[[int, Dict[str, Any], Any, Any, bool], Optional[Dict[str, Any]]],
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            logger.warning(f"Missing elf_parser or dump_reader in context for {symbol_name}")
            return []
        
        list_sym = elf_parser.get_symbol_by_name(symbol_name)
        if not list_sym:
            logger.warning(f"Symbol not found: {symbol_name}")
            return []
        
        list_addr = list_sym['address']
        is_32bit = elf_parser.is_32bit()
        
        struct_type = elf_parser.get_struct_type(struct_name)
        if not struct_type:
            logger.warning(f"Struct type not found: {struct_name}")
            return []
        
        head_ptr = dump_reader.read_pointer(list_addr, is_32bit)
        if not head_ptr:
            return []
        
        next_offset = 0
        for member in struct_type.get('members', []):
            if member.get('name') == next_field_name:
                next_offset = member.get('offset', 0)
                break
        
        visited = set()
        current_ptr = head_ptr
        results = []
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            item_info = parse_func(current_ptr, struct_type, elf_parser, dump_reader, is_32bit)
            if item_info:
                results.append(item_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + next_offset, is_32bit)
            current_ptr = next_ptr
        
        return results
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def get_current_task(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None


class ModulePlugin(Plugin):
    def __init__(self, name: str, version: str, module_type: str, description: str = ""):
        super().__init__(name, version, description)
        self.module_type = module_type


class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.os_plugins: Dict[str, OSPlugin] = {}
        self.module_plugins: Dict[str, ModulePlugin] = {}
        
        self._plugin_modules: Dict[str, Any] = {}
    
    def discover_plugins(self, plugins_dir: str = None):
        if not plugins_dir:
            plugins_dir = os.path.join(os.path.dirname(__file__), '..', 'plugins')
        
        plugins_dir = os.path.abspath(plugins_dir)
        
        if not os.path.exists(plugins_dir):
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return
        
        for root, dirs, files in os.walk(plugins_dir):
            for filename in files:
                if filename.endswith('.py') and not filename.startswith('_'):
                    rel_path = os.path.relpath(root, plugins_dir)
                    module_path = os.path.join(rel_path, filename[:-3]).replace(os.sep, '.')
                    
                    if module_path.startswith('.'):
                        module_path = module_path[1:]
                    
                    if not module_path:
                        module_path = filename[:-3]
                    
                    self._load_plugin_module(module_path, plugins_dir)
    
    def _load_plugin_module(self, module_path: str, plugins_dir: str):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, plugins_dir)
        sys.path.insert(0, project_root)
        
        try:
            module = importlib.import_module(module_path)
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                    try:
                        plugin_instance = attr()
                        self._register_plugin(plugin_instance)
                        logger.debug(f"Loaded plugin: {plugin_instance.name}")
                    except Exception as e:
                        logger.error(f"Failed to instantiate plugin {attr_name}: {e}")
        except ImportError as e:
            logger.error(f"Failed to import plugin module {module_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading plugin {module_path}: {e}")
        finally:
            if plugins_dir in sys.path:
                sys.path.remove(plugins_dir)
    
    def _register_plugin(self, plugin: Plugin):
        self.plugins[plugin.name] = plugin
        
        if isinstance(plugin, OSPlugin):
            key = f"{plugin.os_name}_{plugin.os_version}"
            self.os_plugins[key] = plugin
            logger.debug(f"Registered OS plugin: {key}")
        elif isinstance(plugin, ModulePlugin):
            self.module_plugins[plugin.name] = plugin
            logger.debug(f"Registered module plugin: {plugin.name}")
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self.plugins.get(name)
    
    def get_os_plugin(self, os_name: str, os_version: str) -> Optional[OSPlugin]:
        key = f"{os_name}_{os_version}"
        plugin = self.os_plugins.get(key)
        if not plugin:
            logger.warning(f"No OS plugin found for {key}")
        return plugin
    
    def get_module_plugin(self, name: str) -> Optional[ModulePlugin]:
        return self.module_plugins.get(name)
    
    def load_plugins_from_profile(self, profile: Dict[str, Any]) -> List[Plugin]:
        loaded_plugins = []
        
        os_config = profile.get('os', {})
        os_name = os_config.get('name')
        os_version = os_config.get('version')
        
        if os_name and os_version:
            os_plugin = self.get_os_plugin(os_name, os_version)
            if os_plugin:
                loaded_plugins.append(os_plugin)
            else:
                logger.warning(f"OS plugin not found: {os_name}_{os_version}")
        elif os_name:
            os_plugin = self.os_plugins.get(os_name)
            if os_plugin:
                loaded_plugins.append(os_plugin)
        
        modules_config = profile.get('modules', [])
        for module_name in modules_config:
            module_plugin = self.get_module_plugin(module_name)
            if module_plugin:
                loaded_plugins.append(module_plugin)
            else:
                logger.warning(f"Module plugin not found: {module_name}")
        
        return loaded_plugins
    
    def initialize_plugins(self, plugins: List[Plugin], context: Dict[str, Any]) -> List[Plugin]:
        initialized = []
        for plugin in plugins:
            try:
                if plugin.initialize(context):
                    initialized.append(plugin)
                else:
                    logger.warning(f"Plugin {plugin.name} initialization returned False")
            except Exception as e:
                logger.error(f"Failed to initialize plugin {plugin.name}: {e}")
                raise PluginError(f"Failed to initialize plugin {plugin.name}: {e}")
        return initialized
    
    def execute_plugins(self, plugins: List[Plugin], context: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        for plugin in plugins:
            try:
                result = plugin.execute(context)
                if result:
                    results[plugin.name] = result
            except Exception as e:
                logger.error(f"Failed to execute plugin {plugin.name}: {e}")
                results[plugin.name] = {'error': str(e)}
        return results
    
    def list_all_plugins(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            'os': [
                {
                    'name': p.name,
                    'version': p.version,
                    'os_name': p.os_name,
                    'os_version': p.os_version,
                    'description': p.description,
                }
                for p in self.os_plugins.values()
            ],
            'module': [
                {
                    'name': p.name,
                    'version': p.version,
                    'module_type': p.module_type,
                    'description': p.description,
                }
                for p in self.module_plugins.values()
            ],
            'all': [
                {
                    'name': p.name,
                    'version': p.version,
                    'type': 'os' if isinstance(p, OSPlugin) else 'module',
                    'description': p.description,
                }
                for p in self.plugins.values()
            ],
        }


class PluginContext:
    def __init__(self):
        self.elf_parser = None
        self.dump_reader = None
        self.profile = None
        self.results = {}
        self.config = {}
    
    def set_elf_parser(self, parser):
        self.elf_parser = parser
    
    def set_dump_reader(self, reader):
        self.dump_reader = reader
    
    def set_profile(self, profile):
        self.profile = profile
    
    def set_config(self, config):
        self.config = config
    
    def add_result(self, key: str, value: Any):
        self.results[key] = value
    
    def get_result(self, key: str) -> Optional[Any]:
        return self.results.get(key)
