# tests/test_machine.py
from __future__ import annotations

import pytest

from lab4.binary import ProgramImage, decode_program, encode_program
from lab4.isa import (
    DATA_MEMORY_SIZE_WORDS,
    IO_INPUT_DATA,
    IO_OUTPUT_DATA,
    IO_OUTPUT_STATUS,
    STACK_POINTER,
    WORD_BYTES,
    Instruction,
    OpCode,
    Operand,
)
from lab4.machine import Machine


def test_machine_initial_state() -> None:
    program = ProgramImage(entry_point=16, code=b"\x00\x00")
    machine = Machine(program)

    assert machine.code == b"\x00\x00"
    assert machine.entry_point == 16
    assert machine.pc == 16
    assert len(machine.data_memory) == DATA_MEMORY_SIZE_WORDS * WORD_BYTES
    assert machine.d_regs == [0] * 8
    assert machine.a_regs[0:7] == [0] * 7
    assert machine.a_regs[STACK_POINTER] == DATA_MEMORY_SIZE_WORDS * WORD_BYTES
    assert not machine.n
    assert not machine.z
    assert not machine.v
    assert not machine.c
    assert not machine.halted
    assert machine.tick_counter == 0
    assert machine.log == []


def test_machine_loads_program_data() -> None:
    program = ProgramImage(
        entry_point=0,
        code=b"",
        data=(42, -5, 0x12345678),
    )
    machine = Machine(program)

    assert machine.read_word(0) == 42
    assert machine.read_word(4) == -5
    assert machine.read_word(8) == 0x12345678


def test_read_write_word_success() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    machine.write_word(16, 1234567)
    assert machine.read_word(16) == 1234567

    # Тестируем отрицательные знаковые значения
    machine.write_word(32, -100)
    assert machine.read_word(32) == -100


def test_read_write_word_errors() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.read_word(-4)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.read_word(DATA_MEMORY_SIZE_WORDS * WORD_BYTES)

    with pytest.raises(ValueError, match="must be word-aligned"):
        machine.read_word(2)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.write_word(-4, 42)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.write_word(DATA_MEMORY_SIZE_WORDS * WORD_BYTES, 42)

    with pytest.raises(ValueError, match="must be word-aligned"):
        machine.write_word(3, 42)


def test_push_pop_value() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    initial_sp = machine.a_regs[STACK_POINTER]

    machine.push_value(10)
    assert machine.a_regs[STACK_POINTER] == initial_sp - 4
    assert machine.read_word(initial_sp - 4) == 10

    machine.push_value(-20)
    assert machine.a_regs[STACK_POINTER] == initial_sp - 8
    assert machine.read_word(initial_sp - 8) == -20

    assert machine.pop_value() == -20
    assert machine.a_regs[STACK_POINTER] == initial_sp - 4

    assert machine.pop_value() == 10
    assert machine.a_regs[STACK_POINTER] == initial_sp


def test_push_too_many_values_overflow() -> None:
    program = ProgramImage(entry_point=0, code=b"")
    machine = Machine(program)

    for i in range(DATA_MEMORY_SIZE_WORDS):
        machine.push_value(i)

    with pytest.raises(ValueError, match="out of bounds"):
        machine.push_value(999)


def test_step_nop_and_halt() -> None:
    # Собираем программу: NOP, NOP, HALT
    code = encode_program(
        [
            Instruction(OpCode.NOP),
            Instruction(OpCode.NOP),
            Instruction(OpCode.HALT),
        ]
    )
    program = ProgramImage(entry_point=0, code=code)
    machine = Machine(program)

    # Выполняем первый шаг (NOP)
    machine.step()
    assert machine.tick_counter == 1
    assert machine.pc > 0  # PC сдвинулся на размер NOP
    assert not machine.halted
    assert len(machine.log) == 1
    assert "nop" in machine.log[0]

    # Выполняем второй шаг (NOP)
    machine.step()
    assert machine.tick_counter == 2

    # Выполняем третий шаг (HALT)
    machine.step()
    assert machine.tick_counter == 3
    assert machine.halted
    assert "halt" in machine.log[2]


def test_run_executes_until_halt() -> None:
    code = encode_program(
        [
            Instruction(OpCode.NOP),
            Instruction(OpCode.HALT),
        ]
    )
    program = ProgramImage(entry_point=0, code=code)
    machine = Machine(program)

    machine.run()
    assert machine.halted
    assert machine.tick_counter == 2


