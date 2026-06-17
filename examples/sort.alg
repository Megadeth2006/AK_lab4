// Считываем числа, разделенные пробелами, сортируем пузырьком и выводим
int IO_INPUT_DATA = 4294901760;

int array_buf = 0;
int array_size = 0;
int current_val = 0;
int reading_digits = 0;
int input_done = 0;

fn void on_input() {
    int char = read_io(IO_INPUT_DATA);
    if (char >= 48) {
        if (char <= 57) {
            // Читаем цифру
            current_val = current_val * 10 + (char - 48);
            reading_digits = 1;
        } else {
            // Символ окончания ввода '#' (ASCII 35)
            if (char == 35) {
                if (reading_digits == 1) {
                    write_io(array_buf + array_size * 4, current_val);
                    array_size = array_size + 1;
                }
                input_done = 1;
            }
        }
    } else {
        // Пробел или разделитель
        if (reading_digits == 1) {
            write_io(array_buf + array_size * 4, current_val);
            array_size = array_size + 1;
            current_val = 0;
            reading_digits = 0;
        }
    }
}

fn void main() {
    array_buf = allocate_buffer(50);
    array_size = 0;
    current_val = 0;
    reading_digits = 0;
    input_done = 0;

    enable_interrupts();
    while (input_done == 0) {
        int idle = 0;
    }
    disable_interrupts();

    // Сортировка пузырьком
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

    // Выводим отсортированный массив
    int k = 0;
    while (k < array_size) {
        int val = read_io(array_buf + k * 4);
        print_int(val);
        print_string(" ");
        k = k + 1;
    }
}