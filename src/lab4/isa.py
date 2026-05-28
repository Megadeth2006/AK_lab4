from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Final, assert_never

WORD_BITS: Final[int] = 32
WORD_BYTES: Final[int] = 4
U32_MAX: Final[int] = 0xFFFF_FFFF
DATA_MEMORY_SIZE_WORDS: Final[int] = 4096

# Memory-mapped I/O addresses. They are deliberately placed outside normal RAM.
IO_INPUT_DATA: Final[int] = 0xFFFF_0000
IO_INPUT_STATUS: Final[int] = 0xFFFF_0004
IO_OUTPUT_DATA: Final[int] = 0xFFFF_0008
IO_OUTPUT_STATUS: Final[int] = 0xFFFF_000C

INTERRUPT_INPUT_VECTOR: Final[int] = 0

REGISTER_COUNT: Final[int] = 8
STACK_POINTER: Final[int] = 7  # A7, M68k-like convention.
FRAME_POINTER: Final[int] = 6  # A6, M68k-like convention.


class OpCode(IntEnum):
    NOP = 0x00
    HALT = 0x01

    MOVE = 0x10
    LEA = 0x11
    PUSH = 0x12
    POP = 0x13

    ADD = 0x20
    SUB = 0x21
    MUL = 0x22
    DIV = 0x23
    MOD = 0x24
    CMP = 0x25
    NEG = 0x26

    AND = 0x30
    OR = 0x31
    XOR = 0x32
    NOT = 0x33
    SHL = 0x34
    SHR = 0x35

    JMP = 0x40
    JE = 0x41
    JNE = 0x42
    JL = 0x43
    JLE = 0x44
    JG = 0x45
    JGE = 0x46
    CALL = 0x47
    RET = 0x48
    IRET = 0x49

    EI = 0x50
    DI = 0x51


class OperandKind(IntEnum):
    IMM = 0x01  # #42
    DREG = 0x02  # D0..D7
    AREG = 0x03  # A0..A7
    ABS = 0x04  # [0x100], memory-mapped I/O included
    IND_A = 0x05  # [A0]
    IND_A_DISP = 0x06  # [A0+4]


class RegisterBank(StrEnum):
    DATA = "D"
    ADDRESS = "A"


@dataclass(frozen=True, slots=True)
class Operand:
    kind: OperandKind
    value: int
    offset: int = 0

    @staticmethod
    def imm(value: int) -> Operand:
        return Operand(OperandKind.IMM, value)

    @staticmethod
    def dreg(index: int) -> Operand:
        _validate_register(index)
        return Operand(OperandKind.DREG, index)

    @staticmethod
    def areg(index: int) -> Operand:
        _validate_register(index)
        return Operand(OperandKind.AREG, index)

    @staticmethod
    def abs(address: int) -> Operand:
        if not 0 <= address <= U32_MAX:
            msg = f"absolute address must fit uint32, got {address}"
            raise ValueError(msg)
        return Operand(OperandKind.ABS, address)

    @staticmethod
    def ind_areg(index: int) -> Operand:
        _validate_register(index)
        return Operand(OperandKind.IND_A, index)

    @staticmethod
    def ind_areg_disp(index: int, offset: int) -> Operand:
        _validate_register(index)
        return Operand(OperandKind.IND_A_DISP, index, offset)

    def to_mnemonic(self) -> str:
        match self.kind:
            case OperandKind.IMM:
                return f"#{self.value}"
            case OperandKind.DREG:
                return f"D{self.value}"
            case OperandKind.AREG:
                return f"A{self.value}"
            case OperandKind.ABS:
                return f"[0x{self.value:08X}]"
            case OperandKind.IND_A:
                return f"[A{self.value}]"
            case OperandKind.IND_A_DISP:
                sign = "+" if self.offset >= 0 else ""
                return f"[A{self.value}{sign}{self.offset}]"
        assert_never(self.kind)


@dataclass(frozen=True, slots=True)
class Instruction:
    opcode: OpCode
    operands: tuple[Operand, ...] = ()

    def to_mnemonic(self) -> str:
        if not self.operands:
            return self.opcode.name.lower()
        args = ", ".join(operand.to_mnemonic() for operand in self.operands)
        return f"{self.opcode.name.lower()} {args}"


def _validate_register(index: int) -> None:
    if not 0 <= index < REGISTER_COUNT:
        msg = f"register index must be in range 0..{REGISTER_COUNT - 1}, got {index}"
        raise ValueError(msg)


def to_u32(value: int) -> int:
    return value & U32_MAX


def to_i32(value: int) -> int:
    value &= U32_MAX
    if value & 0x8000_0000:
        return value - 0x1_0000_0000
    return value


def format_hex_word(value: int) -> str:
    return f"0x{to_u32(value):08X}"
