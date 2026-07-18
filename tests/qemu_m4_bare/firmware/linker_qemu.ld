/*
 * Linker script for QEMU mps2-an386 (Cortex-M4)
 *
 * 内存映射（MPS2-AN386）：
 *   FLASH 0x00000000 - 0x003fffff (ssram1, 4MB)
 *   RAM   0x20000000 - 0x203fffff (ssram23, 4MB)
 */

ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 4M
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 4M
}

/* RAM 顶部，作为初始栈指针 */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  /* ── 向量表 ── 放在 Flash 最前 ─────────────────────── */
  .isr_vector :
  {
    . = ALIGN(4);
    KEEP(*(.isr_vector))
    . = ALIGN(4);
  } > FLASH

  /* ── 代码段 ─────────────────────────────────────── */
  .text :
  {
    . = ALIGN(4);
    *(.text)
    *(.text.*)
    *(.rodata)
    *(.rodata.*)
    . = ALIGN(4);
    _etext = .;
  } > FLASH

  /* ── data 段 VMA 在 RAM，LMA 紧跟在 .text 之后 ── */
  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(4);
    _sdata = .;
    *(.data)
    *(.data.*)
    . = ALIGN(4);
    _edata = .;
  } > RAM AT> FLASH

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
