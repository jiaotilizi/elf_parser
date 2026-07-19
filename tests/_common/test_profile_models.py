from pydantic import BaseModel
from typing import Optional
from core.profile_models import ProfileModel, MemoryRegionConfig, ChipConfig, OSConfig, DisplayConfig
from core.profile_registry import ProfileRegistry


class QemuConfig(BaseModel):
    machine: str
    cpu: Optional[str] = None
    binary: Optional[str] = None
    kernel_arg: Optional[str] = None
    serial: Optional[str] = None
    monitor: Optional[str] = None
    qmp: Optional[str] = None
    timeout: int = 30


class QemuProfileModel(ProfileModel):
    qemu: QemuConfig


ProfileRegistry.register_profile_model('qemu', QemuProfileModel)
