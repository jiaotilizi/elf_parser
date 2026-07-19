from pydantic import BaseModel
from typing import Optional, List


class MemoryRegionConfig(BaseModel):
    name: str
    start_addr: int
    size: int
    offset_in_dump: int = 0


class ChipConfig(BaseModel):
    name: str
    arch: Optional[str] = None


class OSConfig(BaseModel):
    name: str
    version: Optional[str] = None


class DisplayConfig(BaseModel):
    scheme: str = 'cli_basic'
    options: dict = {}


class QemuConfig(BaseModel):
    machine: str
    cpu: Optional[str] = None
    binary: Optional[str] = None
    kernel_arg: Optional[str] = None
    serial: Optional[str] = None
    monitor: Optional[str] = None
    qmp: Optional[str] = None
    timeout: int = 30


class QemuProfileModel(BaseModel):
    chip: ChipConfig
    memory: List[MemoryRegionConfig]
    os: Optional[OSConfig] = None
    modules: List[str] = []
    display: Optional[DisplayConfig] = None
    qemu: QemuConfig


class ProfileModel(BaseModel):
    chip: ChipConfig
    memory: List[MemoryRegionConfig]
    os: Optional[OSConfig] = None
    modules: List[str] = []
    display: Optional[DisplayConfig] = None
