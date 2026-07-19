ENTRY(_start)

MEMORY
{
  RAM (rwx) : ORIGIN = 0x40000000, LENGTH = 256K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  __vectors = ORIGIN(RAM);
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

  .data :
  {
    . = ALIGN(16);
    _sdata = .;
    *(.data)
    *(.data.*)
    . = ALIGN(16);
    _edata = .;
  } > RAM

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

  .stack (NOLOAD) :
  {
    _stack_bottom = .;
    . = ALIGN(8);
    . += 16384;
    _sp = . - 16;
    _stack_top = .;
  } > RAM

  _end = .;
  __end__ = .;

  /DISCARD/ :
  {
    *(.comment)
    *(.note.*)
    *(.eh_frame*)
  }
}
