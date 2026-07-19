MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
  RAM (rwx)   : ORIGIN = 0x20000000, LENGTH = 64K
}

ENTRY(main)

SECTIONS
{
  .text :
  {
    *(.text)
    *(.text.*)
  } > FLASH

  .data :
  {
    *(.data)
    *(.data.*)
    *(.rodata)
    *(.rodata.*)
  } > RAM AT> FLASH

  .bss :
  {
    *(.bss)
    *(.bss.*)
    *(COMMON)
  } > RAM
}