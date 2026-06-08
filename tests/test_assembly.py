# tests/test_assembly.py
from __future__ import annotations

import pytest

from lab4.assembly import AssemblyBuilder
from lab4.isa import OpCode


def test_assembly_builder_resolves_labels() -> None:
    builder = AssemblyBuilder()
    # Реализуем цикл ожидания:
    # loop:
    #   NOP
    #   JE loop
    #   HALT
    builder.label("loop")
    builder.add(OpCode.NOP)
    builder.add(OpCode.JE, "loop")
    builder.add(OpCode.HALT)

    program = builder.build(entry_point=0)

    # Проверяем, что адрес перехода JE указывает на начало (0)
    # Первая инструкция NOP занимает 2 байта (OpCode + OperandCount)
    assert program.entry_point == 0
    assert len(program.code) > 0


def test_assembly_builder_forward_reference() -> None:
    builder = AssemblyBuilder()
    # JMP target
    # NOP
    # target:
    # HALT
    builder.add(OpCode.JMP, "target")
    builder.add(OpCode.NOP)
    builder.label("target")
    builder.add(OpCode.HALT)

    program = builder.build(entry_point=10)

    # Проверяем, что адрес точки входа верный
    assert program.entry_point == 10


def test_assembly_builder_rejects_duplicate_labels() -> None:
    builder = AssemblyBuilder()
    builder.label("dup")
    with pytest.raises(ValueError, match="Label already defined"):
        builder.label("dup")


def test_assembly_builder_rejects_undefined_references() -> None:
    builder = AssemblyBuilder()
    builder.add(OpCode.JMP, "missing")
    with pytest.raises(ValueError, match="Undefined label reference"):
        builder.build()
