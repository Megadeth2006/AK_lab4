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


def test_compile_and_run_if_else() -> None:
    # Тестируем условные конструкции (if/else)
    source = """
    fn int max(int a, int b) {
        if (a > b) {
            return a;
        } else {
            return b;
        }
    }

    fn int main() {
        return max(15, 42);
    }
    """
    lexer = Lexer(source)
    parser = Parser(lexer)
    program = parser.parse()

    compiler = Compiler()
    image = compiler.compile(program)

    machine = Machine(image)
    machine.run()

    # Должен вернуться больший элемент: 42
    assert machine.d_regs[0] == 42
    assert machine.halted


def test_compile_and_run_while_loop() -> None:
    # Тестируем цикл while: вычисление факториала 5 (5! = 120)
    source = """
    fn int main() {
        int n = 5;
        int result = 1;
        while (n > 1) {
            result = result * n;
            n = n - 1;
        }
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

    assert machine.d_regs[0] == 120
    assert machine.halted


def test_compile_and_run_print_string() -> None:
    # Тестируем печать Pascal-строк из статической памяти
    source = """
    fn void main() {
        string msg = "Hello from alg!";
        print_string(msg);
    }
    """
    lexer = Lexer(source)
    parser = Parser(lexer)
    program = parser.parse()

    compiler = Compiler()
    image = compiler.compile(program)

    # Проверяем, что в статической памяти есть длина (15) и символы
    assert image.data[0] == 15
    assert image.data[1] == ord("H")

    machine = Machine(image)
    machine.run()

    # Сверяем буфер вывода
    output_str = "".join(chr(c) for c in machine.output_buffer)
    assert output_str == "Hello from alg!"


def test_compile_and_run_print_int() -> None:
    # Тестируем вывод знаковых чисел
    source = """
    fn void main() {
        print_int(-12345);
    }
    """
    lexer = Lexer(source)
    parser = Parser(lexer)
    program = parser.parse()

    compiler = Compiler()
    image = compiler.compile(program)

    machine = Machine(image)
    machine.run()

    output_str = "".join(chr(c) for c in machine.output_buffer)
    assert output_str == "-12345"
