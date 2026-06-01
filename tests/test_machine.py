from __future__ import annotations

import pytest

from lab4.binary import ProgramImage
from lab4.isa import DATA_MEMORY_SIZE_WORDS, STACK_POINTER, WORD_BYTES
from lab4.machine import Machine


def test_machine_initial_state() -> None:
    program = ProgramImage(entry_point=4, code=b"", data=(), interrupt_vectors=())
    machine = Machine(program)

    assert machine.pc == 4
    assert machine.d_regs == [0] * 8
    assert machine.a_regs[:7] == [0] * 7
    assert machine.a_regs[STACK_POINTER] == DATA_MEMORY_SIZE_WORDS * WORD_BYTES
    assert not machine.n
    assert not machine.z
    assert not machine.v
    assert not machine.c
    assert not machine.halted
    assert machine.tick_counter == 0
    assert machine.log == []


def test_machine_static_data_loading() -> None:
    program = ProgramImage(entry_point=0, code=b"", data=(42, -5, 0x12345678), interrupt_vectors=())
    machine = Machine(program)

    assert machine.read_word(0) == 42
    assert machine.read_word(4) == -5
    assert machine.read_word(8) == 0x12345678


def test_machine_read_write_word() -> None:
    program = ProgramImage(entry_point=0, code=b"", data=(), interrupt_vectors=())
    machine = Machine(program)

    machine.write_word(16, 1234567)
    assert machine.read_word(16) == 1234567

    # Test 32-bit signed integer casting.
    machine.write_word(20, 0xFFFF_FFFF)
    assert machine.read_word(20) == -1


def test_machine_unaligned_access() -> None:
    program = ProgramImage(entry_point=0, code=b"", data=(), interrupt_vectors=())
    machine = Machine(program)

    with pytest.raises(ValueError, match="unaligned word access"):
        machine.read_word(1)

    with pytest.raises(ValueError, match="unaligned word access"):
        machine.write_word(2, 42)


def test_machine_out_of_bounds_access() -> None:
    program = ProgramImage(entry_point=0, code=b"", data=(), interrupt_vectors=())
    machine = Machine(program)

    limit = DATA_MEMORY_SIZE_WORDS * WORD_BYTES

    with pytest.raises(ValueError, match="address out of bounds"):
        machine.read_word(-4)

    with pytest.raises(ValueError, match="address out of bounds"):
        machine.read_word(limit)

    with pytest.raises(ValueError, match="address out of bounds"):
        machine.write_word(limit, 42)


def test_machine_push_pop_value() -> None:
    program = ProgramImage(entry_point=0, code=b"", data=(), interrupt_vectors=())
    machine = Machine(program)

    initial_sp = machine.a_regs[STACK_POINTER]

    machine.push_value(100)
    assert machine.a_regs[STACK_POINTER] == initial_sp - WORD_BYTES

    machine.push_value(-200)
    assert machine.a_regs[STACK_POINTER] == initial_sp - 2 * WORD_BYTES

    assert machine.pop_value() == -200
    assert machine.a_regs[STACK_POINTER] == initial_sp - WORD_BYTES

    assert machine.pop_value() == 100
    assert machine.a_regs[STACK_POINTER] == initial_sp
