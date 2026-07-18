/*
 * Linker script for QEMU mps2-an386 (Cortex-M4) + FreeRTOS
 *
 * Memory map (MPS2-AN386):
 *   FLASH 0x00000000 - 0x003fffff (ssram1, 4MB)
 *   RAM   0x20000000 - 0x2003ffff (256K reserved, enough for heap_4 32K
 *          + 4 task stacks 1K each + kernel data + queues)
 */

ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 4M
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 256K
}

/* Top of RAM as initial stack pointer */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  /* ---- Vector table at start of FLASH ---- */
  .isr_vector :
  {
    . = ALIGN(4);
    KEEP(*(.isr_vector))
    . = ALIGN(4);
  } > FLASH

  /* ---- Code + rodata in FLASH ---- */
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

  /* ---- .data: VMA in RAM, LMA in FLASH ---- */
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

  /* ---- .bss in RAM (zero-initialized by Reset_Handler) ---- */
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

  /* ---- Discard unused sections ---- */
  /DISCARD/ :
  {
    *(.ARM.exidx*)
    *(.ARM.extab*)
    *(.comment)
    *(.note.*)
  }
}
