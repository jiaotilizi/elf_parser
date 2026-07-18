/*
 * Linker script for QEMU virt (Cortex-A53 / AArch64)
 *
 * Memory map (QEMU virt default RAM):
 *   RAM 0x40000000 - 0x43ffffff (64MB)
 *
 * All-RAM layout (same as R52): code + data both in RAM.
 * AArch64 pointers are 8 bytes; DWARF DW_TAG_pointer_type
 * DW_AT_byte_size == 8 -- used to validate 64-bit pointer parsing.
 */

ENTRY(_start)

MEMORY
{
  RAM (rwx) : ORIGIN = 0x40000000, LENGTH = 64M
}

/* Top of RAM as initial stack pointer */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  /* ---- .text ---- */
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

  /* ---- .data (LMA = VMA, copy is no-op) ---- */
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

  /* ---- .bss ---- */
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

  /* ---- discard unused sections ---- */
  /DISCARD/ :
  {
    *(.comment)
    *(.note.*)
    *(.eh_frame*)
  }
}
