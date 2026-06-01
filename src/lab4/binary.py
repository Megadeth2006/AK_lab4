from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Final, assert_never

from lab4.isa import Instruction, OpCode, Operand, OperandKind, to_i32, to_u32

MAGIC: Final[bytes] = b"L4HB"  # Lab 4, Harvard, binary
VERSION: Final[int] = 1
_HEADER = struct.Struct("<4sB3xIIII")
_U8 = struct.Struct("<B")
_I32 = struct.Struct("<i")
_U32 = struct.Struct("<I")


@dataclass(frozen=True, slots=True)
class ProgramImage:
    entry_point: int
    code: bytes
    data: tuple[int, ...] = ()
    interrupt_vectors: tuple[int, ...] = ()

    def to_bytes(self) -> bytes:
        header = _HEADER.pack(
            MAGIC,
            VERSION,
            self.entry_point,
            len(self.code),
            len(self.data),
            len(self.interrupt_vectors),
        )
        data = b"".join(_I32.pack(to_i32(word)) for word in self.data)
        vectors = b"".join(_U32.pack(vector) for vector in self.interrupt_vectors)
        return header + self.code + data + vectors

    @staticmethod
    def from_bytes(raw: bytes) -> ProgramImage:
        if len(raw) < _HEADER.size:
            msg = "binary image is shorter than header"
            raise ValueError(msg)

        magic, version, entry_point, code_size, data_count, vector_count = _HEADER.unpack_from(raw)
        if magic != MAGIC:
            msg = f"bad magic: expected {MAGIC!r}, got {magic!r}"
            raise ValueError(msg)
        if version != VERSION:
            msg = f"unsupported binary image version: {version}"
            raise ValueError(msg)

        code_start = _HEADER.size
        code_end = code_start + code_size
        data_start = code_end
        data_end = data_start + data_count * _I32.size
        vectors_start = data_end
        vectors_end = vectors_start + vector_count * _U32.size

        if len(raw) != vectors_end:
            msg = f"binary image size mismatch: expected {vectors_end}, got {len(raw)}"
            raise ValueError(msg)

        code = raw[code_start:code_end]
        data = tuple(
            _I32.unpack_from(raw, data_start + i * _I32.size)[0] for i in range(data_count)
        )
        vectors = tuple(
            _U32.unpack_from(raw, vectors_start + i * _U32.size)[0] for i in range(vector_count)
        )
        return ProgramImage(entry_point, code, data, vectors)


def encode_instruction(instruction: Instruction) -> bytes:
    result = bytearray()
    result.extend(_U8.pack(instruction.opcode.value))
    result.extend(_U8.pack(len(instruction.operands)))
    for operand in instruction.operands:
        result.extend(encode_operand(operand))
    return bytes(result)


def encode_program(instructions: list[Instruction]) -> bytes:
    return b"".join(encode_instruction(instruction) for instruction in instructions)


def decode_instruction(raw: bytes, offset: int = 0) -> tuple[Instruction, int]:
    _require_size(raw, offset, 2)
    opcode = OpCode(_U8.unpack_from(raw, offset)[0])
    operand_count = _U8.unpack_from(raw, offset + 1)[0]
    cursor = offset + 2
    operands: list[Operand] = []
    for _ in range(operand_count):
        operand, cursor = decode_operand(raw, cursor)
        operands.append(operand)
    return Instruction(opcode, tuple(operands)), cursor


def decode_program(raw: bytes) -> list[tuple[int, Instruction, bytes]]:
    cursor = 0
    result: list[tuple[int, Instruction, bytes]] = []
    while cursor < len(raw):
        start = cursor
        instruction, cursor = decode_instruction(raw, cursor)
        result.append((start, instruction, raw[start:cursor]))
    return result


def encode_operand(operand: Operand) -> bytes:
    result = bytearray()
    result.extend(_U8.pack(operand.kind.value))
    match operand.kind:
        case OperandKind.IMM:
            result.extend(_I32.pack(to_i32(operand.value)))
        case OperandKind.DREG | OperandKind.AREG | OperandKind.IND_A:
            result.extend(_U8.pack(operand.value))
        case OperandKind.ABS:
            result.extend(_U32.pack(to_u32(operand.value)))
        case OperandKind.IND_A_DISP:
            result.extend(_U8.pack(operand.value))
            result.extend(_I32.pack(to_i32(operand.offset)))
        case _:
            assert_never(operand.kind)
    return bytes(result)


def decode_operand(raw: bytes, offset: int) -> tuple[Operand, int]:
    _require_size(raw, offset, 1)
    kind = OperandKind(_U8.unpack_from(raw, offset)[0])
    cursor = offset + 1

    match kind:
        case OperandKind.IMM:
            _require_size(raw, cursor, _I32.size)
            value = _I32.unpack_from(raw, cursor)[0]
            return Operand.imm(value), cursor + _I32.size
        case OperandKind.DREG:
            _require_size(raw, cursor, 1)
            return Operand.dreg(_U8.unpack_from(raw, cursor)[0]), cursor + 1
        case OperandKind.AREG:
            _require_size(raw, cursor, 1)
            return Operand.areg(_U8.unpack_from(raw, cursor)[0]), cursor + 1
        case OperandKind.ABS:
            _require_size(raw, cursor, _U32.size)
            return Operand.abs(_U32.unpack_from(raw, cursor)[0]), cursor + _U32.size
        case OperandKind.IND_A:
            _require_size(raw, cursor, 1)
            return Operand.ind_areg(_U8.unpack_from(raw, cursor)[0]), cursor + 1
        case OperandKind.IND_A_DISP:
            _require_size(raw, cursor, 1 + _I32.size)
            register = _U8.unpack_from(raw, cursor)[0]
            displacement = _I32.unpack_from(raw, cursor + 1)[0]
            return Operand.ind_areg_disp(register, displacement), cursor + 1 + _I32.size
    assert_never(kind)


def _require_size(raw: bytes, offset: int, size: int) -> None:
    if offset < 0 or offset + size > len(raw):
        msg = f"unexpected end of binary at offset {offset}: need {size} byte(s)"
        raise ValueError(msg)
