"""模拟固件运行时赋值，生成 crash dump。

这个脚本做的事等同于：
  1. 固件上电 → BSS 段全部清 0
  2. firmware_init() 初始化基础变量
  3. simulate_runtime() 往 g_assert_infos / g_test_points / g_trace_buffer 填数据
  4. trigger_crash_assert() 触发 crash → dump RAM
  5. 生成 dump_bss.bin 供离线分析工具解析
"""
import os
import struct
import random
import sys
from elftools.elf.elffile import ELFFile


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ELF_PATH = os.path.join(BASE_DIR, 'test_firmware_bss.elf')
DUMP_PATH = os.path.join(BASE_DIR, 'test_dump_bss.bin')

RAM_START = 0x20000000
RAM_SIZE = 0x1000


def load_elf_symbols():
    """从 ELF 提取所有符号名→{address, size, type}。"""
    with open(ELF_PATH, 'rb') as f:
        elf = ELFFile(f)
        syms = {}
        for sec in elf.iter_sections():
            if sec.name == '.symtab':
                for s in sec.iter_symbols():
                    if s.name:
                        syms[s.name] = {
                            'address': s['st_value'],
                            'size': s['st_size'],
                            'type': 'data' if s['st_info']['type'] == 'STT_OBJECT' else 'code',
                        }
        return syms


def make_ram():
    return bytearray(RAM_SIZE)


def w_u32(ram, addr, val):
    off = addr - RAM_START
    struct.pack_into('<I', ram, off, val)


def w_u8(ram, addr, val):
    off = addr - RAM_START
    ram[off] = val & 0xFF


def w_str(ram, addr, s):
    """把字符串（含 \0）写入 ram，返回写入长度。"""
    off = addr - RAM_START
    b = s.encode('utf-8') + b'\x00'
    ram[off:off+len(b)] = b
    return len(b)


def str_pool_put(ram, pool_addr, used_ref, s):
    """模拟 str_pool_put，返回字符串首地址。"""
    used = used_ref[0]
    addr = pool_addr + used
    w_str(ram, addr, s)
    used_ref[0] += len(s) + 1
    return addr


def record_assert(ram, syms, pool_addr, used_ref, idx, file, line, func, cond, ts, task, err):
    """往 g_assert_infos[idx] 追加一条记录。"""
    base = syms['g_assert_infos']['address']
    # assert_info_t 大小: count(4) + max_count(4) + records[8]*36 = 8 + 288 = 296
    INFO_SIZE = 296
    RECORD_SIZE = 36

    ai_addr = base + idx * INFO_SIZE
    count_off = 0
    max_count_off = 4
    records_off = 8

    count = struct.unpack_from('<I', ram, ai_addr + count_off - RAM_START)[0]
    max_count = struct.unpack_from('<I', ram, ai_addr + max_count_off - RAM_START)[0]
    if count >= max_count:
        return

    rec_addr = ai_addr + records_off + count * RECORD_SIZE
    w_u32(ram, rec_addr + 0,  str_pool_put(ram, pool_addr, used_ref, file))
    w_u32(ram, rec_addr + 4,  line)
    w_u32(ram, rec_addr + 8,  str_pool_put(ram, pool_addr, used_ref, func))
    w_u32(ram, rec_addr + 12, str_pool_put(ram, pool_addr, used_ref, cond))
    w_u32(ram, rec_addr + 16, ts)
    w_u32(ram, rec_addr + 20, task)
    w_u32(ram, rec_addr + 24, err)
    # reserved[2] 保持 0

    w_u32(ram, ai_addr + count_off, count + 1)

    # g_error_count++
    ec = struct.unpack_from('<I', ram, syms['g_error_count']['address'] - RAM_START)[0]
    w_u32(ram, syms['g_error_count']['address'], ec + 1)


def record_test_point(ram, syms, pool_addr, used_ref, idx, id, name, count,
                      ts_first, ts_last, min_d, max_d, avg_d):
    base = syms['g_test_points']['address']
    TP_SIZE = 32  # 8 uint32 字段
    tp_addr = base + idx * TP_SIZE

    w_u32(ram, tp_addr + 0,  id)
    w_u32(ram, tp_addr + 4,  str_pool_put(ram, pool_addr, used_ref, name))
    w_u32(ram, tp_addr + 8,  count)
    w_u32(ram, tp_addr + 12, ts_first)
    w_u32(ram, tp_addr + 16, ts_last)
    w_u32(ram, tp_addr + 20, min_d)
    w_u32(ram, tp_addr + 24, max_d)
    w_u32(ram, tp_addr + 28, avg_d)


