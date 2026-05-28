proc main() {
    var x = 0;
    var sum = 0;

    while (x < 10) {
        if ((x % 2) == 0) {
            sum = sum + x;
        }
        x = x + 1;
    }

    print_num(sum);
}

Ожидаемый вывод: 20
Покрывает: literals, арифметику, if, while, print_num