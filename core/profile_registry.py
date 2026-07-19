from typing import Dict, Type, Any
from .profile_models import ProfileModel


class ProfileRegistry:
    _registered_models: Dict[str, Type[ProfileModel]] = {}
    
    @classmethod
    def register_profile_model(cls, profile_type: str, model_class: Type[ProfileModel]):
        cls._registered_models[profile_type] = model_class
    
    @classmethod
    def get_profile_model(cls, profile_type: str) -> Type[ProfileModel]:
        return cls._registered_models.get(profile_type, ProfileModel)
    
    @classmethod
    def list_registered_models(cls) -> Dict[str, Type[ProfileModel]]:
        return cls._registered_models.copy()
    
    @classmethod
    def clear_registry(cls):
        cls._registered_models.clear()
