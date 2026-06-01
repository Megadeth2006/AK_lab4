# tests/test_machine.py
from __future__ import annotations

import pytest

from lab4.binary import ProgramImage, encode_program
from lab4.isa import DATA_MEMORY_SIZE_WORDS, STACK_POINTER, WORD_BYTES, Instruction, OpCode
from lab4.machine import Machine


def test_machine_initial_state() -> None:
    program = ProgramImage(entry_point=16, code=b"\x00\x00")
    machine = Machine(program)

    assert machine.code == b"\x00\x00"
    assert machine.entry_point == 16
    assert machine.pc == 16
    assert len(machine.data_memory) == DATA_MEMORY_SIZE_WORDS * WORD_BYTES
    assert machine.d_regs == [0] * 8
    assert machine.a_regs[0:7] == [0] * 7
    assert machine.a_regs[STACK_POINTER] == DATA_MEMORY_SIZE_WORDS * WORD_BYTES
    assert not machine.n
    assert not machine.z
    assert not machine.v
    assert not machine.c
    assert not machine.halted
    assert machine.tick_counter == 0
    assert machine.log == []


def test_machine_loads_program_data() -> None:
    program = ProgramImage(
        entry_point=0,
        code=b"",
        data=(42, -5, 0x12345678),
    )
    machine = Machine(program)

    assert machine.read_word(0) == 42
    assert machine.read_word(4) == -5
    assert machine.read_word(8) == 0x12345678


def test_read_write_word_success() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    machine.write_word(16, 1234567)
    assert machine.read_word(16) == 1234567

    # Тестируем отрицательные знаковые значения
    machine.write_word(32, -100)
    assert machine.read_word(32) == -100


def test_read_write_word_errors() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.read_word(-4)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.read_word(DATA_MEMORY_SIZE_WORDS * WORD_BYTES)

    with pytest.raises(ValueError, match="must be word-aligned"):
        machine.read_word(2)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.write_word(-4, 42)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.write_word(DATA_MEMORY_SIZE_WORDS * WORD_BYTES, 42)

    with pytest.raises(ValueError, match="must be word-aligned"):
        machine.write_word(3, 42)


def test_push_pop_value() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    initial_sp = machine.a_regs[STACK_POINTER]

    machine.push_value(10)
    assert machine.a_regs[STACK_POINTER] == initial_sp - 4
    assert machine.read_word(initial_sp - 4) == 10

    machine.push_value(-20)
    assert machine.a_regs[STACK_POINTER] == initial_sp - 8
    assert machine.read_word(initial_sp - 8) == -20

    assert machine.pop_value() == -20
    assert machine.a_regs[STACK_POINTER] == initial_sp - 4

    assert machine.pop_value() == 10
    assert machine.a_regs[STACK_POINTER] == initial_sp


def test_push_too_many_values_overflow() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    for i in range(DATA_MEMORY_SIZE_WORDS):
        machine.push_value(i)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.push_value(999)


def test_step_nop_and_halt() -> None:
    # Собираем программу: NOP, NOP, HALT
    code = encode_program(
        [
            Instruction(OpCode.NOP),
            Instruction(OpCode.NOP),
            Instruction(OpCode.HALT),
        ]
    )
    program = ProgramImage(entry_point=0, code=code)
    machine = Machine(program)

    # Выполняем первый шаг (NOP)
    machine.step()
    assert machine.tick_counter == 1
    assert machine.pc > 0  # PC сдвинулся на размер NOP
    assert not machine.halted
    assert len(machine.log) == 1
    assert "nop" in machine.log[0]

    # Выполняем второй шаг (NOP)
    machine.step()
    assert machine.tick_counter == 2

    # Выполняем третий шаг (HALT)
    machine.step()
    assert machine.tick_counter == 3
    assert machine.halted
    assert "halt" in machine.log[2]


def test_run_executes_until_halt() -> None:
    code = encode_program(
        [
            Instruction(OpCode.NOP),
            Instruction(OpCode.HALT),
        ]
    )
    program = ProgramImage(entry_point=0, code=code)
    machine = Machine(program)

    machine.run()
    assert machine.halted
    assert machine.tick_counter == 2


def test_not_implemented_opcode_raises_error() -> None:
    # ADD пока не реализован в этом коммите
    code = encode_program(
        [
            Instruction(OpCode.ADD),
        ]
    )
    program = ProgramImage(entry_point=0, code=code)
    machine = Machine(program)

    with pytest.raises(NotImplementedError, match="is not implemented"):
        machine.step()
