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
    StrLiteral,
    UnaryOp,
    VarDecl,
    While,
)
from lab4.isa import IO_OUTPUT_DATA, WORD_BYTES, OpCode, Operand

if TYPE_CHECKING:
    from lab4.binary import ProgramImage


class Compiler:
    """Компилятор из AST языка alg в бинарный образ ProgramImage."""

    def __init__(self) -> None:
        self.builder = AssemblyBuilder()
        self.local_symbols: dict[str, int] = {}
        self.next_local_offset = -4
        self.label_counter = 0

        # Секция статических данных (для Pascal строк)
        self.static_data: list[int] = []
        # Кэш дубликатов строк: литерал -> байтовый адрес
        self.string_literals: dict[str, int] = {}

    def _new_label(self, prefix: str) -> str:
        """Генерация уникальной метки."""
        self.label_counter += 1
        return f"{prefix}_{self.label_counter}"

    def compile(self, program: Program) -> ProgramImage:
        """Компиляция всей программы."""
        self.static_data.clear()
        self.string_literals.clear()

        # Ищем функцию main
        main_func = next((f for f in program.funcs if f.name == "main"), None)
        if not main_func:
            msg = "Entry point function 'main' is not found"
            raise ValueError(msg)

        # Точка входа: вызов main и остановка
        self.builder.add(OpCode.CALL, "main")
        self.builder.add(OpCode.HALT)

        # Компилируем все функции
        for func in program.funcs:
            self._compile_function(func)

        # Внедряем системную библиотеку
        self._inject_print_string()
        self._inject_print_int()

        # Если объявлена функция on_input, регистрируем её в таблице прерываний
        has_on_input = any(f.name == "on_input" for f in program.funcs)
        vectors = ("on_input",) if has_on_input else ()

        return self.builder.build(
            entry_point=0, data=tuple(self.static_data), interrupt_vectors=vectors
        )

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

        elif isinstance(stmt, Return):
            if stmt.value:
                self._compile_expr(stmt.value)
            self._compile_epilogue()

        elif isinstance(stmt, If):
            else_label = self._new_label("else")
            endif_label = self._new_label("endif")

            # Вычисляем условие (результат в D0)
            self._compile_expr(stmt.cond)
            # Сравниваем результат в D0 с нулем (False)
            self.builder.add(OpCode.CMP, Operand.imm(0), Operand.dreg(0))

            # Если условие ложно, прыгаем в ветку else (или endif, если else нет)
            target_false = else_label if stmt.else_branch else endif_label
            self.builder.add(OpCode.JE, target_false)

            # Ветка then
            self._compile_statement(stmt.then_branch)

            if stmt.else_branch:
                # Обходим ветку else
                self.builder.add(OpCode.JMP, endif_label)
                self.builder.label(else_label)
                self._compile_statement(stmt.else_branch)

            self.builder.label(endif_label)

        elif isinstance(stmt, While):
            start_label = self._new_label("while_start")
            end_label = self._new_label("while_end")

            self.builder.label(start_label)
            # Вычисляем условие (результат в D0)
            self._compile_expr(stmt.cond)
            # Если 0 (False), выходим из цикла
            self.builder.add(OpCode.CMP, Operand.imm(0), Operand.dreg(0))
            self.builder.add(OpCode.JE, end_label)

            # Тело цикла
            self._compile_statement(stmt.body)

            # Прыгаем обратно в начало проверки условий
            self.builder.add(OpCode.JMP, start_label)
            self.builder.label(end_label)

        elif isinstance(stmt, ExprStmt):
            self._compile_expr(stmt.expr)

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

        elif isinstance(expr, StrLiteral):
            if expr.value not in self.string_literals:
                # Выделяем адрес начала строки в байтах
                addr = len(self.static_data) * WORD_BYTES
                # Записываем длину (Pascal layout)
                self.static_data.append(len(expr.value))
                # Записываем символы по словам
                for char in expr.value:
                    self.static_data.append(ord(char))
                self.string_literals[expr.value] = addr

            addr = self.string_literals[expr.value]
            # Загружаем адрес строки в D0
            self.builder.add(OpCode.MOVE, Operand.imm(addr), Operand.dreg(0))
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
            elif expr.op in ("==", "!=", "<", "<=", ">", ">="):
                # Сравниваем левый операнд (D1) и правый (D0). CMP D0, D1 делает D1 - D0
                self.builder.add(OpCode.CMP, Operand.dreg(0), Operand.dreg(1))

                true_label = self._new_label("cmp_true")
                end_label = self._new_label("cmp_end")

                # Делаем условный переход на true_label в зависимости от оператора
                if expr.op == "==":
                    self.builder.add(OpCode.JE, true_label)
                elif expr.op == "!=":
                    self.builder.add(OpCode.JNE, true_label)
                elif expr.op == "<":
                    self.builder.add(OpCode.JL, true_label)
                elif expr.op == "<=":
                    self.builder.add(OpCode.JLE, true_label)
                elif expr.op == ">":
                    self.builder.add(OpCode.JG, true_label)
                elif expr.op == ">=":
                    self.builder.add(OpCode.JGE, true_label)

                # Путь ложного условия (False -> 0)
                self.builder.add(OpCode.MOVE, Operand.imm(0), Operand.dreg(0))
                self.builder.add(OpCode.JMP, end_label)

                # Путь истинного условия (True -> 1)
                self.builder.label(true_label)
                self.builder.add(OpCode.MOVE, Operand.imm(1), Operand.dreg(0))

                self.builder.label(end_label)
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
            # Обработка встроенных функций (Built-ins)
            if expr.name == "enable_interrupts":
                self.builder.add(OpCode.EI)
                return
            if expr.name == "disable_interrupts":
                self.builder.add(OpCode.DI)
                return
            if expr.name == "read_io":
                # Вычисляем адрес -> D0
                self._compile_expr(expr.args[0])
                # Переносим в адресный регистр A0 и считываем из него [A0] -> D0
                self.builder.add(OpCode.MOVE, Operand.dreg(0), Operand.areg(0))
                self.builder.add(OpCode.MOVE, Operand.ind_areg(0), Operand.dreg(0))
                return
            if expr.name == "write_io":
                # Вычисляем адрес -> D0, сохраняем на стек
                self._compile_expr(expr.args[0])
                self.builder.add(OpCode.PUSH, Operand.dreg(0))
                # Вычисляем значение -> D0
                self._compile_expr(expr.args[1])
                # Достаем адрес в A0
                self.builder.add(OpCode.POP, Operand.areg(0))
                # Записываем значение: move D0, [A0]
                self.builder.add(OpCode.MOVE, Operand.dreg(0), Operand.ind_areg(0))
                return
            if expr.name == "allocate_buffer":
                # allocate_buffer(size) резервирует место в секции данных
                size_node = expr.args[0]
                if not isinstance(size_node, NumLiteral):
                    msg = "allocate_buffer size must be a number literal"
                    raise ValueError(msg)
                addr = len(self.static_data) * WORD_BYTES
                for _ in range(size_node.value):
                    self.static_data.append(0)
                self.builder.add(OpCode.MOVE, Operand.imm(addr), Operand.dreg(0))
                return

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

    def _inject_print_string(self) -> None:
        """Системная процедура вывода Pascal strings."""
        self.builder.label("print_string")
        self.builder.add(OpCode.PUSH, Operand.areg(6))
        self.builder.add(OpCode.MOVE, Operand.areg(7), Operand.areg(6))

        # Загружаем адрес начала строки [A6 + 8] в A0
        self.builder.add(OpCode.MOVE, Operand.ind_areg_disp(6, 8), Operand.areg(0))
        # Читаем длину строки из [A0] в D0
        self.builder.add(OpCode.MOVE, Operand.ind_areg(0), Operand.dreg(0))

        # Если длина == 0, выходим
        self.builder.add(OpCode.CMP, Operand.imm(0), Operand.dreg(0))
        self.builder.add(OpCode.JE, "print_string_end")

        # Настраиваем A1 на первый символ (адрес + 4)
        self.builder.add(OpCode.LEA, Operand.ind_areg_disp(0, 4), Operand.areg(1))
        # Сеттим счетчик цикла D1 = 0
        self.builder.add(OpCode.MOVE, Operand.imm(0), Operand.dreg(1))

        self.builder.label("print_string_loop")
        # Цикл окончен, если D1 == D0 (счетчик == длина)
        self.builder.add(OpCode.CMP, Operand.dreg(0), Operand.dreg(1))
        self.builder.add(OpCode.JE, "print_string_end")

        # Читаем символ из [A1] в D2
        self.builder.add(OpCode.MOVE, Operand.ind_areg(1), Operand.dreg(2))
        # Выводим в порт вывода
        self.builder.add(OpCode.MOVE, Operand.dreg(2), Operand.abs(IO_OUTPUT_DATA))

        # Инкрементируем адрес символа A1 += 4 и счетчик D1 += 1
        self.builder.add(OpCode.ADD, Operand.imm(4), Operand.areg(1))
        self.builder.add(OpCode.ADD, Operand.imm(1), Operand.dreg(1))
        self.builder.add(OpCode.JMP, "print_string_loop")

        self.builder.label("print_string_end")
        self.builder.add(OpCode.MOVE, Operand.areg(6), Operand.areg(7))
        self.builder.add(OpCode.POP, Operand.areg(6))
        self.builder.add(OpCode.RET)

    def _inject_print_int(self) -> None:
        """Системная процедура вывода знаковых целых чисел."""
        self.builder.label("print_int")
        self.builder.add(OpCode.PUSH, Operand.areg(6))
        self.builder.add(OpCode.MOVE, Operand.areg(7), Operand.areg(6))

        # Загружаем число из параметров [A6 + 8] в D0
        self.builder.add(OpCode.MOVE, Operand.ind_areg_disp(6, 8), Operand.dreg(0))

        # Обработка отрицательных чисел
        self.builder.add(OpCode.CMP, Operand.imm(0), Operand.dreg(0))
        self.builder.add(OpCode.JGE, "print_int_pos")

        # Выводим '-' (ASCII 45)
        self.builder.add(OpCode.MOVE, Operand.imm(45), Operand.dreg(1))
        self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.abs(IO_OUTPUT_DATA))
        self.builder.add(OpCode.NEG, Operand.dreg(0))

        self.builder.label("print_int_pos")
        # Если число == 0, выводим '0' (ASCII 48)
        self.builder.add(OpCode.CMP, Operand.imm(0), Operand.dreg(0))
        self.builder.add(OpCode.JNE, "print_int_nonzero")
        self.builder.add(OpCode.MOVE, Operand.imm(48), Operand.dreg(1))
        self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.abs(IO_OUTPUT_DATA))
        self.builder.add(OpCode.JMP, "print_int_end")

        self.builder.label("print_int_nonzero")
        # Сеттим счетчик цифр D2 = 0
        self.builder.add(OpCode.MOVE, Operand.imm(0), Operand.dreg(2))

        self.builder.label("print_int_loop")
        self.builder.add(OpCode.CMP, Operand.imm(0), Operand.dreg(0))
        self.builder.add(OpCode.JE, "print_int_print_loop")

        # Получаем последнюю цифру: D1 = D0 % 10
        self.builder.add(OpCode.MOVE, Operand.dreg(0), Operand.dreg(1))
        self.builder.add(OpCode.MOD, Operand.imm(10), Operand.dreg(1))
        # Заталкиваем ее на стек
        self.builder.add(OpCode.PUSH, Operand.dreg(1))
        # D0 /= 10
        self.builder.add(OpCode.DIV, Operand.imm(10), Operand.dreg(0))
        # Увеличиваем счетчик цифр
        self.builder.add(OpCode.ADD, Operand.imm(1), Operand.dreg(2))
        self.builder.add(OpCode.JMP, "print_int_loop")

        self.builder.label("print_int_print_loop")
        self.builder.add(OpCode.CMP, Operand.imm(0), Operand.dreg(2))
        self.builder.add(OpCode.JE, "print_int_end")

        # Достаем цифру из стека
        self.builder.add(OpCode.POP, Operand.dreg(1))
        # Переводим в ASCII: D1 += 48
        self.builder.add(OpCode.ADD, Operand.imm(48), Operand.dreg(1))
        # Печатаем
        self.builder.add(OpCode.MOVE, Operand.dreg(1), Operand.abs(IO_OUTPUT_DATA))
        # Уменьшаем счетчик
        self.builder.add(OpCode.SUB, Operand.imm(1), Operand.dreg(2))
        self.builder.add(OpCode.JMP, "print_int_print_loop")

        self.builder.label("print_int_end")
        self.builder.add(OpCode.MOVE, Operand.areg(6), Operand.areg(7))
        self.builder.add(OpCode.POP, Operand.areg(6))
        self.builder.add(OpCode.RET)