def record_trace(ram, syms, ts, point_id, task_id, event_type, data, write_idx_ref):
    base = syms['g_trace_buffer']['address']
    TR_SIZE = 20  # 5 uint32
    idx = write_idx_ref[0]
    tr_addr = base + idx * TR_SIZE

    w_u32(ram, tr_addr + 0,  ts)
    w_u32(ram, tr_addr + 4,  point_id)
    w_u32(ram, tr_addr + 8,  task_id)
    w_u32(ram, tr_addr + 12, event_type)
    w_u32(ram, tr_addr + 16, data)

    write_idx_ref[0] = (write_idx_ref[0] + 1) % 32


def firmware_init(ram, syms):
    """模拟 firmware_init()——BSS 全 0 之后的基础初始化。"""
    # 这些变量本就为 0，只是显式初始化 max_count
    base = syms['g_assert_infos']['address']
    INFO_SIZE = 296
    for i in range(4):
        w_u32(ram, base + i * INFO_SIZE + 4, 8)  # max_count = 8

    w_u8(ram, syms['g_system_status']['address'], 0x01)


def simulate_runtime(ram, syms, use_random=False):
    """模拟运行时填充数据。use_random=True 时用随机值生成。"""
    pool_addr = syms['g_string_pool']['address']
    used_ref = [0]
    write_idx_ref = [0]

    firmware_init(ram, syms)

    if use_random:
        rng = random.Random(42)  # 固定种子，保证可复现
        # 随机生成 assert
        files = ['main.c', 'utils.c', 'driver.c', 'network.c', 'storage.c', 'audio.c', 'display.c']
        funcs = ['task_main', 'process_data', 'init_hw', 'net_send', 'flash_write', 'audio_mix', 'lcd_refresh']
        conds = ['(ptr != NULL)', '(len > 0)', '(status == OK)', '(idx < MAX)', '(buf != NULL)', '(ret == 0)']

        for ai_idx in range(4):
            n = rng.randint(2, 6)
            for _ in range(n):
                record_assert(
                    ram, syms, pool_addr, used_ref, ai_idx,
                    file=rng.choice(files),
                    line=rng.randint(10, 999),
                    func=rng.choice(funcs),
                    cond=rng.choice(conds),
                    ts=rng.randint(1000000, 9000000),
                    task=rng.randint(0, 7),
                    err=rng.randint(0x00010000, 0x00FFFFFF),
                )

        tp_names = ['TaskIdle', 'TaskMain', 'TaskNet', 'TaskStorage',
                    'ISR_Timer', 'ISR_UART', 'TaskAudio', 'TaskDisplay']
        for i in range(8):
            count = rng.randint(500, 30000)
            ts_first = rng.randint(100000, 2000000)
            ts_last = ts_first + rng.randint(1000000, 5000000)
            min_d = rng.randint(1, 500)
            max_d = min_d + rng.randint(100, 10000)
            avg_d = (min_d + max_d) // 2
            record_test_point(
                ram, syms, pool_addr, used_ref, i,
                id=i + 1,
                name=tp_names[i],
                count=count,
                ts_first=ts_first,
                ts_last=ts_last,
                min_d=min_d,
                max_d=max_d,
                avg_d=avg_d,
            )

        for i in range(25):
            record_trace(
                ram, syms,
                ts=1000000 + i * 377,
                point_id=rng.randint(1, 8),
                task_id=rng.randint(0, 7),
                event_type=rng.randint(0, 2),
                data=rng.randint(0, 1000),
                write_idx_ref=write_idx_ref,
            )
    else:
        # 固定数据，方便测试断言
        record_assert(ram, syms, pool_addr, used_ref, 0,
                      "main.c", 128, "main", "(ptr != NULL)", 1000100, 1, 0x00010001)
        record_assert(ram, syms, pool_addr, used_ref, 0,
                      "utils.c", 256, "process_data", "(len <= MAX_LEN)", 1000200, 2, 0x00020002)
        record_assert(ram, syms, pool_addr, used_ref, 0,
                      "driver.c", 64, "init_hw", "(status == OK)", 1000050, 0, 0x00030003)

        record_assert(ram, syms, pool_addr, used_ref, 1,
                      "network.c", 512, "net_send", "(buf != NULL)", 2000300, 3, 0x01010001)
        record_assert(ram, syms, pool_addr, used_ref, 1,
                      "network.c", 620, "net_recv", "(size > 0)", 2000400, 3, 0x01020002)

        record_assert(ram, syms, pool_addr, used_ref, 2,
                      "storage.c", 128, "flash_write", "(addr < end)", 3000100, 4, 0x02010001)
        record_assert(ram, syms, pool_addr, used_ref, 2,
                      "storage.c", 256, "flash_read", "(len <= bufsize)", 3000200, 4, 0x02020002)
        record_assert(ram, syms, pool_addr, used_ref, 2,
                      "storage.c", 384, "flash_erase", "(page < MAX)", 3000300, 4, 0x02030003)

        record_assert(ram, syms, pool_addr, used_ref, 3,
                      "audio.c", 512, "audio_mix", "(ch < MAX_CH)", 4000500, 5, 0x03010001)

        tps = [
            (1, "TaskIdle",    15000, 1000000, 5000000, 10,    500,   50),
            (2, "TaskMain",     8500, 1000100, 5000200, 50,   2000,  300),
            (3, "TaskNet",      3200, 1000200, 5000400, 100,  5000,  800),
            (4, "TaskStorage",  1200, 1000500, 5000800, 200,  8000, 1500),
            (5, "ISR_Timer",   25000, 1000000, 4999999,   1,    50,    5),
            (6, "ISR_UART",    12500, 1000000, 4999000,   5,   100,   20),
            (7, "TaskAudio",    6000, 2000000, 5000100, 500,  3000, 1200),
            (8, "TaskDisplay",  4500, 2500000, 4800000, 800,  6000, 2000),
        ]
        for i, (id, name, count, ts_f, ts_l, mn, mx, avg) in enumerate(tps):
            record_test_point(ram, syms, pool_addr, used_ref, i,
                              id, name, count, ts_f, ts_l, mn, mx, avg)

        for i in range(20):
            record_trace(ram, syms,
                         ts=1000000 + i * 500,
                         point_id=(i % 8) + 1,
                         task_id=(i % 6),
                         event_type=i % 2,
                         data=i * 10,
                         write_idx_ref=write_idx_ref)

    # 最终系统状态
    w_u32(ram, syms['g_system_ticks']['address'], 5234567)
    w_u32(ram, syms['g_active_assert_idx']['address'], 2)
    w_u8(ram, syms['g_system_status']['address'], 0xFF)  # CRASH

    # 写回 g_trace_write_idx
    w_u32(ram, syms['g_trace_write_idx']['address'], write_idx_ref[0])
    # 写回 g_string_pool_used
    w_u32(ram, syms['g_string_pool_used']['address'], used_ref[0])


