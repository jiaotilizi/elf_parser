/*
 * Linker script for NXP i.MX6UL (Cortex-A7, ARMv7-A)
 *
 * Memory map (QEMU virt default RAM):
 *   RAM 0x40000000 - 0x43ffffff (64MB)
 *
 * All-RAM layout: code + data both in RAM.
 * ARMv7-A pointers are 4 bytes; DWARF DW_TAG_pointer_type
 * DW_AT_byte_size == 4 -- used to validate 32-bit pointer parsing.
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
