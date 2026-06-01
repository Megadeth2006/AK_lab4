from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Final

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

        # Гарвардская архитектура: размер памяти данных в байтах
        self.data_memory_size: Final[int] = DATA_MEMORY_SIZE_WORDS * WORD_BYTES
        self.data_memory: bytearray = bytearray(self.data_memory_size)

        # Загрузка начального сегмента данных в память данных
        for i, word in enumerate(program.data):
            address = i * WORD_BYTES
            if address + WORD_BYTES > self.data_memory_size:
                msg = "Initial program data exceeds data memory size limit"
                raise ValueError(msg)
            struct.pack_into("<i", self.data_memory, address, to_i32(word))

        # Регистры CPU (D0-D7 and A0-A7)
        self.d_regs: list[int] = [0] * 8
        self.a_regs: list[int] = [0] * 8

        # A7 is - указатель стека (SP)
        # Начинается c конца памяти и растет вниз (в сторону младших адресов)
        self.a_regs[STACK_POINTER] = self.data_memory_size

        self.pc: int = self.entry_point

        # Флаги состояния
        self.n: bool = False
        self.z: bool = False
        self.v: bool = False
        self.c: bool = False

        # Состояние управления процессором
        self.halted: bool = False  # Сигнал остановки процессора
        self.tick_counter: int = 0  # Счетчик тактов
        self.log: list[str] = []  # Журнал трассировки выполнения

    def read_word(self, address: int) -> int:
        """Чтение 32-битного знакового слова из памяти данных по байтовому адресу."""
        if address < 0 or address + WORD_BYTES > self.data_memory_size:
            msg = f"Data memory access out of bounds: {address}"
            raise ValueError(msg)
        if address % WORD_BYTES != 0:
            msg = f"Data memory address must be word-aligned: {address}"
            raise ValueError(msg)
        val: int = struct.unpack_from("<i", self.data_memory, address)[0]
        return to_i32(val)

    def write_word(self, address: int, value: int) -> None:
        """Запись 32-битного знакового слова в память данных по байтовому адресу."""
        if address < 0 or address + WORD_BYTES > self.data_memory_size:
            msg = f"Data memory access out of bounds: {address}"
            raise ValueError(msg)
        if address % WORD_BYTES != 0:
            msg = f"Data memory address must be word-aligned: {address}"
            raise ValueError(msg)
        struct.pack_into("<i", self.data_memory, address, to_i32(value))

    def push_value(self, value: int) -> None:
        """Запись значения в стек (SP уменьшается на 4)."""
        sp = self.a_regs[STACK_POINTER]
        sp -= WORD_BYTES
        self.write_word(sp, value)
        self.a_regs[STACK_POINTER] = sp

    def pop_value(self) -> int:
        """Извлечение значения из стека (SP увеличивается на 4)."""
        sp = self.a_regs[STACK_POINTER]
        value = self.read_word(sp)
        sp += WORD_BYTES
        self.a_regs[STACK_POINTER] = sp
        return value
