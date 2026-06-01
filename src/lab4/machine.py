from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lab4.binary import ProgramImage

from lab4.isa import (
    DATA_MEMORY_SIZE_WORDS,
    STACK_POINTER,
    WORD_BYTES,
    to_i32,
)


class Machine:
    def __init__(self, program: ProgramImage) -> None:
        self.code: bytes = program.code
        self.entry_point: int = program.entry_point
        self.interrupt_vectors: tuple[int, ...] = program.interrupt_vectors

        # Harvard architecture: distinct data memory.
        self.data_memory_size: int = DATA_MEMORY_SIZE_WORDS * WORD_BYTES
        self.data_memory: bytearray = bytearray(self.data_memory_size)

        # Регистры
        self.d_regs: list[int] = [0] * 8
        self.a_regs: list[int] = [0] * 8

        # Stack pointer (A7) указывает на конец data memory
        self.a_regs[STACK_POINTER] = self.data_memory_size

        self.pc: int = self.entry_point

        # Флаги (Condition Codes)
        self.n: bool = False
        self.z: bool = False
        self.v: bool = False
        self.c: bool = False

        self.halted: bool = False
        self.tick_counter: int = 0
        self.log: list[str] = []

        # Load static data segments
        for i, word in enumerate(program.data):
            self.write_word(i * WORD_BYTES, word)

    def read_word(self, address: int) -> int:
        if address % WORD_BYTES != 0:
            msg = f"unaligned word access at address {address}"
            raise ValueError(msg)
        if not (0 <= address <= self.data_memory_size - WORD_BYTES):
            msg = f"address out of bounds: {address}"
            raise ValueError(msg)
        raw = self.data_memory[address : address + WORD_BYTES]
        value = struct.unpack("<i", raw)[0]
        return to_i32(value)

    def write_word(self, address: int, value: int) -> None:
        if address % WORD_BYTES != 0:
            msg = f"unaligned word access at address {address}"
            raise ValueError(msg)
        if not (0 <= address <= self.data_memory_size - WORD_BYTES):
            msg = f"address out of bounds: {address}"
            raise ValueError(msg)
        raw = struct.pack("<i", to_i32(value))
        self.data_memory[address : address + WORD_BYTES] = raw

    def push_value(self, value: int) -> None:
        sp = self.a_regs[STACK_POINTER] - WORD_BYTES
        self.write_word(sp, value)
        self.a_regs[STACK_POINTER] = sp

    def pop_value(self) -> int:
        sp = self.a_regs[STACK_POINTER]
        value = self.read_word(sp)
        self.a_regs[STACK_POINTER] = sp + WORD_BYTES
        return value
