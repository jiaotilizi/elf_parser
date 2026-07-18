import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader


class TestQEMUM4ThreadXFirmwareAutoParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.firmware_dir = os.path.join(os.path.dirname(__file__), 'firmware')
        cls.elf_path = os.path.join(cls.firmware_dir, 'output', 'img', 'sample_threadx.elf')
        cls.dump_path = os.path.join(cls.firmware_dir, 'output', 'img', 'threadx_ram_dump.bin')
        
        assert os.path.exists(cls.elf_path), f"ELF not found: {cls.elf_path}"
        assert os.path.exists(cls.dump_path), f"Dump not found: {cls.dump_path}"
        
        cls.elf_parser = ELFParser(cls.elf_path)
        cls.dump_reader = DumpReader(cls.dump_path, base_address=0x20000000)

    def test_threadx_thread_control_block_in_dwarf(self):
        self.assertTrue(self.elf_parser.has_type('TX_THREAD'), "TX_THREAD type should exist in DWARF")

    def test_threadx_current_thread_non_null(self):
        addr = self.elf_parser.get_symbol_address('_tx_thread_current_ptr')
        self.assertIsNotNone(addr, "_tx_thread_current_ptr symbol should exist")
        ptr_value = self.dump_reader.read_uint32(addr)
        self.assertNotEqual(ptr_value, 0, "Current thread pointer should not be NULL")

    def test_threadx_created_thread_count(self):
        thread_count = 0
        symbols = self.elf_parser.get_all_symbols()
        for sym in symbols:
            if sym['name'].startswith('thread_') and sym['name'] != 'thread_0_counter':
                addr = sym['address']
                if addr is not None and 0x20000000 <= addr < 0x20800000:
                    thread_count += 1
        self.assertGreaterEqual(thread_count, 8, "At least 8 threads should exist")

    def test_threadx_thread_name_deref(self):
        addr = self.elf_parser.get_symbol_address('thread_0')
        if addr is not None:
            tcb = self.elf_parser.parse_struct_auto('TX_THREAD', self.dump_reader, addr)
            if tcb and 'tx_thread_name' in tcb:
                name = tcb['tx_thread_name']
                self.assertIsInstance(name, str, "Thread name should be string")
                self.assertTrue(len(name) > 0, "Thread name should not be empty")

    def test_threadx_semaphore_in_dwarf(self):
        self.assertTrue(self.elf_parser.has_type('TX_SEMAPHORE'), "TX_SEMAPHORE type should exist")

    def test_threadx_mutex_in_dwarf(self):
        self.assertTrue(self.elf_parser.has_type('TX_MUTEX'), "TX_MUTEX type should exist")

    def test_threadx_queue_in_dwarf(self):
        self.assertTrue(self.elf_parser.has_type('TX_QUEUE'), "TX_QUEUE type should exist")

    def test_threadx_event_flags_in_dwarf(self):
        self.assertTrue(self.elf_parser.has_type('TX_EVENT_FLAGS_GROUP'), "TX_EVENT_FLAGS_GROUP type should exist")

    def test_threadx_byte_pool_in_dwarf(self):
        self.assertTrue(self.elf_parser.has_type('TX_BYTE_POOL'), "TX_BYTE_POOL type should exist")

    def test_threadx_semaphore_count(self):
        addr = self.elf_parser.get_symbol_address('semaphore_0')
        if addr is not None:
            sem = self.elf_parser.parse_struct_auto('TX_SEMAPHORE', self.dump_reader, addr)
            if sem and 'tx_semaphore_count' in sem:
                self.assertIsInstance(sem['tx_semaphore_count'], int, "Semaphore count should be int")


if __name__ == '__main__':
    unittest.main()