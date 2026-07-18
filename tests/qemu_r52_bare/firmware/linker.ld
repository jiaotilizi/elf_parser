/*
 * Linker script for QEMU mps3-an536 (Cortex-R52)
 *
 * 内存映射（MPS3-AN536）：
 *   SRAM 0x20000000 - 0x203fffff (4MB)
 *
 * 全 RAM 布局：代码+数据都在 SRAM，无需 Flash/RAM 分离。
 * _sidata = _sdata 表示 .data 的 LMA = VMA（copy 是 no-op）。
 */

ENTRY(_start)

MEMORY
{
  RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 4M
}

/* RAM 顶部，作为初始栈指针 */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  /* ── 代码段 ─────────────────────────────────────── */
  .text :
  {
    . = ALIGN(4);
    KEEP(*(.text.startup))
    *(.text)
    *(.text.*)
    *(.rodata)
    *(.rodata.*)
    . = ALIGN(4);
    _etext = .;
  } > RAM

  /* ── data 段（LMA = VMA，无 copy）─────────────────── */
  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(4);
    _sdata = .;
    *(.data)
    *(.data.*)
    . = ALIGN(4);
    _edata = .;
  } > RAM AT> RAM

  /* ── bss 段 ─────────────────────────────────────── */
  .bss :
  {
    . = ALIGN(4);
    _sbss = .;
    *(.bss)
    *(.bss.*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
  } > RAM

  /* ── 丢弃不用的段 ───────────────────────────────── */
  /DISCARD/ :
  {
    *(.ARM.exidx*)
    *(.ARM.extab*)
    *(.comment)
    *(.note.*)
  }
}
