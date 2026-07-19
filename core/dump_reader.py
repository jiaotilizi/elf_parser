import os
import struct
from typing import Dict, List, Optional, Tuple, Any


class MemoryRegion:
    def __init__(self, name: str, start_addr: int, size: int, dump_offset: int = 0):
        self.name = name
        self.start_addr = start_addr
        self.size = size
        self.end_addr = start_addr + size
        self.dump_offset = dump_offset
    
    def contains(self, address: int) -> bool:
        return self.start_addr <= address < self.end_addr
    
    def to_dump_offset(self, address: int) -> Optional[int]:
        if self.contains(address):
            return self.dump_offset + (address - self.start_addr)
        return None


class DumpReader:
    def __init__(self, dump_path: str, memory_regions: List[Dict[str, Any]] = None):
        self.dump_path = dump_path
        self.dump_data = b''
        self.memory_regions: List[MemoryRegion] = []
        
        self._load_dump()
        self._init_memory_regions(memory_regions)
    
    def _load_dump(self):
        with open(self.dump_path, 'rb') as f:
            self.dump_data = f.read()
    
    def _init_memory_regions(self, regions_config: List[Dict[str, Any]] = None):
        if not regions_config:
            default_region = MemoryRegion('ram', 0x0, len(self.dump_data), 0)
            self.memory_regions.append(default_region)
            return
        
        dump_offset = 0
        for region_config in regions_config:
            name = region_config.get('name', 'unknown')
            start_addr = region_config.get('start_addr', 0)
            size = region_config.get('size', 0)
            offset_in_dump = region_config.get('offset_in_dump')
            
            if size == 0:
                size = len(self.dump_data) - dump_offset
            
            if offset_in_dump is not None:
                region_dump_offset = offset_in_dump
            else:
                region_dump_offset = dump_offset
            
            region = MemoryRegion(name, start_addr, size, region_dump_offset)
            self.memory_regions.append(region)
            
            if offset_in_dump is None:
                dump_offset += size
    
    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        for region in self.memory_regions:
            if region.contains(address):
                dump_offset = region.to_dump_offset(address)
                if dump_offset + size <= len(self.dump_data):
                    return self.dump_data[dump_offset:dump_offset + size]
        return None
    
    def read_uint8(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 1)
        if data:
            return struct.unpack('<B', data)[0]
        return None
    
    def read_uint16(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 2)
        if data:
            return struct.unpack('<H', data)[0]
        return None
    
    def read_uint32(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 4)
        if data:
            return struct.unpack('<I', data)[0]
        return None
    
    def read_uint64(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 8)
        if data:
            return struct.unpack('<Q', data)[0]
        return None
    
    def read_int8(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 1)
        if data:
            return struct.unpack('<b', data)[0]
        return None
    
    def read_int16(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 2)
        if data:
            return struct.unpack('<h', data)[0]
        return None
    
    def read_int32(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 4)
        if data:
            return struct.unpack('<i', data)[0]
        return None
    
    def read_int64(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 8)
        if data:
            return struct.unpack('<q', data)[0]
        return None
    
    def read_pointer(self, address: int, is_32bit: bool = True) -> Optional[int]:
        """读取指针值，地址不可读时返回 None（与 0/NULL 区分）。"""
        if is_32bit:
            return self.read_uint32(address)
        else:
            return self.read_uint64(address)
    
    def read_pointer_or_zero(self, address: int, is_32bit: bool = True) -> int:
        """读取指针值，地址不可读时返回 0（用于需要 int 类型的场景）。
        
        与 read_pointer 的区别：
          - read_pointer 返回 Optional[int]，None 表示"读不到"
          - read_pointer_or_zero 返回 int，0 表示"读不到或 NULL 指针"
          
        调用方应根据语义选择：
          - 需要区分 NULL 和"读不到"：使用 read_pointer，自己处理 None
          - 不区分或需要 int 类型（如 JSON 输出）：使用 read_pointer_or_zero
        """
        ptr = self.read_pointer(address, is_32bit)
        return ptr if ptr is not None else 0

    def read_pointer_by_size(self, address: int, byte_size: int = 4) -> Optional[int]:
        """按指针字节大小读指针值（4 或 8 字节），用于解析器跨架构泛用。"""
        if byte_size == 4:
            return self.read_uint32(address)
        elif byte_size == 8:
            return self.read_uint64(address)
        raw = self.read_memory(address, byte_size)
        return int.from_bytes(raw, 'little') if raw else None
    
    def read_string(self, address: int, max_length: int = 256) -> Optional[str]:
        data = self.read_memory(address, max_length)
        if data:
            null_pos = data.find(b'\x00')
            if null_pos >= 0:
                data = data[:null_pos]
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return data.decode('latin-1')
        return None
    
    def read_struct_array(self, address: int, struct_size: int, count: int) -> List[bytes]:
        result = []
        for i in range(count):
            struct_data = self.read_memory(address + i * struct_size, struct_size)
            if struct_data:
                result.append(struct_data)
            else:
                break
        return result
    
    def get_memory_region(self, address: int) -> Optional[MemoryRegion]:
        for region in self.memory_regions:
            if region.contains(address):
                return region
        return None
    
    def get_memory_regions_info(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': region.name,
                'start_addr': region.start_addr,
                'end_addr': region.end_addr,
                'size': region.size,
                'dump_offset': region.dump_offset,
            }
            for region in self.memory_regions
        ]
    
    def get_dump_size(self) -> int:
        return len(self.dump_data)