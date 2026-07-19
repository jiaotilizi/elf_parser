/*
 * Linker script for NXP i.MX6UL (Cortex-A7, ARMv7-A) + FreeRTOS
 */

ENTRY(_start)

MEMORY
{
  RAM (rwx) : ORIGIN = 0x40000000, LENGTH = 64M
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  .text :
  {
    . = ALIGN(16);
    KEEP(*(.text.startup))
    *(.text)
    *(.text.*)
    *(.rodata)
    *(.rodata.*)
    . = ALIGN(16);
    _etext = .;
  } > RAM

  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(16);
    _sdata = .;
    *(.data)
    *(.data.*)
    . = ALIGN(16);
    _edata = .;
  } > RAM AT> RAM

  .bss (NOLOAD) :
  {
    . = ALIGN(16);
    _sbss = .;
    *(.bss)
    *(.bss.*)
    *(COMMON)
    . = ALIGN(16);
    _ebss = .;
  } > RAM

  /DISCARD/ :
  {
    *(.comment)
    *(.note.*)
    *(.eh_frame*)
  }
}
