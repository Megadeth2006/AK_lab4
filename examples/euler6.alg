fn void on_input() {
    int char = read_io(4294901760);
    if (char >= 48) {
        if (char <= 57) {
            int n = read_io(0);
            n = n * 10 + (char - 48);
            write_io(0, n);
        } else {
            if (char == 35) { // '#'
                write_io(4, 1); // input_done = 1
            }
        }
    }
}

fn void main() {
    write_io(0, 0); // n = 0
    write_io(4, 0); // input_done = 0

    enable_interrupts();
    while (read_io(4) == 0) {
        int idle = 0;
    }
    disable_interrupts();

    int final_n = read_io(0);
    int sum = final_n * (final_n + 1) / 2;
    int sum_sq = sum * sum;
    int sq_sum = final_n * (final_n + 1) * (2 * final_n + 1) / 6;

    int diff = sum_sq - sq_sum;
    print_int(diff);
}