def test_execute_move_instructions() -> None:
    # MOVE #40, D0       (40 делится на 4, выровненный базовый адрес)
    # MOVE D0, A0
    # MOVE #100, [A0+4]  (Запись по адресу 44, выровнен по границе слова)
    # MOVE [A0+4], D1
    # HALT
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(40), Operand.dreg(0))),
            Instruction(OpCode.MOVE, (Operand.dreg(0), Operand.areg(0))),
            Instruction(OpCode.MOVE, (Operand.imm(100), Operand.ind_areg_disp(0, 4))),
            Instruction(OpCode.MOVE, (Operand.ind_areg_disp(0, 4), Operand.dreg(1))),
            Instruction(OpCode.HALT),
        ]
    )
    program = ProgramImage(entry_point=0, code=code)
    machine = Machine(program)
    machine.run()

    assert machine.d_regs[0] == 40
    assert machine.a_regs[0] == 40
    assert machine.read_word(44) == 100  # A0(40) + 4 = 44
    assert machine.d_regs[1] == 100
    assert machine.halted
    # Проверяем, что флаги обновились (100 > 0, значит N=False, Z=False)
    assert not machine.n
    assert not machine.z


def test_move_updates_flags() -> None:
    # Тест установки флага Z (MOVE #0, D0)
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(0), Operand.dreg(0))),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()
    assert machine.z
    assert not machine.n

    # Тест установки флага N (MOVE #-1, D0)
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(-1), Operand.dreg(0))),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()
    assert machine.n
    assert not machine.z


def test_execute_lea_instruction() -> None:
    # LEA [0x20], A0 (A0 <- 32)
    # MOVEA #10, A1
    # LEA [A1+8], A2 (A2 <- 18)
    # HALT
    code = encode_program(
        [
            Instruction(OpCode.LEA, (Operand.abs(32), Operand.areg(0))),
            Instruction(OpCode.MOVE, (Operand.imm(10), Operand.areg(1))),
            Instruction(OpCode.LEA, (Operand.ind_areg_disp(1, 8), Operand.areg(2))),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()

    assert machine.a_regs[0] == 32
    assert machine.a_regs[1] == 10
    assert machine.a_regs[2] == 18


def test_execute_push_pop_instructions() -> None:
    # MOVE #50, D0
    # PUSH D0
    # MOVE #0, D0
    # POP D1
    # HALT
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(50), Operand.dreg(0))),
            Instruction(OpCode.PUSH, (Operand.dreg(0),)),
            Instruction(OpCode.MOVE, (Operand.imm(0), Operand.dreg(0))),
            Instruction(OpCode.POP, (Operand.dreg(1),)),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()

    assert machine.d_regs[0] == 0
    assert machine.d_regs[1] == 50


def test_execute_arithmetic_instructions() -> None:
    # MOVE #20, D0
    # ADD #10, D0     (D0 = 30)
    # SUB #5, D0      (D0 = 25)
    # MUL #3, D0      (D0 = 75)
    # DIV #2, D0      (D0 = 37)
    # MOD #10, D0     (D0 = 7)
    # NEG D0          (D0 = -7)
    # HALT
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(20), Operand.dreg(0))),
            Instruction(OpCode.ADD, (Operand.imm(10), Operand.dreg(0))),
            Instruction(OpCode.SUB, (Operand.imm(5), Operand.dreg(0))),
            Instruction(OpCode.MUL, (Operand.imm(3), Operand.dreg(0))),
            Instruction(OpCode.DIV, (Operand.imm(2), Operand.dreg(0))),
            Instruction(OpCode.MOD, (Operand.imm(10), Operand.dreg(0))),
            Instruction(OpCode.NEG, (Operand.dreg(0),)),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()

    assert machine.d_regs[0] == -7
    assert machine.n
    assert not machine.z


def test_division_by_zero_raises_error() -> None:
    # MOVE #10, D0
    # DIV #0, D0
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(10), Operand.dreg(0))),
            Instruction(OpCode.DIV, (Operand.imm(0), Operand.dreg(0))),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    with pytest.raises(ZeroDivisionError, match="Division by zero"):
        machine.run()


def test_add_sub_overflow_flags() -> None:
    # ADD 0x7FFFFFFF, 0x1 -> sets V, C=0, N=1, Z=0 (Overflow)
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(0x7FFFFFFF), Operand.dreg(0))),
            Instruction(OpCode.ADD, (Operand.imm(1), Operand.dreg(0))),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()
    assert machine.v
    assert not machine.c
    assert machine.n

    # SUB 1, 0 -> sets C=1 (Borrow), V=0, N=1
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(0), Operand.dreg(0))),
            Instruction(OpCode.SUB, (Operand.imm(1), Operand.dreg(0))),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()
    assert machine.c
    assert not machine.v
    assert machine.n


