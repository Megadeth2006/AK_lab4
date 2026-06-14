# src/lab4/compiler.py
from __future__ import annotations

from typing import TYPE_CHECKING

from lab4.assembly import AssemblyBuilder
from lab4.ast import (
    Assign,
    BinOp,
    Block,
    Call,
    Expression,
    ExprStmt,
    Function,
    Identifier,
    If,
    NumLiteral,
    Program,
    Return,
    Statement,
    UnaryOp,
    VarDecl,
    While,
)
from lab4.isa import OpCode, Operand

if TYPE_CHECKING:
    from lab4.binary import ProgramImage

class Compiler:
    """Компилятор из AST языка alg в бинарный образ ProgramImage."""

    def __init__(self) -> None:
        self.builder = AssemblyBuilder()
        # Таблица символов текущей функции: имя_переменной -> смещение_от_A6
        self.local_symbols: dict[str, int] = {}
        # Смещение для следующей локальной переменной
        self.next_local_offset = -4

    def compile(self, program: Program) -> ProgramImage:
        """Компиляция всей программы."""
        # Ищем функцию main — она должна быть точкой входа
        main_func = next((f for f in program.funcs if f.name == "main"), None)
        if not main_func:
            msg = "Entry point function 'main' is not found"
            raise ValueError(msg)

        # Компилируем вызов main в качестве стартовой точки бинарного образа
        self.builder.add(OpCode.CALL, "main")
        self.builder.add(OpCode.HALT)

        # Компилируем все функции программы
        for func in program.funcs:
            self._compile_function(func)

        # Собираем и возвращаем бинарный образ
        return self.builder.build(entry_point=0)

    def _compile_function(self, func: Function) -> None:
        """Компиляция одной функции (пролог, тело, эпилог)."""
        self.builder.label(func.name)

        # Сбрасываем таблицу локальных символов для новой функции
        self.local_symbols.clear()
        self.next_local_offset = -4

        # 1. Пролог: сохраняем старый Frame Pointer (A6) и устанавливаем новый
        self.builder.add(OpCode.PUSH, Operand.areg(6))
        self.builder.add(OpCode.MOVE, Operand.areg(7), Operand.areg(6))

        # Мапим параметры функции на положительные смещения от A6
        # Первым на стеке лежит сохраненный A6 (0), вторым — адрес возврата (4),
        # поэтому параметры начинаются с адреса [A6 + 8]
        for i, param in enumerate(func.params):
            param_offset = 8 + i * 4
            self.local_symbols[param.name] = param_offset

        # Считаем количество локальных переменных для выделения памяти на стеке
        local_vars_count = self._count_local_variables(func.body)
        if local_vars_count > 0:
            # Выделяем место на стеке: sub #N_bytes, A7
            self.builder.add(OpCode.SUB, Operand.imm(local_vars_count * 4), Operand.areg(7))

        # 2. Компилируем тело функции
        for stmt in func.body.statements:
            self._compile_statement(stmt)

        # 3. Эпилог по умолчанию (если функция void и нет явного return на выходе)
        # Он безопасно восстанавливает стек и возвращает управление
        self._compile_epilogue()

    def _compile_statement(self, stmt: Statement) -> None:
        """Компиляция отдельной инструкции."""
        if isinstance(stmt, VarDecl):
            # Резервируем место под новую локальную переменную
            offset = self.next_local_offset
            self.next_local_offset -= 4
            self.local_symbols[stmt.name] = offset

            # Если есть инициализатор, вычисляем его и записываем в переменную
            if stmt.init:
                self._compile_expr(stmt.init)
                # move D0, [A6 + offset]
                self.builder.add(OpCode.MOVE, Operand.dreg(0), Operand.ind_areg_disp(6, offset))

        elif isinstance(stmt, Assign):
            if stmt.name not in self.local_symbols:
                msg = f"Undefined variable: {stmt.name}"
                raise ValueError(msg)
            offset = self.local_symbols[stmt.name]
            self._compile_expr(stmt.value)
            # move D0, [A6 + offset]
            self.builder.add(OpCode.MOVE, Operand.dreg(0), Operand.ind_areg_disp(6, offset))

        elif isinstance(stmt, Return):
            if stmt.value:
                self._compile_expr(stmt.value)
            self._compile_epilogue()

        elif isinstance(stmt, ExprStmt):
            self._compile_expr(stmt.expr)

        elif isinstance(stmt, Block):
            for sub_stmt in stmt.statements:
                self._compile_statement(sub_stmt)

        else:
            msg = f"Unsupported statement type: {type(stmt).__name__}"
            raise NotImplementedError(msg)

    def _compile_expr(self, expr: Expression) -> None:
        """Компиляция выражения. Результат вычисления всегда помещается в регистр D0."""
        if isinstance(expr, NumLiteral):
            self.builder.add(OpCode.MOVE, Operand.imm(expr.value), Operand.dreg(0))

        elif isinstance(expr, Identifier):
            if expr.name not in self.local_symbols:
                msg = f"Undefined variable reference: {expr.name}"
                raise ValueError(msg)
            offset = self.local_symbols[expr.name]
            # move [A6 + offset], D0
            self.builder.add(OpCode.MOVE, Operand.ind_areg_disp(6, offset), Operand.dreg(0))

        elif isinstance(expr, BinOp):
            # 1. Вычисляем левый операнд -> результат в D0
            self._compile_expr(expr.left)
            # 2. Сохраняем его на стек
            self.builder.add(OpCode.PUSH, Operand.dreg(0))
            # 3. Вычисляем правый операнд -> результат в D0
            self._compile_expr(expr.right)
            # 4. Восстанавливаем левый операнд в D1
            self.builder.add(OpCode.POP, Operand.dreg(1))

            # 5. Выполняем операцию над D1 и D0
            # Результат возвращается в D0
            if expr.op == "+":
                self.builder.add(OpCode.ADD, Operand.dreg(0), Operand.dreg(1))
                self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.dreg(0))
            elif expr.op == "-":
                self.builder.add(OpCode.SUB, Operand.dreg(0), Operand.dreg(1))
                self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.dreg(0))
            elif expr.op == "*":
                self.builder.add(OpCode.MUL, Operand.dreg(0), Operand.dreg(1))
                self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.dreg(0))
            elif expr.op == "/":
                self.builder.add(OpCode.DIV, Operand.dreg(0), Operand.dreg(1))
                self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.dreg(0))
            elif expr.op == "%":
                self.builder.add(OpCode.MOD, Operand.dreg(0), Operand.dreg(1))
                self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.dreg(0))
            else:
                msg = f"Unsupported binary operator in expressions: {expr.op}"
                raise NotImplementedError(msg)

        elif isinstance(expr, UnaryOp):
            self._compile_expr(expr.expr)
            if expr.op == "-":
                self.builder.add(OpCode.NEG, Operand.dreg(0))
            else:
                msg = f"Unsupported unary operator: {expr.op}"
                raise NotImplementedError(msg)

        elif isinstance(expr, Call):
            # Передаем параметры функции на стеке в обратном порядке (M68k / CDECL)
            for arg in reversed(expr.args):
                self._compile_expr(arg)
                self.builder.add(OpCode.PUSH, Operand.dreg(0))

            # Вызываем функцию
            self.builder.add(OpCode.CALL, expr.name)

            # Восстанавливаем (очищаем) стек от переданных аргументов: add #N*4, A7
            if len(expr.args) > 0:
                self.builder.add(OpCode.ADD, Operand.imm(len(expr.args) * 4), Operand.areg(7))

        else:
            msg = f"Unsupported expression type: {type(expr).__name__}"
            raise NotImplementedError(msg)

    def _compile_epilogue(self) -> None:
        """Генерация эпилога функции."""
        # Восстанавливаем указатель стека: move A6, A7
        self.builder.add(OpCode.MOVE, Operand.areg(6), Operand.areg(7))
        # Восстанавливаем старый Frame Pointer: pop A6
        self.builder.add(OpCode.POP, Operand.areg(6))
        # Возврат
        self.builder.add(OpCode.RET)

    def _count_local_variables(self, block: Block) -> int:
        """Вспомогательный метод для подсчета количества локальных переменных в блоке."""
        count = 0
        for stmt in block.statements:
            if isinstance(stmt, VarDecl):
                count += 1
            elif isinstance(stmt, If):
                count += self._count_local_variables(stmt.then_branch)
                if stmt.else_branch:
                    count += self._count_local_variables(stmt.else_branch)
            elif isinstance(stmt, While):
                count += self._count_local_variables(stmt.body)
        return count
