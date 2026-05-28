from __future__ import annotations

from lab4.binary import ProgramImage, decode_program


def disassemble_code(code: bytes) -> str:
    lines: list[str] = []
    for address, instruction, raw_instruction in decode_program(code):
        hex_code = raw_instruction.hex(" ").upper()
        lines.append(f"{address:04X} - {hex_code:<32} - {instruction.to_mnemonic()}")
    return "\n".join(lines)


def disassemble_image(image: ProgramImage) -> str:
    lines = [
        f"entry: 0x{image.entry_point:08X}",
        "",
        "instruction memory:",
        disassemble_code(image.code),
        "",
        "data memory:",
    ]
    if image.data:
        lines.extend(
            f"{index:04X} - 0x{word & 0xFFFF_FFFF:08X} - {word}"
            for index, word in enumerate(image.data)
        )
    else:
        lines.append("<empty>")

    lines.extend(["", "interrupt vectors:"])
    if image.interrupt_vectors:
        lines.extend(
            f"{index:04X} - 0x{address:08X}"
            for index, address in enumerate(image.interrupt_vectors)
        )
    else:
        lines.append("<empty>")
    return "\n".join(lines)
