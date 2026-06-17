fn void on_input() {
    int char = read_io(4294901760); // IO_INPUT_DATA
    if (char == 10) { // '\n'
        write_io(8, 1); // выставляем флаг input_done (адрес 8) в 1
    } else {
        if (char == 13) { // '\r'
            write_io(8, 1);
        } else {
            int name_buf = read_io(0); // адрес буфера лежит в ячейке 0
            int char_count = read_io(4); // текущая длина лежит в ячейке 4
            int addr = name_buf + 4 + char_count * 4;
            write_io(addr, char);
            write_io(4, char_count + 1); // инкрементируем char_count
        }
    }
}

fn void main() {
    int name_buf = allocate_buffer(33);
    write_io(0, name_buf); // сохраняем адрес буфера в ячейку 0
    write_io(4, 0);        // char_count = 0 в ячейку 4
    write_io(8, 0);        // input_done = 0 в ячейку 8

    print_string("What is your name?\n");
    enable_interrupts();

    // Ожидаем окончания ввода (пока в ячейке 8 не появится 1)
    while (read_io(8) == 0) {
        int idle = 0;
    }
    disable_interrupts();

    int final_count = read_io(4);
    write_io(name_buf, final_count); // записываем длину в Pascal string

    print_string("Hello, ");
    print_string(name_buf);
    print_string("!\n");
}