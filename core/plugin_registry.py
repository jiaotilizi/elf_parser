"""
MIT License

Copyright (c) 2026 Tom Yang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import os
import sys
import importlib
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Plugin discovery and management.

    On init, discovers all available plugins and caches their metadata.
    Plugins are lazily instantiated only when requested via load_plugin()
    or get_plugins_for_profile().
    """

    _PLUGIN_DIRS = ['rtos', 'module', 'arch']

    def __init__(self, plugins_dir: str = None):
        if not plugins_dir:
            plugins_dir = os.path.join(os.path.dirname(__file__), '..', 'plugins')
        self.plugins_dir = os.path.abspath(plugins_dir)
        self._plugin_cache: Dict[str, Dict[str, Any]] = {}
        self._instance_cache: Dict[str, Any] = {}
        self._discover()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _discover(self):
        """Walk plugins/ directory and discover all Plugin subclasses."""
        self._plugin_cache = {}

        for plugin_dir in self._PLUGIN_DIRS:
            full_dir = os.path.join(self.plugins_dir, plugin_dir)
            if not os.path.isdir(full_dir):
                continue

            for subdir in sorted(os.listdir(full_dir)):
                subdir_path = os.path.join(full_dir, subdir)
                if not os.path.isdir(subdir_path):
                    continue

                for filename in sorted(os.listdir(subdir_path)):
                    if not filename.endswith('.py') or filename.startswith('_'):
                        continue

                    module_name = filename[:-3]
                    import_path = f"plugins.{plugin_dir}.{subdir}.{module_name}"
                    plugin_path = f"{plugin_dir}.{subdir}.{module_name}"

                    try:
                        plugin_info = self._inspect_plugin(import_path, plugin_path)
                        if plugin_info:
                            self._plugin_cache[plugin_path] = plugin_info
                    except Exception as e:
                        logger.debug(f"Plugin discovery skipped {import_path}: {e}")

    def _inspect_plugin(self, import_path: str, plugin_path: str) -> Optional[Dict[str, Any]]:
        """Import a module and extract metadata without instantiating."""
        try:
            module = importlib.import_module(import_path)
        except ImportError:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            try:
                module = importlib.import_module(import_path)
            except ImportError as e:
                logger.debug(f"Failed to import {import_path}: {e}")
                return None

        from plugins.base import Plugin
        from plugins.rtos.base import RTOSPlugin
        from plugins.module.base import ModulePlugin

        try:
            from plugins.arch.base import ArchPlugin
        except ImportError:
            ArchPlugin = None

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if not isinstance(attr, type) or not issubclass(attr, Plugin) or attr is Plugin:
                continue
            if attr.__name__ in ('RTOSPlugin', 'ModulePlugin', 'ArchPlugin', 'Plugin'):
                continue

            plugin_type = 'unknown'
            if issubclass(attr, RTOSPlugin):
                plugin_type = 'rtos'
            elif issubclass(attr, ModulePlugin):
                plugin_type = 'module'
            elif ArchPlugin and issubclass(attr, ArchPlugin):
                plugin_type = 'arch'

            return {
                'path': plugin_path,
                'import_path': import_path,
                'class_name': attr.__name__,
                'type': plugin_type,
                'module': module,
            }

        return None

    def _ensure_sys_path(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return all discovered plugins metadata (cached, no instantiation)."""
        return list(self._plugin_cache.values())

    def load_plugin(self, plugin_path: str):
        """Load and instantiate a single plugin by its dot-path.

        Args:
            plugin_path: e.g. 'rtos.threadx.threadx_v6p5p1'

        Returns:
            Instantiated plugin object.

        Raises:
            ValueError: If the plugin is not found or cannot be loaded.
        """
        if plugin_path in self._instance_cache:
            return self._instance_cache[plugin_path]

        if plugin_path in self._plugin_cache:
            info = self._plugin_cache[plugin_path]
            return self._instantiate_plugin(plugin_path, info)

        import_path = f"plugins.{plugin_path}"
        self._ensure_sys_path()

        try:
            module = importlib.import_module(import_path)
        except ImportError as e:
            raise ValueError(f"Failed to import plugin {import_path}: {e}")

        try:
            from plugins.base import Plugin
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                    if attr.__name__ in ('RTOSPlugin', 'ModulePlugin', 'Plugin'):
                        continue
                    instance = attr()
                    self._instance_cache[plugin_path] = instance
                    return instance

            raise ValueError(f"No plugin class found in {import_path}")
        except ImportError as e:
            raise ValueError(f"Failed to import plugin {import_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading plugin {import_path}: {e}")
            raise

    def _instantiate_plugin(self, plugin_path: str, info: Dict[str, Any]):
        """Instantiate from cached discovery info."""
        if plugin_path in self._instance_cache:
            return self._instance_cache[plugin_path]

        cls = getattr(info['module'], info['class_name'])
        instance = cls()
        self._instance_cache[plugin_path] = instance
        return instance

    def get_plugins_for_profile(self, profile: Dict[str, Any]) -> List[Any]:
        """Load plugins specified in a profile's 'plugins' list.

        Returns:
            List of instantiated plugin objects.
        """
        plugins = []
        plugin_paths = profile.get('plugins', [])

        for plugin_path in plugin_paths:
            try:
                plugin = self.load_plugin(plugin_path)
                plugins.append(plugin)
                logger.debug(f"Loaded plugin: {plugin_path} -> {plugin.name}")
            except Exception as e:
                logger.warning(f"Failed to load plugin {plugin_path}: {e}")

        return plugins

    def get_arch_plugin(self, arch_name: str):
        """Load an architecture plugin by architecture name.

        Args:
            arch_name: Architecture name (e.g., 'armv7-m', 'armv7-r')

        Returns:
            Instantiated ArchPlugin object, or None if no matching plugin found.
        """
        for plugin_path, info in self._plugin_cache.items():
            if info.get('type') != 'arch':
                continue

            try:
                plugin = self._instantiate_plugin(plugin_path, info)
                if plugin.matches_arch(arch_name):
                    logger.debug(f"Loaded arch plugin for {arch_name}: {plugin.name}")
                    return plugin
            except Exception as e:
                logger.debug(f"Failed to load arch plugin {plugin_path}: {e}")

        logger.debug(f"No arch plugin found for {arch_name}")
        return None