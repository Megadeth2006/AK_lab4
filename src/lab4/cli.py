# src/lab4/cli.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lab4.binary import ProgramImage
from lab4.compiler import Compiler
from lab4.disasm import disassemble_image
from lab4.lexer import Lexer
from lab4.machine import Machine
from lab4.parser import Parser


def load_input_schedule(path: Path) -> list[tuple[int, str]]:
    """Чтение текстового файла ввода и планирование
    прерываний по одному символу каждые 10 тактов."""
    text = path.read_text(encoding="utf-8")
    schedule: list[tuple[int, str]] = []
    for i, char in enumerate(text):
        # Первый символ придет на такте 10, второй на 20 и т.д.
        schedule.append((10 + i * 10, char))
    return schedule


def main() -> None:
    parser = argparse.ArgumentParser(prog="lab4")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Команда деассемблирования
    disasm_parser = subparsers.add_parser("disasm", help="disassemble a binary program image")
    disasm_parser.add_argument("binary", type=Path)
    disasm_parser.add_argument("output", type=Path, nargs="?")

    # 2. Команда трансляции (компиляции)
    translate_parser = subparsers.add_parser(
        "translate", help="translate alg source code to binary image"
    )
    translate_parser.add_argument("source", type=Path)
    translate_parser.add_argument("binary", type=Path)

    # 3. Команда запуска симуляции
    run_parser = subparsers.add_parser("run", help="run binary image in tick-accurate simulator")
    run_parser.add_argument("binary", type=Path)
    run_parser.add_argument("input", type=Path, nargs="?", help="optional plain-text input file")
    run_parser.add_argument("output", type=Path, nargs="?", help="optional log/output result file")

    args = parser.parse_args()

    match args.command:
        case "disasm":
            image = ProgramImage.from_bytes(args.binary.read_bytes())
            text = disassemble_image(image)
            if args.output is None:
                sys.stdout.write(text + "\n")
            else:
                args.output.write_text(text + "\n", encoding="utf-8")

        case "translate":
            # Считываем исходный код
            source_code = args.source.read_text(encoding="utf-8")

            # Лексический, синтаксический анализ и компиляция
            lexer = Lexer(source_code)
            parser_obj = Parser(lexer)
            program = parser_obj.parse()

            compiler = Compiler()
            image = compiler.compile(program)

            # Запись бинарного образа в файл
            args.binary.write_bytes(image.to_bytes())
            sys.stdout.write(
                f"Successfully compiled {len(source_code.splitlines())} lines of code.\n"
            )
            sys.stdout.write(f"Binary size: {len(image.to_bytes())} bytes.\n")

        case "run":
            # Считываем бинарный образ
            image = ProgramImage.from_bytes(args.binary.read_bytes())

            # Подготовка асинхронного расписания ввода
            schedule = []
            if args.input:
                schedule = load_input_schedule(args.input)

            # Запуск симулятора
            machine = Machine(image, input_schedule=schedule)
            machine.run(limit=50000)  # Безопасный лимит тактов

            output_text = "".join(chr(c) for c in machine.output_buffer)
            log_text = "\n".join(machine.log)

            if args.output:
                # Записываем результат и логи в файл
                result_text = f"OUTPUT \n{output_text}\n\nLOG\n{log_text}"
                args.output.write_text(result_text, encoding="utf-8")
                sys.stdout.write(
                    f"""Simulation completed. Ticks: {machine.tick_counter}.
                    Results saved to {args.output}\n"""
                )
            else:
                # Печатаем вывод прямо в консоль
                sys.stdout.write("SIMULATION OUTPUT\n")
                sys.stdout.write(output_text + "\n")
                sys.stdout.write("----\n")
                sys.stdout.write(f"Total ticks: {machine.tick_counter}\n")

        case _:
            msg = "argparse should reject unknown commands"
            raise AssertionError(msg)


if __name__ == "__main__":
    main()
