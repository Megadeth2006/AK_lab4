fn void on_input() {
    int char = read_io(4294901760); // IO_INPUT_DATA
    if (char == 10) { // '\n'
        write_io(1008, 1); // выставляем флаг input_done (адрес 1008) в 1
    } else {
        if (char == 13) { // '\r'
            write_io(1008, 1);
        } else {
            int name_buf = read_io(1000); // адрес буфера лежит в ячейке 1000
            int char_count = read_io(1004); // текущая длина лежит в ячейке 1004
            int addr = name_buf + 4 + char_count * 4;
            write_io(addr, char);
            write_io(1004, char_count + 1); // инкрементируем char_count
        }
    }
}

fn void main() {
    int name_buf = allocate_buffer(33);
    write_io(1000, name_buf); // сохраняем адрес буфера в ячейку 1000
    write_io(1004, 0);        // char_count = 0 в ячейку 1004
    write_io(1008, 0);        // input_done = 0 в ячейку 1008

    print_string("What is your name?\n");
    enable_interrupts();

    // Ожидаем окончания ввода (пока в ячейке 1008 не появится 1)
    while (read_io(1008) == 0) {
        int idle = 0;
    }
    disable_interrupts();

    int final_count = read_io(1004);
    write_io(name_buf, final_count); // записываем длину в Pascal string

    print_string("Hello, ");
    print_string(name_buf);
    print_string("!\n");
}