def main():
    use_random = '--random' in sys.argv
    syms = load_elf_symbols()

    print("=" * 70)
    print("模拟固件运行 → 生成 crash dump")
    print("=" * 70)
    print(f"ELF: {os.path.basename(ELF_PATH)}")
    print(f"模式: {'随机数据(seed=42)' if use_random else '固定数据'}")
    print(f"RAM: 0x{RAM_START:08x} - 0x{RAM_START+RAM_SIZE-1:08x} ({RAM_SIZE} bytes)")

    print(f"\nBSS 段变量（从 ELF 读取地址）：")
    bss_syms = [(n, i) for n, i in syms.items()
                if n.startswith('g_') and i['type'] == 'data']
    for name, info in sorted(bss_syms, key=lambda x: x[1]['address']):
        print(f"  {name:<25} @ 0x{info['address']:08x}  size={info['size']}")

    # 全 0 的 BSS 段
    ram = make_ram()
    simulate_runtime(ram, syms, use_random=use_random)

    with open(DUMP_PATH, 'wb') as f:
        f.write(ram)

    print(f"\n✓ 生成 dump: {os.path.basename(DUMP_PATH)} ({len(ram)} bytes)")

    # 打印几个关键值，方便验证
    print(f"\n关键快照：")
    base = syms['g_assert_infos']['address']
    for i in range(4):
        info_addr = base + i * 296
        cnt = struct.unpack_from('<I', ram, info_addr - RAM_START)[0]
        print(f"  g_assert_infos[{i}].count = {cnt}")

    print(f"  g_system_ticks     = {struct.unpack_from('<I', ram, syms['g_system_ticks']['address'] - RAM_START)[0]}")
    print(f"  g_system_status    = 0x{struct.unpack_from('B', ram, syms['g_system_status']['address'] - RAM_START)[0]:02x}")
    print(f"  g_error_count      = {struct.unpack_from('<I', ram, syms['g_error_count']['address'] - RAM_START)[0]}")
    print(f"  g_trace_write_idx  = {struct.unpack_from('<I', ram, syms['g_trace_write_idx']['address'] - RAM_START)[0]}")


if __name__ == '__main__':
    main()
