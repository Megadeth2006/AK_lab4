// Читает число N из ввода и вычисляет разность между квадратом суммы и суммой квадратов
int IO_INPUT_DATA = 4294901760;

int n = 0;
int input_done = 0;

fn void on_input() {
    int char = read_io(IO_INPUT_DATA);
    if (char >= 48) {
        if (char <= 57) {
            n = n * 10 + (char - 48);
        } else {
            if (char == 35) { // Конец ввода '#'
                input_done = 1;
            }
        }
    }
}

fn void main() {
    n = 0;
    input_done = 0;

    enable_interrupts();
    while (input_done == 0) {
        int idle = 0;
    }
    disable_interrupts();

    // Вычисляем:
    // Сумма чисел: sum = n * (n + 1) / 2
    // Квадрат суммы: sum_sq = sum * sum
    // Сумма квадратов: sq_sum = n * (n + 1) * (2n + 1) / 6
    int sum = n * (n + 1) / 2;
    int sum_sq = sum * sum;
    int sq_sum = n * (n + 1) * (2 * n + 1) / 6;

    int diff = sum_sq - sq_sum;
    print_int(diff);
}