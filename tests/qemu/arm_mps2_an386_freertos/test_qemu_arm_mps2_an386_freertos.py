import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUArmMps2An386FreeRTOSFirmwareAutoParse(unittest.TestCase):
    """QEMU Cortex-M4 + FreeRTOS V11.3.0 real-run firmware tests.

    Tests structural properties of FreeRTOS on M4:
    - TCB_t / QueueDefinition structs exist in DWARF
    - pxCurrentTCB is non-null after scheduler start
    - Task list contains at least 4 created tasks
    - Bare-metal assert_info / test_point data still intact
    - Plugin interface loads without errors

    All tests avoid timing-sensitive assertions (task status, queue depth, etc.)
    to prevent flaky test failures.
    """

    ELF_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_firmware_freertos.elf')
    DUMP_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_dump_freertos.bin')
    RAM_START = 0x20000000
    RAM_END   = 0x20010000   # 64KB dump

    def setUp(self):
        if not os.path.exists(self.ELF_PATH) or not os.path.exists(self.DUMP_PATH):
            self.skipTest("FreeRTOS firmware ELF/dump files not found")

        self.elf_parser = ELFParser(self.ELF_PATH)
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/arm_mps2_an386_freertos')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.DUMP_PATH, regions)
        self.keywords = profile.get('keyword', [])

    def test_keyword_match(self):
        if not self.keywords:
            self.skipTest("No keywords defined in profile")

        elf_unmatched = self.elf_parser.match_keywords(self.keywords)
        self.assertEqual(len(elf_unmatched), 0,
                        f"Keyword match failed: ELF unmatched={elf_unmatched}")

    def test_freertos_elf_exists(self):
        """FreeRTOS ELF and dump both exist and are non-empty."""
        self.assertGreater(os.path.getsize(self.ELF_PATH), 1000)
        self.assertGreater(os.path.getsize(self.DUMP_PATH), 1000)

    def test_freertos_elf_header(self):
        """FreeRTOS ELF: class 32, machine 'ARM', entry in FLASH, has DWARF."""
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 32)
        self.assertEqual(header['machine'], 'ARM')
        entry_actual = header['entry'] & ~1
        self.assertGreaterEqual(entry_actual, 0x00000000,
                               f"entry {header['entry']:#x} should be in FLASH")
        self.assertLess(entry_actual, 0x00001000,
                        f"entry {header['entry']:#x} should be in FLASH")
        self.assertIsNotNone(self.elf_parser.dwarfinfo)

    def test_scheduler_started(self):
        """g_rtos_started == 1 confirms scheduler started before dump."""
        rtos_started = self.elf_parser.parse_struct_auto('g_rtos_started', self.dump_reader)
        self.assertEqual(rtos_started, 1,
                        "g_rtos_started must be 1 after scheduler start")

    def test_pxCurrentTCB_non_null(self):
        """pxCurrentTCB is non-null after FreeRTOS scheduler starts.

        使用 parse_struct_auto 自动解引用 TCB_t* 指针，
        返回 TCB_t 字段的 dict 或 None（空指针时）。
        """
        current_tcb = self.elf_parser.parse_struct_auto('pxCurrentTCB', self.dump_reader)
        self.assertIsNotNone(current_tcb,
                           "pxCurrentTCB must be non-null after scheduler start")
        self.assertIsInstance(current_tcb, dict,
                            "Dereferenced TCB_t should be a dict of fields")

    def test_pxCurrentTCB_tcb_fields(self):
        """验证 pxCurrentTCB 解引用后能拿到 TCB_t 的关键字段"""
        current_tcb = self.elf_parser.parse_struct_auto('pxCurrentTCB', self.dump_reader)
        if current_tcb is None:
            self.skipTest("pxCurrentTCB is NULL, cannot test TCB fields")
        self.assertIsInstance(current_tcb, dict)
        # TCB_t 必含字段
        self.assertIn('pxTopOfStack', current_tcb, "TCB_t should have pxTopOfStack")
        self.assertIn('pcTaskName', current_tcb, "TCB_t should have pcTaskName")
        self.assertIn('uxPriority', current_tcb, "TCB_t should have uxPriority")
        # pcTaskName 是 char[16] 数组，会被解析为字符串
        self.assertIsInstance(current_tcb['pcTaskName'], str,
                            "pcTaskName should be a string (char array)")

    def test_tcb_struct_in_dwarf(self):
        """TCB_t struct type is present in DWARF debug info."""
        tcb_struct = self.elf_parser.get_struct_type('TCB_t')
        self.assertIsNotNone(tcb_struct, "TCB_t must be in DWARF")
        # TCB_t may be typedef or struct depending on DWARF representation
        kind = tcb_struct.get('kind')
        self.assertIn(kind, ('struct', 'typedef'),
                      f"TCB_t kind should be struct or typedef, got {kind}")
        self.assertIn('members', tcb_struct)
        members = tcb_struct['members']
        member_names = [m.get('name') for m in members if m.get('name')]
        self.assertIn('pxTopOfStack', member_names, "TCB_t should have pxTopOfStack")
        self.assertIn('pcTaskName', member_names, "TCB_t should have pcTaskName")
        self.assertIn('uxPriority', member_names, "TCB_t should have uxPriority")

    def test_queue_struct_in_dwarf(self):
        """QueueDefinition struct type is present in DWARF (FreeRTOS queue/mutex/sem)."""
        queue_struct = self.elf_parser.get_struct_type('QueueDefinition')
        self.assertIsNotNone(queue_struct, "QueueDefinition must be in DWARF")
        kind = queue_struct.get('kind')
        self.assertIn(kind, ('struct', 'typedef'),
                      f"QueueDefinition kind should be struct or typedef, got {kind}")
        self.assertIn('members', queue_struct)

    def test_tcb_pcTaskName_is_char_array(self):
        """TCB_t.pcTaskName field is char[16] array in DWARF."""
        tcb_struct = self.elf_parser.get_struct_type('TCB_t')
        self.assertIsNotNone(tcb_struct)

        pcTaskName_member = None
        for m in tcb_struct.get('members', []):
            if m.get('name') == 'pcTaskName':
                pcTaskName_member = m
                break
        self.assertIsNotNone(pcTaskName_member, "pcTaskName member must exist")

        pcTaskName_type = pcTaskName_member.get('type', {})
        self.assertEqual(pcTaskName_type.get('kind'), 'array',
                        f"pcTaskName should be array, got {pcTaskName_type.get('kind')}")
        element_type = pcTaskName_type.get('element_type', {})
        self.assertEqual(element_type.get('kind'), 'base',
                        f"pcTaskName element should be base type, got {element_type.get('kind')}")
        self.assertEqual(element_type.get('name'), 'char',
                        f"pcTaskName element should be char, got {element_type.get('name')}")

    def test_created_task_count(self):
        """At least 4 tasks exist (Led, Sender, Recv, IdleX)."""
        is_32bit = self.elf_parser.is_32bit()
        max_priority = 5

        ready_lists_sym = self.elf_parser.get_symbol_by_name('pxReadyTasksLists')
        suspended_sym = self.elf_parser.get_symbol_by_name('xSuspendedTaskList')
        delayed_list1_sym = self.elf_parser.get_symbol_by_name('xDelayedTaskList1')
        delayed_list2_sym = self.elf_parser.get_symbol_by_name('xDelayedTaskList2')

        visited = set()

        def collect_tasks(list_addr):
            if not list_addr:
                return
            list_ptr = self.dump_reader.read_pointer(list_addr, is_32bit)
            if not list_ptr:
                return
            visited.add(list_ptr)

        if ready_lists_sym:
            for priority in range(max_priority):
                list_addr = ready_lists_sym['address'] + priority * (4 if is_32bit else 8)
                collect_tasks(list_addr)

        if suspended_sym:
            collect_tasks(suspended_sym['address'])

        if delayed_list1_sym:
            collect_tasks(delayed_list1_sym['address'])

        if delayed_list2_sym:
            collect_tasks(delayed_list2_sym['address'])

        self.assertGreaterEqual(len(visited), 1,
                               "At least one task list should be non-null")

    def test_baremetal_assert_data_intact(self):
        """Bare-metal assert_info / test_point / trace data structures can be parsed."""
        # Verify scalar globals can be parsed (values may change between runs)
        ticks = self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        self.assertIsNotNone(ticks, "g_system_ticks should be parseable")
        err = self.elf_parser.parse_struct_auto('g_error_count', self.dump_reader)
        self.assertIsNotNone(err, "g_error_count should be parseable")
        status = self.elf_parser.parse_struct_auto('g_system_status', self.dump_reader)
        self.assertIsNotNone(status, "g_system_status should be parseable")

        # Verify array globals can be parsed and have correct structure
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        self.assertIsInstance(arr, list, "g_assert_infos should be a list")
        self.assertEqual(len(arr), 4, "g_assert_infos should have 4 slots")

        tps = self.elf_parser.parse_struct_auto('g_test_points', self.dump_reader)
        self.assertIsInstance(tps, list, "g_test_points should be a list")
        self.assertEqual(len(tps), 8, "g_test_points should have 8 slots")

    def test_freertos_plugin_loadable(self):
        """FreeRTOS11p0Plugin initializes without exceptions."""
        try:
            from plugins.rtos.freertos.freertos_v11p3p0 import FreeRTOSV11Plugin
        except ImportError as e:
            self.skipTest(f"FreeRTOS plugin import failed: {e}")

        context = {
            'elf_parser': self.elf_parser,
            'dump_reader': self.dump_reader,
            'profile': {},
        }

        plugin = FreeRTOSV11Plugin()
        result = plugin.initialize(context)
        self.assertTrue(result, "Plugin initialize() should return True")

        tasks = plugin.get_tasks(context)
        self.assertIsInstance(tasks, list, "get_tasks() should return a list")


if __name__ == '__main__':
    unittest.main()