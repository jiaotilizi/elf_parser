from pydantic import BaseModel, field_validator, ValidationInfo
from typing import List, Dict, Optional


class ChipConfig(BaseModel):
    name: str
    cpu: Optional[str] = None
    vendor: Optional[str] = None


class MemoryRegionConfig(BaseModel):
    name: str
    start_addr: int
    size: int
    offset_in_dump: int = 0


class OSConfig(BaseModel):
    name: str
    version: str
    
    @field_validator('version')
    def validate_version_format(cls, v, info: ValidationInfo):
        if not v.startswith('v'):
            raise ValueError(f"OS version must start with 'v', got: {v}")
        parts = v[1:].split('p')
        if len(parts) != 3:
            raise ValueError(f"OS version must be in format 'vMAJORpMINORpPATCH', got: {v}")
        return v


class DisplayOptionsConfig(BaseModel):
    show_hex: bool = True
    show_address: bool = True
    max_rows: int = 50


class DisplayConfig(BaseModel):
    scheme: str = 'cli_basic'
    options: DisplayOptionsConfig = DisplayOptionsConfig()


class QemuConfig(BaseModel):
    machine: str
    cpu: Optional[str] = None
    binary: Optional[str] = None
    kernel_arg: Optional[str] = None
    serial: Optional[str] = None
    monitor: Optional[str] = None
    qmp: Optional[str] = None
    timeout: int = 30


class ProfileModel(BaseModel):
    chip: ChipConfig
    os: OSConfig
    memory: List[MemoryRegionConfig]
    modules: List[str] = []
    display: DisplayConfig = DisplayConfig()
    qemu: Optional[QemuConfig] = None
    
    @field_validator('memory')
    def validate_memory_not_empty(cls, v, info: ValidationInfo):
        if len(v) == 0:
            raise ValueError("Profile must have at least one memory region")
        return v
