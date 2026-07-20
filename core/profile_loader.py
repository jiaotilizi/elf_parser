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
import yaml
import logging
from typing import Dict, List, Any

from .exceptions import ProfileError

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Profile discovery and management.

    On init, discovers all available profiles and caches their metadata.
    list_profiles() returns cached data without re-reading files.
    """

    def __init__(self, profiles_dir: str = None):
        if not profiles_dir:
            profiles_dir = os.path.join(os.path.dirname(__file__), '..', 'profiles')
        self.profiles_dir = os.path.abspath(profiles_dir)
        self._profile_cache: Dict[str, Dict[str, Any]] = {}
        self._discover()

    def _discover(self):
        """Discover all profiles and cache their metadata."""
        self._profile_cache = {}

        for root, dirs, files in os.walk(self.profiles_dir):
            for filename in files:
                if filename.endswith(('.yaml', '.yml')):
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, self.profiles_dir)
                    profile_name = rel_path[:-5].replace(os.sep, '/')

                    try:
                        with open(filepath, 'r') as f:
                            content = yaml.safe_load(f)
                            self._profile_cache[profile_name] = {
                                'name': profile_name,
                                'path': filepath,
                                'chip': content.get('chip', {}).get('name', 'unknown'),
                                'arch': content.get('chip', {}).get('arch', 'unknown'),
                                'vendor': content.get('chip', {}).get('vendor', 'unknown'),
                                'description': content.get('chip', {}).get('description', ''),
                            }
                    except Exception as e:
                        logger.warning(f"Failed to parse profile {filepath}: {e}")
                        self._profile_cache[profile_name] = {
                            'name': profile_name,
                            'path': filepath,
                            'chip': 'unknown',
                            'arch': 'unknown',
                            'vendor': 'unknown',
                            'description': '',
                        }

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
        """Return cached profile metadata (no re-reading of files)."""
        return list(self._profile_cache.values())
    
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
    
    def get_parser_config(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        parser_config = profile.get('parser', 'elftools')
        if isinstance(parser_config, str):
            return {'type': parser_config, 'options': {}}
        return {
            'type': parser_config.get('type', 'elftools'),
            'options': parser_config.get('options', {})
        }
    
    def validate_profile(self, profile: Dict[str, Any]) -> List[str]:
        errors = []
        
        if 'chip' not in profile:
            errors.append("Missing 'chip' section")
        else:
            if 'name' not in profile['chip']:
                errors.append("Missing 'chip.name'")
        
        return errors
    
    
