fn void on_input() {
    int char = read_io(4294901760); // IO_INPUT_DATA
    if (char >= 48) {
        if (char <= 57) {
            int current_val = read_io(1008);
            current_val = current_val * 10 + (char - 48);
            write_io(1008, current_val);
            write_io(1012, 1); // reading_digits = 1
        } else {
            if (char == 35) { // '#' - завершение ввода
                if (read_io(1012) == 1) {
                    int array_buf = read_io(1000);
                    int array_size = read_io(1004);
                    write_io(array_buf + array_size * 4, read_io(1008));
                    write_io(1004, array_size + 1);
                }
                write_io(1016, 1); // input_done = 1
            }
        }
    } else {
        // Пробел или перевод строки
        if (read_io(1012) == 1) {
            int array_buf = read_io(1000);
            int array_size = read_io(1004);
            write_io(array_buf + array_size * 4, read_io(1008));
            write_io(1004, array_size + 1);
            write_io(1008, 0);  // current_val = 0
            write_io(1012, 0); // reading_digits = 0
        }
    }
}

fn void main() {
    int array_buf = allocate_buffer(50);
    write_io(1000, array_buf);
    write_io(1004, 0);  // array_size = 0
    write_io(1008, 0);  // current_val = 0
    write_io(1012, 0); // reading_digits = 0
    write_io(1016, 0); // input_done = 0

    enable_interrupts();
    while (read_io(1016) == 0) {
        int idle = 0;
    }
    disable_interrupts();

    // Пузырьковая сортировка
    int array_size = read_io(1004);
    int i = 0;
    while (i < array_size) {
        int j = 0;
        while (j < array_size - 1 - i) {
            int addr1 = array_buf + j * 4;
            int addr2 = array_buf + (j + 1) * 4;
            int val1 = read_io(addr1);
            int val2 = read_io(addr2);
            if (val1 > val2) {
                write_io(addr1, val2);
                write_io(addr2, val1);
            }
            j = j + 1;
        }
        i = i + 1;
    }

    // Вывод отсортированного массива
    int k = 0;
    while (k < array_size) {
        int val = read_io(array_buf + k * 4);
        print_int(val);
        print_string(" ");
        k = k + 1;
    }
}