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
import yaml
import importlib
import logging
from typing import Dict, List, Optional, Any, Type

from .exceptions import ProfileError

logger = logging.getLogger(__name__)


class PluginRegistry:
    @staticmethod
    def load_plugin(plugin_path: str):
        import_path = f"plugins.{plugin_path}"
        
        try:
            module = importlib.import_module(import_path)
        except ImportError:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            try:
                module = importlib.import_module(import_path)
            except ImportError as e:
                logger.error(f"Failed to import plugin {import_path}: {e}")
                raise ValueError(f"Failed to import plugin {import_path}: {e}")
        
        try:
            from plugins.base import Plugin
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                    if attr.__name__ in ('RTOSPlugin', 'ModulePlugin', 'Plugin'):
                        continue
                    return attr()
            
            logger.error(f"No plugin class found in {import_path}")
            raise ValueError(f"No plugin class found in {import_path}")
        except ImportError as e:
            logger.error(f"Failed to import plugin {import_path}: {e}")
            raise ValueError(f"Failed to import plugin {import_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading plugin {import_path}: {e}")
            raise


class ProfileLoader:
    def __init__(self, profiles_dir: str = None):
        if not profiles_dir:
            profiles_dir = os.path.join(os.path.dirname(__file__), '..', 'profiles')
        self.profiles_dir = os.path.abspath(profiles_dir)
    
    def load_profile(self, profile_name: str) -> Dict[str, Any]:
        profile_path = os.path.abspath(profile_name)
        
        if not os.path.exists(profile_path):
            raise ProfileError(f"Profile not found: {profile_path}")
        
        try:
            with open(profile_path, 'r') as f:
                content = yaml.safe_load(f)
                if content is None:
                    raise ProfileError(f"Profile file is empty: {profile_path}")
                return content
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {profile_path}: {e}")
            raise ProfileError(f"Failed to parse profile {profile_path}: {e}")
        except IOError as e:
            logger.error(f"Cannot read profile {profile_path}: {e}")
            raise ProfileError(f"Cannot read profile {profile_path}: {e}")
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        profiles = []
        
        for root, dirs, files in os.walk(self.profiles_dir):
            for filename in files:
                if filename.endswith(('.yaml', '.yml')):
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, self.profiles_dir)
                    profile_name = rel_path[:-5].replace(os.sep, '/')
                    
                    try:
                        with open(filepath, 'r') as f:
                            content = yaml.safe_load(f)
                            os_name = content.get('os', {}).get('name', 'unknown')
                            profiles.append({
                                'name': profile_name,
                                'path': filepath,
                                'chip': content.get('chip', {}).get('name', 'unknown'),
                                'os': os_name,
                            })
                    except Exception as e:
                        logger.warning(f"Failed to parse profile {filepath}: {e}")
                        profiles.append({
                            'name': profile_name,
                            'path': filepath,
                            'chip': 'unknown',
                            'os': 'unknown',
                        })
        
        return profiles
    
    def get_memory_regions(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        memory_config = profile.get('memory', [])
        regions = []
        
        for region in memory_config:
            regions.append({
                'name': region.get('name', 'unknown'),
                'start_addr': region.get('start_addr', 0),
                'size': region.get('size', 0),
                'offset_in_dump': region.get('offset_in_dump', 0),
            })
        
        return regions
    
    def get_os_config(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        return profile.get('os', {})
    
    def get_modules(self, profile: Dict[str, Any]) -> List[str]:
        return profile.get('modules', [])
    
    def get_display_config(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        display_config = profile.get('display', {})
        return {
            'scheme': display_config.get('scheme', 'cli_basic'),
            'options': display_config.get('options', {})
        }
    
    def validate_profile(self, profile: Dict[str, Any]) -> List[str]:
        errors = []
        
        if 'chip' not in profile:
            errors.append("Missing 'chip' section")
        else:
            if 'name' not in profile['chip']:
                errors.append("Missing 'chip.name'")
        
        return errors
    
    def load_plugins_from_profile(self, profile: Dict[str, Any]) -> List[Any]:
        plugins = []
        
        plugins_config = profile.get('plugins', [])
        for plugin_path in plugins_config:
            try:
                plugin = PluginRegistry.load_plugin(plugin_path)
                plugins.append(plugin)
                logger.debug(f"Loaded plugin: {plugin_path} -> {plugin.name}")
            except Exception as e:
                logger.warning(f"Failed to load plugin {plugin_path}: {e}")
        
        return plugins
