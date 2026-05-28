from __future__ import annotations

import pytest

from lab4.binary import (
    ProgramImage,
    decode_instruction,
    decode_program,
    encode_instruction,
    encode_program,
)
from lab4.disasm import disassemble_image
from lab4.isa import IO_OUTPUT_DATA, Instruction, OpCode, Operand


def test_instruction_roundtrip_with_variable_length_operands() -> None:
    instruction = Instruction(
        OpCode.ADD,
        (
            Operand.ind_areg_disp(6, -4),
            Operand.dreg(0),
        ),
    )

    raw = encode_instruction(instruction)
    decoded, next_offset = decode_instruction(raw)

    assert decoded == instruction
    assert next_offset == len(raw)
    assert len(raw) == 2 + 1 + 1 + 4 + 1 + 1


def test_program_roundtrip() -> None:
    instructions = [
        Instruction(OpCode.MOVE, (Operand.imm(65), Operand.dreg(0))),
        Instruction(OpCode.MOVE, (Operand.dreg(0), Operand.abs(IO_OUTPUT_DATA))),
        Instruction(OpCode.HALT),
    ]

    raw = encode_program(instructions)
    decoded = [instruction for _, instruction, _ in decode_program(raw)]

    assert decoded == instructions


def test_image_roundtrip_with_harvard_sections() -> None:
    code = encode_program(
        [
            Instruction(OpCode.JMP, (Operand.abs(10),)),
            Instruction(OpCode.HALT),
        ],
    )
    image = ProgramImage(
        entry_point=0, code=code, data=(5, 72, 101, 108, 108, 111), interrupt_vectors=(42,)
    )

    decoded = ProgramImage.from_bytes(image.to_bytes())

    assert decoded == image


def test_disassemble_image_contains_code_data_and_interrupt_vectors() -> None:
    code = encode_program([Instruction(OpCode.MOVE, (Operand.imm(1), Operand.dreg(0)))])
    image = ProgramImage(entry_point=0, code=code, data=(1, 2), interrupt_vectors=(8,))

    text = disassemble_image(image)

    assert "instruction memory" in text
    assert "move #1, D0" in text
    assert "data memory" in text
    assert "0001 - 0x00000002 - 2" in text
    assert "interrupt vectors" in text
    assert "0000 - 0x00000008" in text


def test_decode_rejects_truncated_instruction() -> None:
    with pytest.raises(ValueError, match="unexpected end"):
        decode_instruction(bytes([OpCode.MOVE, 1, 1]))
