import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUMps2An386ThreadXFirmwareAutoParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.firmware_dir = os.path.join(os.path.dirname(__file__), 'firmware')
        cls.elf_path = os.path.join(cls.firmware_dir, 'output', 'img', 'sample_threadx.elf')
        cls.dump_path = os.path.join(cls.firmware_dir, 'output', 'img', 'threadx_ram_dump.bin')

        assert os.path.exists(cls.elf_path), f"ELF not found: {cls.elf_path}"
        assert os.path.exists(cls.dump_path), f"Dump not found: {cls.dump_path}"

        loader = ProfileLoader()
        profile = loader.load_profile('profiles/qemu/mps2_an386_threadx.yaml')
        regions = loader.get_memory_regions(profile)

        cls.elf_parser = ELFParser(cls.elf_path)
        cls.dump_reader = DumpReader(cls.dump_path, regions)
        cls.keywords = profile.get('keyword', [])

    def test_keyword_match(self):
        if not self.keywords:
            self.skipTest("No keywords defined in profile")

        elf_unmatched = self.elf_parser.match_keywords(self.keywords)
        self.assertEqual(len(elf_unmatched), 0,
                        f"Keyword match failed: ELF unmatched={elf_unmatched}")

    def test_threadx_thread_control_block_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_THREAD'),
                             "TX_THREAD type should exist in DWARF")

    def test_threadx_current_thread_non_null(self):
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        self.assertIsNotNone(current_tcb, "Current thread pointer should not be NULL")
        self.assertIsInstance(current_tcb, dict,
                            "Dereferenced TCB should be a dict of TX_THREAD fields")

    def test_threadx_current_thread_tcb_fields(self):
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        if current_tcb is None:
            self.skipTest("_tx_thread_current_ptr is NULL, cannot test TCB fields")
        self.assertIsInstance(current_tcb, dict)
        self.assertIn('tx_thread_name', current_tcb,
                      "TX_THREAD should have tx_thread_name field")

    def test_threadx_created_thread_count(self):
        thread_count = 0
        symbols = self.elf_parser.get_all_symbols()
        for sym in symbols:
            name = sym['name']
            if name.startswith('thread_') and not name.endswith('_counter') and not name.endswith('_entry'):
                addr = sym['address']
                if addr is not None and 0x20000000 <= addr < 0x20800000:
                    thread_count += 1
        self.assertGreaterEqual(thread_count, 8, "At least 8 threads should exist")

    def test_threadx_semaphore_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_SEMAPHORE'),
                             "TX_SEMAPHORE type should exist")

    def test_threadx_mutex_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_MUTEX'),
                             "TX_MUTEX type should exist")

    def test_threadx_queue_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_QUEUE'),
                             "TX_QUEUE type should exist")

    def test_threadx_event_flags_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_EVENT_FLAGS_GROUP'),
                             "TX_EVENT_FLAGS_GROUP type should exist")

    def test_threadx_byte_pool_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_BYTE_POOL'),
                             "TX_BYTE_POOL type should exist")

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

        # 10 个用户线程 + System Timer Thread = 11（dump 时机可能尚未全部创建）
        self.assertGreaterEqual(len(tasks), 9,
                               f"Expected at least 9 threads, got {len(tasks)}")

        by_name = {t['name']: t for t in tasks if t.get('name')}

        # 验证所有用户线程存在且优先级正确（来自 sample_threadx.c）
        # 注：thread 8/9 可能因 dump 时机未创建，仅检查 thread 0-7
        expected = {
            'thread 0': 1,
            'thread 1': 16,
            'thread 2': 16,
            'thread 3': 8,
            'thread 4': 8,
            'thread 5': 4,
            'thread 6': 8,
            'thread 7': 8,
        }
        for name, expected_priority in expected.items():
            self.assertIn(name, by_name, f"Thread '{name}' should exist")
            self.assertEqual(by_name[name]['priority'], expected_priority,
                           f"Thread '{name}' priority should be {expected_priority}")

        # System Timer Thread
        self.assertIn('System Timer Thread', by_name,
                     "System Timer Thread should exist")

        # 所有线程栈大小应为 1024
        for task in tasks:
            if task.get('name', '').startswith('thread '):
                self.assertEqual(task.get('stack_size', 0), 1024,
                               f"Thread '{task.get('name')}' stack_size should be 1024")

    def test_plugin_semaphore_data(self):
        """验证信号量数据：名称、初始计数。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        semaphores = result['semaphores']

        by_name = {s['name']: s for s in semaphores if s.get('name')}

        self.assertGreaterEqual(len(semaphores), 2,
                               f"Expected at least 2 semaphores, got {len(semaphores)}")
        self.assertIn('semaphore 0', by_name, "semaphore 0 should exist")
        self.assertIn('semaphore 1', by_name, "semaphore 1 should exist")

    def test_plugin_mutex_data(self):
        """验证互斥锁数据：名称。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        mutexes = result['mutexes']

        by_name = {m['name']: m for m in mutexes if m.get('name')}

        self.assertEqual(len(mutexes), 2, f"Expected 2 mutexes, got {len(mutexes)}")
        self.assertIn('mutex 0', by_name, "mutex 0 should exist")
        self.assertIn('mutex 1', by_name, "mutex 1 should exist")

    def test_plugin_queue_data(self):
        """验证队列数据：名称、容量。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        queues = result['queues']

        by_name = {q['name']: q for q in queues if q.get('name')}

        self.assertEqual(len(queues), 2, f"Expected 2 queues, got {len(queues)}")

        self.assertIn('queue 0', by_name, "queue 0 should exist")
        self.assertEqual(by_name['queue 0']['max_messages'], 100,
                        "queue 0 capacity should be 100")

        self.assertIn('queue 1', by_name, "queue 1 should exist")
        self.assertEqual(by_name['queue 1']['max_messages'], 10,
                        "queue 1 capacity should be 10")

    def test_plugin_event_data(self):
        """验证事件组数据：名称。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        events = result['events']

        by_name = {e['name']: e for e in events if e.get('name')}

        self.assertGreaterEqual(len(events), 2,
                               f"Expected at least 2 event groups, got {len(events)}")
        self.assertIn('event flags 0', by_name, "event flags 0 should exist")
        self.assertIn('event flags 1', by_name, "event flags 1 should exist")

    def test_plugin_timer_data(self):
        """验证定时器数据：名称、周期。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        timers = result['timers']

        by_name = {t['name']: t for t in timers if t.get('name')}

        self.assertEqual(len(timers), 2, f"Expected 2 timers, got {len(timers)}")

        # timer 0: periodic, period=10 ticks
        self.assertIn('timer 0', by_name, "timer 0 should exist")
        self.assertEqual(by_name['timer 0']['period_ticks'], 10,
                        "timer 0 period_ticks should be 10")

        # timer 1: one-shot (50, 0)，已过期后 reschedule_ticks=0，不检查具体值
        self.assertIn('timer 1', by_name, "timer 1 should exist")

    def test_plugin_block_pool_data(self):
        """验证块池数据：名称、块大小、总数。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        block_pools = result['block_pools']

        by_name = {b['name']: b for b in block_pools if b.get('name')}

        self.assertGreaterEqual(len(block_pools), 1,
                               f"Expected at least 1 block pool, got {len(block_pools)}")
        self.assertIn('block pool 0', by_name, "block pool 0 should exist")
        self.assertEqual(by_name['block pool 0']['block_size'], 4,
                        "block pool 0 block_size should be sizeof(ULONG)=4")
        self.assertEqual(by_name['block pool 0']['total_blocks'], 12,
                        "block pool 0 total_blocks should be 12")

    def test_plugin_byte_pool_data(self):
        """验证字节池数据：名称、总大小。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        byte_pools = result['byte_pools']

        by_name = {b['name']: b for b in byte_pools if b.get('name')}

        self.assertGreaterEqual(len(byte_pools), 1,
                               f"Expected at least 1 byte pool, got {len(byte_pools)}")
        self.assertIn('byte pool 0', by_name, "byte pool 0 should exist")
        self.assertEqual(by_name['byte pool 0']['total_bytes'], 9120,
                        "byte pool 0 total_bytes should be 9120")

    def test_plugin_execute_all_resource_types(self):
        """验证 execute() 返回所有 8 种资源类型。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)

        self.assertIsInstance(result, dict)
        for rt in ['tasks', 'semaphores', 'mutexes', 'queues', 'events',
                    'timers', 'block_pools', 'byte_pools']:
            self.assertIn(rt, result, f"execute() should include '{rt}'")
            self.assertIsInstance(result[rt], list, f"'{rt}' should be a list")


if __name__ == '__main__':
    unittest.main()
