# tests/test_golden.py
from __future__ import annotations

import os
from pathlib import Path

import pytest

from lab4.compiler import Compiler
from lab4.disasm import disassemble_image
from lab4.lexer import Lexer
from lab4.machine import Machine
from lab4.parser import Parser

# Папка с исходными кодами алгоритмов
EXAMPLES_DIR = Path("examples")
# Папка для хранения эталонных "golden" файлов
GOLDEN_DIR = Path("tests") / "golden"


def load_input_schedule(text: str) -> list[tuple[int, str]]:
    """Преобразование строки ввода в асинхронное
    расписание прерываний (по символу каждые 10 тактов)."""
    schedule: list[tuple[int, str]] = []
    for i, char in enumerate(text):
        schedule.append((10 + i * 10, char))
    return schedule


@pytest.mark.parametrize(
    "program_name,input_data",
    [
        ("hello", ""),
        ("cat", "hello"),
        ("hello_user_name", "Alice\n"),
        ("sort", "42 12 1 99 5 #"),
        ("math64", ""),
        ("euler6", "10#"),
    ],
)
def test_golden_algorithms(program_name: str, input_data: str) -> None:
    # 1. Читаем исходный код на языке alg
    source_file = EXAMPLES_DIR / f"{program_name}.alg"
    assert source_file.exists(), f"Source file {source_file} not found"
    source_code = source_file.read_text(encoding="utf-8")

    # 2. Компилируем
    lexer = Lexer(source_code)
    parser = Parser(lexer)
    program = parser.parse()
    compiler = Compiler()
    image = compiler.compile(program)

    # 3. Деассемблируем бинарный образ для эталона
    disassembly = disassemble_image(image)

    # 4. Запускаем симуляцию
    schedule = load_input_schedule(input_data)
    machine = Machine(image, input_schedule=schedule)
    machine.run(limit=50000)

    # 5. Собираем результаты симуляции
    output_text = "".join(chr(c) for c in machine.output_buffer)
    # Берем первые 100 строк лога для компактности файлов эталонов
    truncated_log = "\n".join(machine.log[:100])
    if len(machine.log) > 100:
        truncated_log += f"\n... [Truncated: total {len(machine.log)} lines] ..."

    # 6. Формируем единый текст эталона
    golden_content = (
        f"=== SOURCE ===\n{source_code}\n"
        f"=== INPUT ===\n{input_data}\n"
        f"=== DISASSEMBLY ===\n{disassembly}\n"
        f"=== OUTPUT ===\n{output_text}\n"
        f"=== LOG (FIRST 100 LINES) ===\n{truncated_log}\n"
    )

    # Путь к golden-файлу
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_file = GOLDEN_DIR / f"{program_name}.golden"

    # Если включен режим обновления или файла нет — записываем его
    if os.environ.get("UPDATE_GOLDEN") == "1" or not golden_file.exists():
        golden_file.write_text(golden_content, encoding="utf-8")

    # Сверяем текущий результат с эталоном
    expected_content = golden_file.read_text(encoding="utf-8")
    assert golden_content == expected_content