def test_cmp_instruction() -> None:
    # MOVE #42, D0
    # CMP #42, D0  -> sets Z=1, but D0 remains 42
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(42), Operand.dreg(0))),
            Instruction(OpCode.CMP, (Operand.imm(42), Operand.dreg(0))),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()
    assert machine.z
    assert machine.d_regs[0] == 42


def test_execute_logical_instructions() -> None:
    # MOVE #0xF0, D0
    # AND #0x3C, D0  -> D0 = 0x30
    # OR #0x0F, D0   -> D0 = 0x3F
    # XOR #0x30, D0  -> D0 = 0x0F
    # NOT D0         -> D0 = ~0x0F
    # SHL #2, D0
    # SHR #2, D0
    # HALT
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(0xF0), Operand.dreg(0))),
            Instruction(OpCode.AND, (Operand.imm(0x3C), Operand.dreg(0))),
            Instruction(OpCode.OR, (Operand.imm(0x0F), Operand.dreg(0))),
            Instruction(OpCode.XOR, (Operand.imm(0x30), Operand.dreg(0))),
            Instruction(OpCode.NOT, (Operand.dreg(0),)),
            Instruction(OpCode.SHL, (Operand.imm(2), Operand.dreg(0))),
            Instruction(OpCode.SHR, (Operand.imm(2), Operand.dreg(0))),
            Instruction(OpCode.HALT),
        ]
    )
    machine = Machine(ProgramImage(entry_point=0, code=code))
    machine.run()

    # ~0x0F is 0xFFFFFFF0.
    # << 2 -> 0xFFFFFFC0 (which is signed -64).
    # >> 2 -> Logical right shift of 0xFFFFFFC0 gives 0x3FFFFFF0 (1073741808)
    assert machine.d_regs[0] == 0x3FFFFFF0


def test_execute_branches_jmp_and_conditional() -> None:
    # Строим тест динамически, чтобы избежать магических смещений байт
    instrs_template = [
        # 0
        Instruction(OpCode.MOVE, (Operand.imm(10), Operand.dreg(0))),
        # 1
        Instruction(OpCode.CMP, (Operand.imm(10), Operand.dreg(0))),
        # 2 (будет запатчен)
        Instruction(OpCode.JE, (Operand.abs(0),)),
        # 3 (пропускается)
        Instruction(OpCode.MOVE, (Operand.imm(1), Operand.dreg(1))),
        # 4 (пропускается)
        Instruction(OpCode.HALT),
        # 5 (цель JE)
        Instruction(OpCode.MOVE, (Operand.imm(2), Operand.dreg(1))),
        # 6
        Instruction(OpCode.CMP, (Operand.imm(5), Operand.dreg(0))),
        # 7 (будет запатчен, не должен сработать)
        Instruction(OpCode.JL, (Operand.abs(0),)),
        # 8 (будет запатчен, безусловный прыжок на конец)
        Instruction(OpCode.JMP, (Operand.abs(0),)),
        # 9 (пропускается)
        Instruction(OpCode.MOVE, (Operand.imm(99), Operand.dreg(1))),
        # 10 (цель безусловного прыжка)
        Instruction(OpCode.HALT),
    ]

    # Шаг 1: кодируем в байты, чтобы узнать точные адреса смещений
    raw_temp = encode_program(instrs_template)
    decoded_info = decode_program(raw_temp)

    target_je = decoded_info[5][0]
    target_jl = decoded_info[9][0]
    target_jmp = decoded_info[10][0]

    # Шаг 2: пересобираем инструкции с корректными целевыми адресами
    instrs_template[2] = Instruction(OpCode.JE, (Operand.abs(target_je),))
    instrs_template[7] = Instruction(OpCode.JL, (Operand.abs(target_jl),))
    instrs_template[8] = Instruction(OpCode.JMP, (Operand.abs(target_jmp),))

    final_code = encode_program(instrs_template)
    machine = Machine(ProgramImage(entry_point=0, code=final_code))
    machine.run()

    # Проверяем правильность выполнения переходов:
    # D1 должен быть равен 2, а не 1 или 99
    assert machine.d_regs[1] == 2
    assert machine.halted


