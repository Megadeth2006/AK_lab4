# src/lab4/machine.py
from __future__ import annotations

import struct
from typing import Final

from lab4.binary import ProgramImage, decode_instruction
from lab4.isa import (
    DATA_MEMORY_SIZE_WORDS,
    STACK_POINTER,
    WORD_BYTES,
    OpCode,
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

        # Регистры процессора (D0-D7 и A0-A7)
        self.d_regs: list[int] = [0] * 8
        self.a_regs: list[int] = [0] * 8

        # A7 - указатель стека (Stack Pointer)
        # Начинается c конца памяти данных и растет вниз (в сторону младших адресов).
        self.a_regs[STACK_POINTER] = self.data_memory_size

        self.pc: int = self.entry_point

        # Флаги состояния (регистр признаков)
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

    def step(self) -> None:
        """Выполнение одного такта/инструкции процессора."""
        if self.halted:
            return

        # Запоминаем текущий PC для логирования
        current_pc = self.pc

        try:
            # Выборка и декодирование инструкции переменной длины
            instr, next_pc = decode_instruction(self.code, self.pc)
        except ValueError as e:
            # Прерываем выполнение при ошибке выборки (например, вышли за границы кода)
            self.halted = True
            msg = f"Instruction fetch error at PC=0x{self.pc:04X}: {e}"
            raise ValueError(msg) from e

        # По умолчанию PC указывает на следующую инструкцию.
        # Если инструкция — переход, она сама изменит self.pc.
        self.pc = next_pc

        # Исполнение инструкции
        match instr.opcode:
            case OpCode.NOP:
                self.tick_counter += 1
            case OpCode.HALT:
                self.halted = True
                self.tick_counter += 1
            case _:
                # Bce остальные инструкции будут реализованы в последующих коммитах
                msg = f"Instruction {instr.opcode.name} is not implemented in the machine core"
                raise NotImplementedError(msg)

        # Логирование состояния процессора после выполнения шага
        self._log_state(current_pc, instr.to_mnemonic())

    def run(self, limit: int = 1000) -> None:
        """Запуск цикла выполнения до остановки (HALT) или превышения лимита тактов."""
        while not self.halted and self.tick_counter < limit:
            self.step()

    def _log_state(self, pc: int, mnemonic: str) -> None:
        """Запись текущего состояния процессора в журнал трассировки."""
        flags_str = "".join(
            [
                "N" if self.n else "-",
                "Z" if self.z else "-",
                "V" if self.v else "-",
                "C" if self.c else "-",
            ]
        )
        d_regs_str = ", ".join(f"{val}" for val in self.d_regs)
        a_regs_str = ", ".join(f"{val}" for val in self.a_regs)
        log_entry = (
            f"TICK: {self.tick_counter:4d} | "
            f"PC: 0x{pc:04X} | "
            f"{mnemonic:<25} | "
            f"D: [{d_regs_str}] | "
            f"A: [{a_regs_str}] | "
            f"Flags: {flags_str}"
        )
        self.log.append(log_entry)
