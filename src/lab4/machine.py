# src/lab4/machine.py
from __future__ import annotations

import struct
from typing import Final

from lab4.binary import ProgramImage, decode_instruction
from lab4.isa import (
    DATA_MEMORY_SIZE_WORDS,
    INTERRUPT_INPUT_VECTOR,
    IO_INPUT_DATA,
    IO_INPUT_STATUS,
    IO_OUTPUT_DATA,
    IO_OUTPUT_STATUS,
    STACK_POINTER,
    WORD_BYTES,
    OpCode,
    Operand,
    OperandKind,
    to_i32,
)


class Machine:
    MIN_INT32 = -2147483648
    UINT32_OVERFLOW_BOUND = 0x100000000

    def __init__(
        self, program: ProgramImage, input_schedule: list[tuple[int, str]] | None = None
    ) -> None:
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

        # A7 — указатель стека (Stack Pointer).
        # Начинается с конца памяти данных и растет вниз (в сторону младших адресов).
        self.a_regs[STACK_POINTER] = self.data_memory_size

        self.pc: int = self.entry_point

        # Флаги состояния (регистр признаков)
        self.n: bool = False  # Negative (отрицательный результат)
        self.z: bool = False  # Zero (нулевой результат)
        self.v: bool = False  # Overflow (переполнение)
        self.c: bool = False  # Carry (перенос)

        # Состояние управления процессором
        self.halted: bool = False  # Сигнал остановки процессора
        self.tick_counter: int = 0  # Счетчик тактов
        self.log: list[str] = []  # Журнал трассировки выполнения

        # Буфер вывода символов (хранит ASCII-коды выведенных символов)
        self.output_buffer: list[int] = []

        # Система прерываний и ввода (Trap)
        # Сортируем расписание по тактам в обратном порядке для эффективного pop()
        self.input_schedule: list[tuple[int, str]] = sorted(
            input_schedule or [], key=lambda x: x[0], reverse=True
        )
        self.input_data: int = 0  # Регистр данных ввода
        self.input_status: int = 0  # Регистр статуса ввода (1 - готовы новые данные)
        self.interrupt_vectors: tuple[int, ...] = program.interrupt_vectors
        self.interrupts_enabled: bool = False  # Разрешены ли прерывания (флаг I)
        self.in_interrupt_handler: bool = False  # Флаг обработки прерывания (маскирует вложенные)

    def read_word(self, address: int) -> int:
        """Чтение 32-битного знакового слова из памяти данных по байтовому адресу."""
        # Обработка портов ввода-вывода (Memory-mapped I/O)
        if address == IO_INPUT_STATUS:
            return self.input_status
        if address == IO_INPUT_DATA:
            input_val: int = self.input_data
            self.input_status = 0  # Чтение данных сбрасывает готовность порта
            return input_val

        # Обработка портов вывода (Memory-mapped I/O)
        if address == IO_OUTPUT_STATUS:
            return 1  # Порт вывода всегда готов к приему данных
        if address == IO_OUTPUT_DATA:
            return 0  # Порт данных только для записи, при чтении возвращает 0
        if address < 0 or address + WORD_BYTES > self.data_memory_size:
            msg = f"Data memory access out of bounds: {address}"
            raise ValueError(msg)
        if address % WORD_BYTES != 0:
            msg = f"Data memory address must be word-aligned: {address}"
            raise ValueError(msg)
        memory_val: int = struct.unpack_from("<i", self.data_memory, address)[0]
        return to_i32(memory_val)

    def write_word(self, address: int, value: int) -> None:
        """Запись 32-битного знакового слова в память данных по байтовому адресу."""
        if address == IO_OUTPUT_DATA:
            self.output_buffer.append(value & 0xFF)  # Сохраняем младший байт как ASCII-символ
            return
        if address == IO_OUTPUT_STATUS:
            return  # Запись в порт статуса вывода игнорируется
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

        # Проверяем внешние прерывания ввода на текущем такте
        self._check_interrupts()
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
            case OpCode.MOVE:
                src, dest = instr.operands[0], instr.operands[1]
                val = self._read_operand(src)
                self._write_operand(dest, val)
                self._update_nz_flags(val)
                self.tick_counter += 2
            case OpCode.LEA:
                src, dest = instr.operands[0], instr.operands[1]
                if dest.kind != OperandKind.AREG:
                    msg = f"LEA destination must be an address register, got: {dest.kind.name}"
                    raise ValueError(msg)
                addr = self._resolve_address(src)
                self._write_operand(dest, addr)
                self.tick_counter += 2
            case OpCode.PUSH:
                src = instr.operands[0]
                val = self._read_operand(src)
                self.push_value(val)
                self.tick_counter += 2
            case OpCode.POP:
                dest = instr.operands[0]
                val = self.pop_value()
                self._write_operand(dest, val)
                self.tick_counter += 2

            # Арифметические и логические инструкции (ALU) со вторым операндом
            case (
                OpCode.ADD
                | OpCode.SUB
                | OpCode.MUL
                | OpCode.DIV
                | OpCode.MOD
                | OpCode.CMP
                | OpCode.AND
                | OpCode.OR
                | OpCode.XOR
                | OpCode.SHL
                | OpCode.SHR
            ):
                src, dest = instr.operands[0], instr.operands[1]
                src_val = self._read_operand(src)
                dest_val = self._read_operand(dest)
                self._execute_alu_op(instr.opcode, src_val, dest_val, dest)
                self.tick_counter += 2

            case OpCode.NEG:
                dest = instr.operands[0]
                val = self._read_operand(dest)
                result = to_i32(0 - val)
                self.n = result < 0
                self.z = result == 0
                self.v = val == self.MIN_INT32
                self.c = val != 0
                self._write_operand(dest, result)
                self.tick_counter += 2

            case OpCode.NOT:
                dest = instr.operands[0]
                val = self._read_operand(dest)
                result = to_i32(~val)
                self._update_nz_flags(result)
                self._write_operand(dest, result)
                self.tick_counter += 2

            # Инструкции переходов (Control Flow)
            case (
                OpCode.JMP
                | OpCode.JE
                | OpCode.JNE
                | OpCode.JL
                | OpCode.JLE
                | OpCode.JG
                | OpCode.JGE
            ):
                op = instr.operands[0]
                target = self._get_jump_target(op)

                taken = False
                match instr.opcode:
                    case OpCode.JMP:
                        taken = True
                    case OpCode.JE:
                        taken = self.z
                    case OpCode.JNE:
                        taken = not self.z
                    case OpCode.JL:
                        taken = self.n != self.v
                    case OpCode.JLE:
                        taken = self.z or (self.n != self.v)
                    case OpCode.JG:
                        taken = (not self.z) and (self.n == self.v)
                    case OpCode.JGE:
                        taken = self.n == self.v

                if taken:
                    self.pc = target

                self.tick_counter += 2

            # Вызов подпрограммы
            case OpCode.CALL:
                op = instr.operands[0]
                target = self._get_jump_target(op)
                # Сохраняем адрес возврата (PC следующей инструкции) на стек
                self.push_value(self.pc)
                # Переходим к подпрограмме
                self.pc = target
                self.tick_counter += 3

            # Возврат из подпрограммы
            case OpCode.RET:
                # Извлекаем адрес возврата со стека и переходим к нему
                self.pc = self.pop_value()
                self.tick_counter += 3

            # Разрешение прерываний
            case OpCode.EI:
                self.interrupts_enabled = True
                self.tick_counter += 1

            # Запрещение прерываний
            case OpCode.DI:
                self.interrupts_enabled = False
                self.tick_counter += 1

            # Возврат из прерывания
            case OpCode.IRET:
                # 1. Восстанавливаем сохраненные флаги из стека
                flags_word = self.pop_value()
                self.n = bool(flags_word & 1)
                self.z = bool(flags_word & 2)
                self.v = bool(flags_word & 4)
                self.c = bool(flags_word & 8)

                # 2. Восстанавливаем PC из стека
                self.pc = self.pop_value()

                # Сбрасываем флаг нахождения в обработчике
                self.in_interrupt_handler = False
                self.tick_counter += 4

        # Логирование состояния процессора после выполнения шага
        self._log_state(current_pc, instr.to_mnemonic())

    def run(self, limit: int = 1000) -> None:
        """Запуск цикла выполнения до остановки (HALT) или превышения лимита тактов."""
        while not self.halted and self.tick_counter < limit:
            self.step()

    def _read_operand(self, op: Operand) -> int:
        """Чтение значения операнда в зависимости от его режима адресации."""
        match op.kind:
            case OperandKind.IMM:
                return op.value
            case OperandKind.DREG:
                return self.d_regs[op.value]
            case OperandKind.AREG:
                return self.a_regs[op.value]
            case OperandKind.ABS:
                return self.read_word(op.value)
            case OperandKind.IND_A:
                return self.read_word(self.a_regs[op.value])
            case OperandKind.IND_A_DISP:
                return self.read_word(self.a_regs[op.value] + op.offset)
        msg = f"Unsupported operand kind for reading: {op.kind.name}"
        raise ValueError(msg)

    def _write_operand(self, op: Operand, value: int) -> None:
        """Запись значения в операнд-назначение."""
        match op.kind:
            case OperandKind.IMM:
                msg = "Cannot write to immediate operand"
                raise ValueError(msg)
            case OperandKind.DREG:
                self.d_regs[op.value] = to_i32(value)
            case OperandKind.AREG:
                self.a_regs[op.value] = to_i32(value)
            case OperandKind.ABS:
                self.write_word(op.value, value)
            case OperandKind.IND_A:
                self.write_word(self.a_regs[op.value], value)
            case OperandKind.IND_A_DISP:
                self.write_word(self.a_regs[op.value] + op.offset, value)
            case _:
                msg = f"Unsupported operand kind for writing: {op.kind.name}"
                raise ValueError(msg)

    def _resolve_address(self, op: Operand) -> int:
        """Вычисление эффективного адреса операнда (для LEA и адресации)."""
        match op.kind:
            case OperandKind.ABS:
                return op.value
            case OperandKind.IND_A:
                return self.a_regs[op.value]
            case OperandKind.IND_A_DISP:
                return self.a_regs[op.value] + op.offset
            case _:
                msg = f"Cannot resolve effective address for operand kind: {op.kind.name}"
                raise ValueError(msg)

    def _get_jump_target(self, op: Operand) -> int:
        """Вычисление целевого адреса перехода PC."""
        match op.kind:
            case OperandKind.ABS | OperandKind.IMM:
                return op.value
            case OperandKind.AREG:
                return self.a_regs[op.value]
            case OperandKind.IND_A:
                return self.a_regs[op.value]
            case _:
                return self._read_operand(op)

    def _execute_alu_op(self, opcode: OpCode, src: int, dest_val: int, dest_op: Operand) -> None:
        """Выполнение двухместной арифметической или логической операции."""
        result = 0
        match opcode:
            case OpCode.ADD:
                result = to_i32(dest_val + src)
                self.n = result < 0
                self.z = result == 0
                self.v = ((dest_val < 0) == (src < 0)) and ((result < 0) != (dest_val < 0))
                self.c = (
                    (dest_val & 0xFFFFFFFF) + (src & 0xFFFFFFFF)
                ) >= self.UINT32_OVERFLOW_BOUND
                self._write_operand(dest_op, result)

            case OpCode.SUB | OpCode.CMP:
                result = to_i32(dest_val - src)
                self.n = result < 0
                self.z = result == 0
                self.v = ((dest_val < 0) != (src < 0)) and ((result < 0) != (dest_val < 0))
                self.c = (dest_val & 0xFFFFFFFF) < (src & 0xFFFFFFFF)
                if opcode == OpCode.SUB:
                    self._write_operand(dest_op, result)

            case OpCode.MUL:
                result = to_i32(dest_val * src)
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

            case OpCode.DIV:
                if src == 0:
                    msg = "Division by zero"
                    raise ZeroDivisionError(msg)
                result = to_i32(int(dest_val / src))
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

            case OpCode.MOD:
                if src == 0:
                    msg = "Division by zero"
                    raise ZeroDivisionError(msg)
                result = to_i32(dest_val - src * int(dest_val / src))
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

            case OpCode.AND:
                result = to_i32(dest_val & src)
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

            case OpCode.OR:
                result = to_i32(dest_val | src)
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

            case OpCode.XOR:
                result = to_i32(dest_val ^ src)
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

            case OpCode.SHL:
                shift = src & 31
                result = to_i32(dest_val << shift)
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

            case OpCode.SHR:
                shift = src & 31
                result = to_i32((dest_val & 0xFFFFFFFF) >> shift)
                self._update_nz_flags(result)
                self._write_operand(dest_op, result)

    def _update_nz_flags(self, value: int) -> None:
        """Обновление флагов N и Z по результату операции. Флаги V и C сбрасываются."""
        self.n = value < 0
        self.z = value == 0
        self.v = False
        self.c = False

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
        mode_str = "INT" if self.in_interrupt_handler else "USR"
        log_entry = (
            f"TICK: {self.tick_counter:4d} | "
            f"PC: 0x{pc:04X} | "
            f"{mode_str} | "
            f"{mnemonic:<25} | "
            f"D: [{d_regs_str}] | "
            f"A: [{a_regs_str}] | "
            f"Flags: {flags_str}"
        )
        self.log.append(log_entry)

    def _check_interrupts(self) -> None:
        """Проверка наступления запланированных событий прерывания ввода."""
        if self.input_schedule and self.tick_counter >= self.input_schedule[-1][0]:
            _, char = self.input_schedule.pop()
            self.input_data = ord(char)
            self.input_status = 1  # Выставляем готовность данных

            # Если прерывания разрешены процессором и мы не обрабатываем другое прерывание
            if self.interrupts_enabled and not self.in_interrupt_handler:
                self._trigger_interrupt()

    def _trigger_interrupt(self) -> None:
        """Переход к обработчику прерывания."""
        if not self.interrupt_vectors:
            return  # Нет зарегистрированных векторов - игнорируем прерывание

        self.in_interrupt_handler = True

        # Сохраняем состояние на стек: сначала PC (адрес возврата), затем упакованные флаги
        self.push_value(self.pc)
        flags_word = (
            (1 if self.n else 0)
            | (2 if self.z else 0)
            | (4 if self.v else 0)
            | (8 if self.c else 0)
        )
        self.push_value(flags_word)

        # Переходим к обработчику по вектору ввода
        self.pc = self.interrupt_vectors[INTERRUPT_INPUT_VECTOR]
        self.tick_counter += 4
