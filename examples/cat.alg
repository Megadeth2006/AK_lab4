fn void on_input() {
    // 4294901760 — это 0xFFFF0000 (IO_INPUT_DATA)
    int char = read_io(4294901760);
    // 4294901768 — это 0xFFFF0008 (IO_OUTPUT_DATA)
    write_io(4294901768, char);
}

fn void main() {
    enable_interrupts();
    while (1 == 1) {
        int idle = 0;
    }
}