def test_execute_call_ret_subroutine() -> None:
    instrs_template = [
        Instruction(OpCode.MOVE, (Operand.imm(5), Operand.dreg(0))),  # 0
        Instruction(OpCode.CALL, (Operand.abs(0),)),  # 1 (будет запатчен)
        Instruction(OpCode.MUL, (Operand.imm(2), Operand.dreg(0))),  # 2 (возврат сюда!)
        Instruction(OpCode.HALT),  # 3
        # Подпрограмма:
        Instruction(OpCode.ADD, (Operand.imm(10), Operand.dreg(0))),  # 4 (цель вызова)
        Instruction(OpCode.RET),  # 5
    ]

    # Шаг 1: кодируем в байты, чтобы узнать точные адреса смещений
    raw_temp = encode_program(instrs_template)
    decoded_info = decode_program(raw_temp)

    target_sub = decoded_info[4][0]

    # Шаг 2: пересобираем с правильным адресом вызова
    instrs_template[1] = Instruction(OpCode.CALL, (Operand.abs(target_sub),))

    final_code = encode_program(instrs_template)
    machine = Machine(ProgramImage(entry_point=0, code=final_code))
    machine.run()

    # Проверяем: D0 должен стать (5 + 10) * 2 = 30
    assert machine.d_regs[0] == 30
    assert machine.halted


def test_memory_mapped_output() -> None:
    # MOVE #65, D0 (ASCII 'A')
    # MOVE D0, [0xFFFF0008] (Запись в IO_OUTPUT_DATA)
    # MOVE #66, [0xFFFF0008] (Запись ASCII 'B' напрямую)
    # HALT
    code = encode_program(
        [
            Instruction(OpCode.MOVE, (Operand.imm(65), Operand.dreg(0))),
            Instruction(OpCode.MOVE, (Operand.dreg(0), Operand.abs(IO_OUTPUT_DATA))),
            Instruction(OpCode.MOVE, (Operand.imm(66), Operand.abs(IO_OUTPUT_DATA))),
            Instruction(OpCode.HALT),
        ]
    )
    program = ProgramImage(entry_point=0, code=code)
    machine = Machine(program)

    # Проверяем, что порт статуса сообщает о готовности (1)
    assert machine.read_word(IO_OUTPUT_STATUS) == 1

    machine.run()

    # Проверяем буфер вывода
    assert machine.output_buffer == [65, 66]
    # 'AB' в символьном представлении
    output_str = "".join(chr(c) for c in machine.output_buffer)
    assert output_str == "AB"


def test_trap_based_input_interrupts() -> None:
    # Шаблон программы:
    # Вектор прерываний содержит адрес обработчика handler.
    # Основная программа:
    #   0x00: EI                  (Разрешаем прерывания)
    #   loop:
    #   0x01: NOP
    #   0x02: CMP #88, D0         (Ждем, пока D0 станет равен ASCII 'X' = 88)
    #   0x05: JNE loop
    #   0x0B: HALT
    #
    # Обработчик прерывания (handler):
    #   0x0D: MOVE [IO_INPUT_DATA], D0    (Читаем символ из порта ввода)
    #   0x13: MOVE D0, [IO_OUTPUT_DATA]   (Выводим его обратно — эхо)
    #   0x19: IRET                        (Возврат)

    instrs_template = [
        # Основная программа
        Instruction(OpCode.EI),  # 0
        Instruction(OpCode.NOP),  # 1 (метка loop)
        Instruction(OpCode.CMP, (Operand.imm(88), Operand.dreg(0))),  # 2
        Instruction(OpCode.JNE, (Operand.abs(0),)),  # 3 (будет запатчен на адрес loop)
        Instruction(OpCode.HALT),  # 4
        # Обработчик прерывания
        Instruction(
            OpCode.MOVE, (Operand.abs(IO_INPUT_DATA), Operand.dreg(0))
        ),  # 5 (цель прерывания)
        Instruction(OpCode.MOVE, (Operand.dreg(0), Operand.abs(IO_OUTPUT_DATA))),  # 6
        Instruction(OpCode.IRET),  # 7
    ]

    # Шаг 1: Кодируем для определения точных смещений
    raw_temp = encode_program(instrs_template)
    decoded_info = decode_program(raw_temp)

    loop_pc = decoded_info[1][0]
    handler_pc = decoded_info[5][0]

    # Шаг 2: Пересобираем программу
    instrs_template[3] = Instruction(OpCode.JNE, (Operand.abs(loop_pc),))
    final_code = encode_program(instrs_template)

    # Задаем расписание: на такте 15 придет символ 'X' (ASCII 88)
    schedule = [(15, "X")]
    image = ProgramImage(entry_point=0, code=final_code, interrupt_vectors=(handler_pc,))
    machine = Machine(image, input_schedule=schedule)

    machine.run(limit=100)

    # Проверяем успешность
    assert machine.d_regs[0] == 88  # Символ 'X' прочитан в D0
    assert machine.output_buffer == [88]  # Эхо-вывод сработал
    assert machine.halted  # Машина успешно остановилась, выйдя из цикла ожидания

    # Проверяем наличие логов обработки прерываний
    int_logs = [line for line in machine.log if "INT" in line]
    assert len(int_logs) > 0  # Мы заходили в режим INT!
