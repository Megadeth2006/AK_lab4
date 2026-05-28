proc on_input() {
    var ch = read_char();
    write_char(ch);
}

proc main() {
    var msg = "OK";
    print_str(msg);

    var a = 2;
    var b = 3;
    var c = 4;
    var d = 5;

    a = a + b;
    c = c + d;

    halt();
}
Сразу выводится "OK".
При приходе входного символа вызывается обработчик on_input().
Инструкции a=a+b и c=c+d могут быть выпущены параллельно.