int IO_INPUT_DATA = 4294901760;

int name_buf = 0;
int char_count = 0;
int input_done = 0;

fn void on_input() {
    int char = read_io(IO_INPUT_DATA);
    // Если встретили символ новой строки '\n' (ASCII 10) или возврат каретки (13)
    if (char == 10) {
        input_done = 1;
    } else {
        if (char == 13) {
            input_done = 1;
        } else {
            // Пишем символ в буфер: name_buf + 4 + char_count*4
            int addr = name_buf + 4 + char_count * 4;
            write_io(addr, char);
            char_count = char_count + 1;
        }
    }
}

fn void main() {
    // Выделяем буфер под строку (1 слово под длину + 32 под символы)
    name_buf = allocate_buffer(33);
    char_count = 0;
    input_done = 0;

    print_string("What is your name?\n");
    enable_interrupts();

    // Ожидаем окончания ввода по прерыванию
    while (input_done == 0) {
        int idle = 0;
    }
    disable_interrupts();

    // Записываем длину строки в первое слово буфера (Pascal layout)
    write_io(name_buf, char_count);

    print_string("Hello, ");
    print_string(name_buf);
    print_string("!\n");
}