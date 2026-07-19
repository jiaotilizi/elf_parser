from pydantic import BaseModel
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


class DisplayOptionsConfig(BaseModel):
    show_hex: bool = True
    show_address: bool = True
    max_rows: int = 50


class DisplayConfig(BaseModel):
    scheme: str = 'cli_basic'
    options: DisplayOptionsConfig = DisplayOptionsConfig()


class ProfileModel(BaseModel):
    chip: ChipConfig
    memory: List[MemoryRegionConfig]
    os: Optional[OSConfig] = None
    modules: List[str] = []
    display: Optional[DisplayConfig] = None
