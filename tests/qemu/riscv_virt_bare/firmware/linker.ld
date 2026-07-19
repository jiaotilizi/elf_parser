/*
 * Linker script for QEMU sifive_e (RISC-V RV32)
 *
 * Memory map (per QEMU sifive_e mask ROM):
 *   FLASH 0x20400000 - 0x204fffff (1MB)  - code + rodata (mask ROM jumps here)
 *   RAM   0x80000000 - 0x80003fff (16KB) - data + bss (read-write)
 *
 * NOTE: sifive_e mask ROM at 0x1000 hard-codes a jump to 0x20400000,
 * not to the ELF entry point. So _start must be at 0x20400000.
 * The full flash region starts at 0x20000000 (1GB), but firmware lives at 4MB offset.
 *
 * .data LMA is in FLASH, VMA in RAM; startup copies it (no-op here since
 * shared test_firmware_bss.c has no initialized data, but kept for correctness).
 */

ENTRY(_start)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x20400000, LENGTH = 1M
  RAM   (rwx) : ORIGIN = 0x80000000, LENGTH = 16K
}

/* Top of RAM as initial stack pointer */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  /* ---- .text in FLASH ---- */
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

  /* ---- .bss in RAM ---- */
  .bss (NOLOAD) :
  {
    . = ALIGN(4);
    _sbss = .;
    *(.bss)
    *(.bss.*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
  } > RAM

  /* ---- discard unused ---- */
  /DISCARD/ :
  {
    *(.comment)
    *(.note.*)
    *(.eh_frame*)
    *(.riscv.attributes)
  }
}
