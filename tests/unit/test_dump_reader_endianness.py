import os
import sys
import unittest
import tempfile
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.dump_reader import DumpReader


class TestDumpReaderEndianness(unittest.TestCase):
    """测试 DumpReader 的端序支持。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dump_path = os.path.join(self.temp_dir, 'test_dump.bin')

    def tearDown(self):
        if os.path.exists(self.dump_path):
            os.remove(self.dump_path)
        os.rmdir(self.temp_dir)

    def test_read_uint32_little_endian_default(self):
        """默认小端序读取 uint32。"""
        ptr_value = 0x12345678
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('<I', ptr_value))

        reader = DumpReader(self.dump_path)
        self.assertEqual(reader.read_uint32(0), ptr_value)

    def test_read_uint32_little_endian_explicit(self):
        """显式指定小端序读取 uint32。"""
        ptr_value = 0x12345678
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('<I', ptr_value))

        reader = DumpReader(self.dump_path, endianness='little')
        self.assertEqual(reader.read_uint32(0), ptr_value)

    def test_read_uint32_big_endian(self):
        """大端序读取 uint32。"""
        ptr_value = 0x12345678
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('>I', ptr_value))

        reader = DumpReader(self.dump_path, endianness='big')
        self.assertEqual(reader.read_uint32(0), ptr_value)

    def test_read_uint16_big_endian(self):
        """大端序读取 uint16。"""
        value = 0x1234
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('>H', value))

        reader = DumpReader(self.dump_path, endianness='big')
        self.assertEqual(reader.read_uint16(0), value)

    def test_read_uint64_big_endian(self):
        """大端序读取 uint64。"""
        value = 0x123456789ABCDEF0
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('>Q', value))

        reader = DumpReader(self.dump_path, endianness='big')
        self.assertEqual(reader.read_uint64(0), value)

    def test_read_pointer_little_endian(self):
        """小端序读取指针。"""
        ptr_value = 0x88001234
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('<I', ptr_value))

        reader = DumpReader(self.dump_path)
        self.assertEqual(reader.read_pointer(0, True), ptr_value)

    def test_read_pointer_big_endian(self):
        """大端序读取指针。"""
        ptr_value = 0x88001234
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('>I', ptr_value))

        reader = DumpReader(self.dump_path, endianness='big')
        self.assertEqual(reader.read_pointer(0, True), ptr_value)

    def test_read_pointer_64bit_big_endian(self):
        """大端序读取 64 位指针。"""
        ptr_value = 0x880012345678ABCD
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('>Q', ptr_value))

        reader = DumpReader(self.dump_path, endianness='big')
        self.assertEqual(reader.read_pointer(0, False), ptr_value)

    def test_invalid_endianness_raises_error(self):
        """无效的端序参数抛出 ValueError。"""
        with self.assertRaises(ValueError):
            DumpReader(self.dump_path, endianness='invalid')


if __name__ == '__main__':
    unittest.main()