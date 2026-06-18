# tests/test_golden.py
from __future__ import annotations

import os
from pathlib import Path
import pytest

from lab4.binary import ProgramImage
from lab4.compiler import Compiler
from lab4.disasm import disassemble_image, disassemble_code
from lab4.lexer import Lexer
from lab4.machine import Machine
from lab4.parser import Parser

# Папки для исходников и эталонов
EXAMPLES_DIR = Path("examples")
GOLDEN_DIR = Path("golden")


def load_input_schedule(text: str) -> list[tuple[int, str]]:
    """Преобразование строки ввода в асинхронное расписание прерываний (по символу каждые 150 тактов, начиная с 500)."""
    schedule: list[tuple[int, str]] = []
    for i, char in enumerate(text):
        # Начинаем с 500-го такта, чтобы программа успела завершить вывод 
        # приветствия и аппаратно разрешить прерывания (вызвать EI)
        schedule.append((500 + i * 150, char))
    return schedule


def save_as_golden_yaml(path: Path, data: dict[str, str]) -> None:
    """Запись структуры в файл YAML с сохранением блочного форматирования '|' для многострочных полей."""
    content = []
    for key in ["source_code", "disassembly", "input", "schedule", "expected_stdout", "log_journal"]:
        val = data[key]
        # Если в значении есть переносы строк, форматируем как блок '|'
        if "\n" in val or key in ("source_code", "disassembly", "expected_stdout", "log_journal"):
            content.append(f"{key}: |")
            for line in val.splitlines():
                content.append(f"  {line}")
        else:
            content.append(f'{key}: "{val}"')
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


def parse_golden_yaml(path: Path) -> dict[str, str]:
    """Быстрый и надежный парсер YAML без внешних зависимостей для нашей структуры."""
    lines = path.read_text(encoding="utf-8").splitlines()
    data: dict[str, str] = {}
    current_key = None
    current_block: list[str] = []

    for line in lines:
        if line.startswith(("source_code:", "disassembly:", "input:", "schedule:", "expected_stdout:", "log_journal:")):
            if current_key:
                data[current_key] = "\n".join(current_block)
            parts = line.split(":", 1)
            current_key = parts[0].strip()
            val_part = parts[1].strip()
            if val_part == "|":
                current_block = []
            else:
                # Однострочное значение в кавычках
                current_block = [val_part.strip('"')]
        else:
            if line.startswith("  "):
                current_block.append(line[2:])
            elif line.strip() == "":
                current_block.append("")

    if current_key:
        data[current_key] = "\n".join(current_block)

    return data


def generate_harvard_memory_dump(machine: Machine, image: ProgramImage) -> str:
    """Генерация красивого и детального дампа Гарвардской памяти."""
    dump_lines = [
        "HARVARD MEMORY DUMP",
        "INSTRUCTION MEMORY (Code Section):",
    ]
    # Добавляем деассемблирование кода
    dis_code = disassemble_code(image.code)
    for line in dis_code.splitlines():
        dump_lines.append(f"   {line}")

    dump_lines.append("--------------------------------------------------------------------------------")
    dump_lines.append("DATA MEMORY (Used Non-Zero Words & Active Stack):")

    # Считываем используемые ячейки памяти данных
    # Выводим статические переменные из начала памяти
    for addr in range(0, machine.data_memory_size, 4):
        val = machine.read_word(addr)
        if val != 0 or addr < len(image.data) * 4:
            # Пытаемся представить в виде ASCII символа
            char_repr = f"'{chr(val)}'" if 32 <= val <= 126 else " "
            dump_lines.append(f"   [{addr:04X}]: {val:<10} {char_repr:<5} (STATIC/GLOBAL)")

    # Считываем ячейки стека в конце памяти
    stack_start = machine.a_regs[7]
    for addr in range(stack_start, machine.data_memory_size, 4):
        val = machine.read_word(addr)
        dump_lines.append(f"   [{addr:04X}]: {val:<10}       (STACK)")

    return "\n".join(dump_lines)


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
def test_golden_scenarios(program_name: str, input_data: str) -> None:
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

    # 3. Деассемблируем
    disassembly = disassemble_image(image)

    # 4. Запускаем симуляцию
    schedule = load_input_schedule(input_data)
    machine = Machine(image, input_schedule=schedule)
    machine.run(limit=50000)

    # 5. Собираем stdout
    output_text = "".join(chr(c) for c in machine.output_buffer)
    expected_stdout = (
        f"=== SIMULATION OUTPUT ===\n"
        f"{output_text}\n"
        f"=========================\n"
        f"Total ticks: {machine.tick_counter}"
    )

    # 6. Собираем потактовый журнал выполнения и дамп памяти
    # Берем первые 100 строк лога для компактности
    truncated_log = "\n".join(machine.log[:100])
    if len(machine.log) > 100:
        truncated_log += f"\n... [Truncated: total {len(machine.log)} lines] ..."

    # Формируем красивый дамп Гарвардской памяти
    mem_dump = generate_harvard_memory_dump(machine, image)

    log_journal = (
        f"{truncated_log}\n"
        f"--------------------------------------------------------------------------------\n"
        f"Finished at tick {machine.tick_counter}\n"
        f"{mem_dump}"
    )

    # Готовим структуру для YAML
    golden_data = {
        "source_code": source_code,
        "disassembly": disassembly,
        "input": input_data,
        "schedule": "",
        "expected_stdout": expected_stdout,
        "log_journal": log_journal,
    }

    # Путь к файлу в корневой папке golden/
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_file = GOLDEN_DIR / f"{program_name}.yaml"

    # Если включен режим обновления или файла нет — записываем его
    if os.environ.get("UPDATE_GOLDEN") == "1" or not golden_file.exists():
        save_as_golden_yaml(golden_file, golden_data)

    # Считываем эталон и сверяем
    expected_data = parse_golden_yaml(golden_file)

    assert golden_data["source_code"].strip() == expected_data["source_code"].strip()
    assert golden_data["disassembly"].strip() == expected_data["disassembly"].strip()
    assert golden_data["expected_stdout"].strip() == expected_data["expected_stdout"].strip()
    assert golden_data["log_journal"].strip() == expected_data["log_journal"].strip()