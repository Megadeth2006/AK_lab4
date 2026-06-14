# tests/test_compiler.py
from __future__ import annotations

from lab4.compiler import Compiler
from lab4.lexer import Lexer
from lab4.machine import Machine
from lab4.parser import Parser


def test_compile_and_run_simple_addition() -> None:
    # Исходный код на языке alg: объявляем переменные, складываем и возвращаем
    source = """
    fn int main() {
        int x = 12;
        int y = 30;
        return x + y;
    }
    """
    lexer = Lexer(source)
    parser = Parser(lexer)
    program = parser.parse()

    # Компилируем в бинарный образ
    compiler = Compiler()
    image = compiler.compile(program)

    # Запускаем симуляцию на процессоре
    machine = Machine(image)
    machine.run()

    # Результат выполнения main (из регистра D0) должен быть равен 12 + 30 = 42
    assert machine.d_regs[0] == 42
    assert machine.halted


def test_compile_and_run_nested_expressions_and_params() -> None:
    # Тестируем передачу параметров, вложенные выражения и унарный минус
    source = """
    fn int add_triple(int a, int b) {
        int temp = a + b;
        return temp * -3;
    }

    fn int main() {
        int result = add_triple(2, 8);
        return result;
    }
    """
    lexer = Lexer(source)
    parser = Parser(lexer)
    program = parser.parse()

    compiler = Compiler()
    image = compiler.compile(program)

    machine = Machine(image)
    machine.run()

    # (2 + 8) * -3 = -30
    assert machine.d_regs[0] == -30
    assert machine.halted
