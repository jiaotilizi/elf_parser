MEMORY
{
  FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 0x00400000
  RAM (wx) : ORIGIN = 0x20000000, LENGTH = 0x00080000
}

SECTIONS
{
  .vectors :
  {
    _vectors = .;
    KEEP(*(.vectors))
  } > FLASH

  .text :
  {
    *(.text*)
    *(.rodata*)
    KEEP(*(.init))
    KEEP(*(.fini))
  } > FLASH

  __data_load_start__ = .;
  .data : AT(__data_load_start__)
  {
    __data_start__ = .;
    *(.data*)
    __data_end__ = .;
  } > RAM

  .bss :
  {
    __bss_start__ = .;
    *(.bss*)
    *(COMMON)
    __bss_end__ = .;
  } > RAM

  .stack (NOLOAD) :
  {
    . = ALIGN(4);
    __stack_start__ = .;
    . += 0x1000;
    __stack_end__ = .;
  } > RAM

  __RAM_segment_used_end__ = .;
}