#!/usr/bin/env python3
"""Show parsed result for NXP i.MX6UL + ThreadX firmware."""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase


class ShowNxpImx6ulThreadX(ShowParsedBase):
    BANNER_TITLE = 'NXP i.MX6UL (Cortex-A7) + ThreadX Crash Dump 自动恢复'
    BANNER_LINES = [
        '  芯片 : NXP i.MX6UL (Cortex-A7, ARMv7-A)',
        '  RTOS : ThreadX V6.5.1',
        '  平台 : QEMU virt machine',
    ]
    FOOTER_LINES = [
        '★ 验证要点: ARMv7-A 架构下 ThreadX TX_THREAD/TX_QUEUE 解析',
    ]

    def show_system_status(self):
        print("\n" + "─" * 78)
        print("【1】ThreadX 内核状态")
        print("─" * 78)
        state = self.elf_parser.parse_struct_auto('_tx_thread_system_state', self.dump_reader)
        current_ptr = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        ticks = self.elf_parser.parse_struct_auto('_tx_time_current', self.dump_reader)
        
        state_map = {0: 'TX_INITIALIZE_IS_FINISHED', 1: 'TX_INITIALIZE_IN_PROGRESS'}
        print(f"  _tx_thread_system_state = {state}  ({state_map.get(state, 'UNKNOWN')})")
        print(f"  _tx_time_current        = {ticks}  (系统 tick 数)")
        if current_ptr is not None:
            name = current_ptr.get('tx_thread_name', 'unknown')
            print(f"  当前运行线程             = {name!r}")
        else:
            print(f"  当前运行线程             = NULL")

    def show_assert_infos(self):
        print("\n" + "─" * 78)
        print("【2】ThreadX 任务列表")
        print("─" * 78)
        try:
            from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
            context = {
                'elf_parser': self.elf_parser,
                'dump_reader': self.dump_reader,
                'profile': {},
            }
            plugin = ThreadXV6Plugin()
            plugin.initialize(context)
            result = plugin.execute(context)
            tasks = result.get('tasks', [])
            print(f"  共 {len(tasks)} 个线程")
            print(f"  {'名称':<12} {'优先级':>8} {'状态':<10} {'运行计数':>10}")
            print(f"  {'─'*12} {'─'*8} {'─'*10} {'─'*10}")
            for task in tasks[:10]:
                name = task.get('name', 'unknown')
                prio = task.get('priority', 'N/A')
                state = task.get('state', 'N/A')
                count = task.get('run_count', 0)
                print(f"  {name:<12} {prio:>8} {state:<10} {count:>10}")
        except Exception as e:
            print(f"  插件加载失败: {e}")

    def show_test_points(self):
        print("\n" + "─" * 78)
        print("【3】ThreadX 同步原语")
        print("─" * 78)
        try:
            from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
            context = {
                'elf_parser': self.elf_parser,
                'dump_reader': self.dump_reader,
                'profile': {},
            }
            plugin = ThreadXV6Plugin()
            plugin.initialize(context)
            result = plugin.execute(context)
            
            semaphores = result.get('semaphores', [])
            mutexes = result.get('mutexes', [])
            queues = result.get('queues', [])
            events = result.get('events', [])
            timers = result.get('timers', [])
            
            print(f"  信号量 : {len(semaphores)} 个")
            print(f"  互斥锁 : {len(mutexes)} 个")
            print(f"  队列   : {len(queues)} 个")
            print(f"  事件组 : {len(events)} 个")
            print(f"  定时器 : {len(timers)} 个")
            
            if queues:
                print("\n  队列详情:")
                for q in queues:
                    name = q.get('name', 'unknown')
                    messages = q.get('messages', 0)
                    max_msgs = q.get('max_messages', 0)
                    print(f"    - {name!r}: {messages}/{max_msgs} 消息")
                    
            if semaphores:
                print("\n  信号量详情:")
                for s in semaphores:
                    name = s.get('name', 'unknown')
                    count = s.get('count', 0)
                    print(f"    - {name!r}: count={count}")
                    
        except Exception as e:
            print(f"  插件加载失败: {e}")

    def show_trace_buffer(self):
        print("\n" + "─" * 78)
        print("【4】ThreadX 字节池和块池")
        print("─" * 78)
        try:
            from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
            context = {
                'elf_parser': self.elf_parser,
                'dump_reader': self.dump_reader,
                'profile': {},
            }
            plugin = ThreadXV6Plugin()
            plugin.initialize(context)
            result = plugin.execute(context)
            
            byte_pools = result.get('byte_pools', [])
            block_pools = result.get('block_pools', [])
            
            print(f"  字节池 : {len(byte_pools)} 个")
            print(f"  块池   : {len(block_pools)} 个")
            
            if byte_pools:
                print("\n  字节池详情:")
                for bp in byte_pools:
                    name = bp.get('name', 'unknown')
                    size = bp.get('total_bytes', 0)
                    used = bp.get('used_bytes', 0)
                    print(f"    - {name!r}: {used}/{size} 字节")
                    
        except Exception as e:
            print(f"  插件加载失败: {e}")


def main():
    scenario_dir = os.path.dirname(os.path.abspath(__file__))
    elf_filename = 'output/img/test_firmware_nxp_imx6ul_threadx.elf'
    dump_filename = 'output/img/test_dump_nxp_imx6ul_threadx.bin'
    profile_name = 'qemu/nxp_imx6ul_threadx'

    show = ShowNxpImx6ulThreadX(
        scenario_dir=scenario_dir,
        elf_filename=elf_filename,
        dump_filename=dump_filename,
        profile_name=profile_name,
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())