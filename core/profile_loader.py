import os
import yaml
import logging
from typing import Dict, List, Optional, Any
from .exceptions import ProfileError
from .profile_models import ProfileModel

logger = logging.getLogger(__name__)


class ProfileLoader:
    def __init__(self, profiles_dir: str = None):
        if not profiles_dir:
            profiles_dir = os.path.join(os.path.dirname(__file__), '..', 'profiles')
        self.profiles_dir = os.path.abspath(profiles_dir)
    
    def load_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        profile_path = self._find_profile(profile_name)
        if not profile_path:
            logger.warning(f"Profile not found: {profile_name}")
            return None
        
        try:
            with open(profile_path, 'r') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {profile_path}: {e}")
            raise ProfileError(f"Failed to parse profile {profile_name}: {e}")
        except IOError as e:
            logger.error(f"Cannot read profile {profile_path}: {e}")
            raise ProfileError(f"Cannot read profile {profile_name}: {e}")
    
    def _find_profile(self, profile_name: str) -> Optional[str]:
        if os.path.isabs(profile_name):
            if os.path.exists(profile_name):
                return profile_name
            return None
        
        paths_to_check = [
            os.path.join(self.profiles_dir, f"{profile_name}.yaml"),
            os.path.join(self.profiles_dir, f"{profile_name}.yml"),
            os.path.join(self.profiles_dir, profile_name, "config.yaml"),
            os.path.join(self.profiles_dir, profile_name, "config.yml"),
        ]
        
        for path in paths_to_check:
            if os.path.exists(path):
                return path
        
        for root, dirs, files in os.walk(self.profiles_dir):
            for filename in files:
                if filename.endswith(('.yaml', '.yml')):
                    filepath = os.path.join(root, filename)
                    if profile_name in filepath or profile_name == filename[:-5]:
                        return filepath
        
        return None
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        profiles = []
        
        for root, dirs, files in os.walk(self.profiles_dir):
            for filename in files:
                if filename.endswith(('.yaml', '.yml')):
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, self.profiles_dir)
                    
                    try:
                        with open(filepath, 'r') as f:
                            content = yaml.safe_load(f)
                            os_name = content.get('os', {}).get('name', 'unknown')
                            os_version = content.get('os', {}).get('version', 'unknown')
                            profiles.append({
                                'name': rel_path[:-5],
                                'path': filepath,
                                'chip': content.get('chip', {}).get('name', 'unknown'),
                                'os': os_name,
                                'os_version': os_version,
                            })
                    except Exception as e:
                        logger.warning(f"Failed to parse profile {filepath}: {e}")
                        profiles.append({
                            'name': rel_path[:-5],
                            'path': filepath,
                            'chip': 'unknown',
                            'os': 'unknown',
                            'os_version': 'unknown',
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
        
        if 'os' not in profile:
            errors.append("Missing 'os' section")
        else:
            if 'name' not in profile['os']:
                errors.append("Missing 'os.name'")
        
        if 'memory' not in profile:
            errors.append("Missing 'memory' section")
        
        return errors
    
    def validate_profile_pydantic(self, profile: Dict[str, Any]) -> Optional[ProfileModel]:
        try:
            return ProfileModel(**profile)
        except Exception as e:
            logger.error(f"Profile validation failed: {e}")
            raise ProfileError(f"Profile validation failed: {e}")
