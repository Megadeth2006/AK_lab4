// Адреса портов ввода-вывода
int IO_INPUT_DATA = 4294901760;   // 0xFFFF0000
int IO_OUTPUT_DATA = 4294901768;  // 0xFFFF0008

fn void on_input() {
    // Читаем символ из порта ввода
    int char = read_io(IO_INPUT_DATA);
    // Сразу пишем его в порт вывода
    write_io(IO_OUTPUT_DATA, char);
}

fn void main() {
    enable_interrupts();
    // Бесконечный цикл ожидания прерываний ввода
    while (1 == 1) {
        int idle = 0;
    }
}