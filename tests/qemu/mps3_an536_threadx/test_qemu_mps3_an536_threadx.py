import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.elf_parser import ELFParserFactory
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUMps3An536ThreadXFirmwareAutoParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.firmware_dir = os.path.join(os.path.dirname(__file__), 'firmware')
        cls.elf_path = os.path.join(cls.firmware_dir, 'output', 'img', 'sample_threadx.elf')
        cls.dump_path = os.path.join(cls.firmware_dir, 'output', 'img', 'threadx_ram_dump.bin')

        assert os.path.exists(cls.elf_path), f"ELF not found: {cls.elf_path}"
        assert os.path.exists(cls.dump_path), f"Dump not found: {cls.dump_path}"

        loader = ProfileLoader()
        profile = loader.load_profile('profiles/qemu/mps3_an536_threadx.yaml')
        regions = loader.get_memory_regions(profile)

        cls.elf_parser = ELFParserFactory.create(cls.elf_path, 'elftools')
        cls.dump_reader = DumpReader(cls.dump_path, regions)
        cls.keywords = profile.get('keyword', [])

    def test_keyword_match(self):
        if not self.keywords:
            self.skipTest("No keywords defined in profile")

        elf_unmatched = self.elf_parser.match_keywords(self.keywords)
        self.assertEqual(len(elf_unmatched), 0,
                        f"Keyword match failed: ELF unmatched={elf_unmatched}")

    def test_threadx_thread_control_block_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_THREAD'), "TX_THREAD type should exist in DWARF")

    def test_threadx_current_thread_non_null(self):
        current_ptr_sym = self.elf_parser.get_symbol_by_name('_tx_thread_current_ptr')
        if current_ptr_sym is None:
            self.skipTest("_tx_thread_current_ptr symbol not found")
        
        current_ptr_value = self.dump_reader.read_uint32(current_ptr_sym['address'])
        
        if current_ptr_value == 0:
            self.skipTest("_tx_thread_current_ptr is NULL (may be captured during scheduler switch)")
        
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        self.assertIsNotNone(current_tcb, "Dereferenced TCB should not be None")
        self.assertIsInstance(current_tcb, dict,
                            "Dereferenced TCB should be a dict of TX_THREAD fields")

    def test_threadx_current_thread_tcb_fields(self):
        """验证 TCB 指针解引用后能拿到 TX_THREAD 的关键字段"""
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        if current_tcb is None:
            self.skipTest("_tx_thread_current_ptr is NULL, cannot test TCB fields")
        self.assertIsInstance(current_tcb, dict)
        self.assertIn('tx_thread_name', current_tcb,
                      "TX_THREAD should have tx_thread_name field")

    def test_threadx_system_state_finished(self):
        # _tx_thread_system_state 是 ULONG 标量，parse_struct_auto 直接返回整数值
        state = self.elf_parser.parse_struct_auto('_tx_thread_system_state', self.dump_reader)
        self.assertEqual(state, 0, "ThreadX system state should be 0 (TX_INITIALIZE_IS_FINISHED)")

    def test_threadx_created_thread_count(self):
        thread_count = 0
        symbols = self.elf_parser.get_all_symbols()
        for sym in symbols:
            name = sym['name']
            if name.startswith('thread_') and not name.endswith('_counter') and not name.endswith('_entry'):
                addr = sym['address']
                if addr is not None and 0x20000000 <= addr < 0x20400000:
                    thread_count += 1
        self.assertGreaterEqual(thread_count, 8, "At least 8 threads should exist")

    def test_threadx_semaphore_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_SEMAPHORE'), "TX_SEMAPHORE type should exist")

    def test_threadx_mutex_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_MUTEX'), "TX_MUTEX type should exist")

    def test_threadx_queue_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_QUEUE'), "TX_QUEUE type should exist")

    def test_threadx_event_flags_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_EVENT_FLAGS_GROUP'), "TX_EVENT_FLAGS_GROUP type should exist")

    def test_threadx_timer_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_TIMER'), "TX_TIMER type should exist")

    def test_threadx_byte_pool_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_BYTE_POOL'), "TX_BYTE_POOL type should exist")

    def _get_plugin(self):
        """Helper: load and initialize the ThreadX plugin."""
        from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
        plugin = ThreadXV6Plugin()
        context = {
            'elf_parser': self.elf_parser,
            'dump_reader': self.dump_reader,
            'profile': {},
        }
        self.assertTrue(plugin.initialize(context), "Plugin initialize() should return True")
        return plugin, context

    # ========================================================================
    # 数据准确性检查 — 通过插件 execute() 验证资源的数据值
    # 基于 sample_threadx.c 中的 tx_thread_create / tx_queue_create 等参数
    # ========================================================================

    def test_plugin_task_data(self):
        """验证线程数据：名称、优先级、数量是否与固件源码一致。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        tasks = result['tasks']

        self.assertGreaterEqual(len(tasks), 10,
                               f"Expected at least 10 threads, got {len(tasks)}")

        by_name = {t['name']: t for t in tasks if t.get('name')}

        expected = {
            'thread 0': 1, 'thread 1': 16, 'thread 2': 16, 'thread 3': 8,
            'thread 4': 8, 'thread 5': 4, 'thread 6': 8, 'thread 7': 8,
            'thread 8': 2, 'thread 9': 3,
        }
        for name, expected_priority in expected.items():
            self.assertIn(name, by_name, f"Thread '{name}' should exist")
            self.assertEqual(by_name[name]['priority'], expected_priority,
                           f"Thread '{name}' priority should be {expected_priority}")

        self.assertIn('System Timer Thread', by_name, "System Timer Thread should exist")

        for task in tasks:
            if task.get('name', '').startswith('thread '):
                self.assertEqual(task.get('stack_size', 0), 1024)

    def test_plugin_semaphore_data(self):
        plugin, context = self._get_plugin()
        semaphores = plugin.execute(context)['semaphores']
        by_name = {s['name']: s for s in semaphores if s.get('name')}
        self.assertGreaterEqual(len(semaphores), 2)
        self.assertIn('semaphore 0', by_name)
        self.assertIn('semaphore 1', by_name)

    def test_plugin_mutex_data(self):
        plugin, context = self._get_plugin()
        mutexes = plugin.execute(context)['mutexes']
        by_name = {m['name']: m for m in mutexes if m.get('name')}
        self.assertEqual(len(mutexes), 2)
        self.assertIn('mutex 0', by_name)
        self.assertIn('mutex 1', by_name)

    def test_plugin_queue_data(self):
        plugin, context = self._get_plugin()
        queues = plugin.execute(context)['queues']
        by_name = {q['name']: q for q in queues if q.get('name')}
        self.assertEqual(len(queues), 2)
        self.assertIn('queue 0', by_name)
        self.assertEqual(by_name['queue 0']['max_messages'], 100)
        self.assertIn('queue 1', by_name)
        self.assertEqual(by_name['queue 1']['max_messages'], 10)

    def test_plugin_event_data(self):
        plugin, context = self._get_plugin()
        events = plugin.execute(context)['events']
        by_name = {e['name']: e for e in events if e.get('name')}
        self.assertGreaterEqual(len(events), 2)
        self.assertIn('event flags 0', by_name)
        self.assertIn('event flags 1', by_name)

    def test_plugin_timer_data(self):
        plugin, context = self._get_plugin()
        timers = plugin.execute(context)['timers']
        by_name = {t['name']: t for t in timers if t.get('name')}
        self.assertEqual(len(timers), 2)
        self.assertIn('timer 0', by_name)
        self.assertEqual(by_name['timer 0']['period_ticks'], 10)
        self.assertIn('timer 1', by_name)
        self.assertEqual(by_name['timer 1']['period_ticks'], 100)

    def test_plugin_block_pool_data(self):
        plugin, context = self._get_plugin()
        block_pools = plugin.execute(context)['block_pools']
        by_name = {b['name']: b for b in block_pools if b.get('name')}
        self.assertGreaterEqual(len(block_pools), 1)
        self.assertIn('block pool 0', by_name)
        self.assertEqual(by_name['block pool 0']['block_size'], 4)
        self.assertEqual(by_name['block pool 0']['total_blocks'], 12)

    def test_plugin_byte_pool_data(self):
        plugin, context = self._get_plugin()
        byte_pools = plugin.execute(context)['byte_pools']
        by_name = {b['name']: b for b in byte_pools if b.get('name')}
        self.assertGreaterEqual(len(byte_pools), 1)
        self.assertIn('byte pool 0', by_name)
        self.assertEqual(by_name['byte pool 0']['total_bytes'], 9120)

    def test_plugin_execute_all_resource_types(self):
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        self.assertIsInstance(result, dict)
        for rt in ['tasks', 'semaphores', 'mutexes', 'queues', 'events',
                    'timers', 'block_pools', 'byte_pools']:
            self.assertIn(rt, result, f"execute() should include '{rt}'")
            self.assertIsInstance(result[rt], list, f"'{rt}' should be a list")


if __name__ == '__main__':
    unittest.main()
