from __future__ import annotations

from lab4.binary import ProgramImage, encode_instruction, encode_program
from lab4.isa import Instruction, OpCode, Operand


class AssemblyBuilder:
    """Вспомогательный сборщик (builder) ассемблерного кода для упрощения написания тестов."""

    def __init__(self) -> None:
        self._elements: list[Instruction | str] = []  # Список инструкций или имен меток
        self._refs: list[
            tuple[int, int, str]
        ] = []  # (индекс_инструкции, индекс_операнда, имя_метки)

    def add(self, opcode: OpCode, *operands: Operand | str) -> AssemblyBuilder:
        """Добавление инструкции в программу. Операнд-строка считается ссылкой на метку."""
        instr_idx = sum(1 for el in self._elements if isinstance(el, Instruction))
        resolved_operands: list[Operand] = []

        for op_idx, op in enumerate(operands):
            if isinstance(op, str):
                # Временно подставляем заглушку, запоминаем ссылку на метку
                resolved_operands.append(Operand.abs(0))
                self._refs.append((instr_idx, op_idx, op))
            else:
                resolved_operands.append(op)

        self._elements.append(Instruction(opcode, tuple(resolved_operands)))
        return self

    def label(self, name: str) -> AssemblyBuilder:
        """Объявление метки в текущей позиции программы."""
        if any(el == name for el in self._elements if isinstance(el, str)):
            msg = f"Label already defined: {name}"
            raise ValueError(msg)
        self._elements.append(name)
        return self

    def build(
        self,
        entry_point: int = 0,
        data: tuple[int, ...] = (),
        interrupt_vectors: tuple[int | str, ...] = (),
    ) -> ProgramImage:
        """Сборка программы: расчет смещений меток, подстановка адресов и генерация ProgramImage."""
        labels: dict[str, int] = {}
        current_offset = entry_point
        instructions: list[Instruction] = []

        # Первый проход: вычисление адресов всех меток
        for el in self._elements:
            if isinstance(el, str):
                labels[el] = current_offset
            else:
                instructions.append(el)
                current_offset += len(encode_instruction(el))

        # Разрешение адресов в векторах прерываний
        resolved_vectors: list[int] = []
        for vec in interrupt_vectors:
            if isinstance(vec, str):
                if vec not in labels:
                    msg = f"Undefined interrupt handler label: {vec}"
                    raise ValueError(msg)
                resolved_vectors.append(labels[vec])
            else:
                resolved_vectors.append(vec)

        # Второй проход: разрешение ссылок на метки в инструкциях
        for instr_idx, op_idx, label_name in self._refs:
            if label_name not in labels:
                msg = f"Undefined label reference: {label_name}"
                raise ValueError(msg)

            target_pc = labels[label_name]
            instr = instructions[instr_idx]

            new_operands = list(instr.operands)
            new_operands[op_idx] = Operand.abs(target_pc)

            instructions[instr_idx] = Instruction(instr.opcode, tuple(new_operands))

        code = encode_program(instructions)
        return ProgramImage(
            entry_point=entry_point, code=code, data=data, interrupt_vectors=tuple(resolved_vectors)
        )
