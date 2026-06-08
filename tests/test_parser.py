# tests/test_parser.py
from __future__ import annotations

import pytest

from lab4.lexer import Lexer
from lab4.parser import Parser


def test_parser_arithmetic_precedence() -> None:
    # 5 + 10 * x должны сгруппироваться как 5 + (10 * x)
    lexer = Lexer("fn void main() { int res = 5 + 10 * x; }")
    parser = Parser(lexer)
    program = parser.parse()

    ast_dict = program.to_dict()

    # Извлекаем узел математического выражения
    var_decl = ast_dict["funcs"][0]["body"]["statements"][0]
    assert var_decl["type"] == "VarDecl"
    assert var_decl["name"] == "res"

    init_expr = var_decl["init"]
    assert init_expr["type"] == "BinOp"
    assert init_expr["op"] == "+"
    assert init_expr["left"]["type"] == "NumLiteral"
    assert init_expr["left"]["value"] == 5

    assert init_expr["right"]["type"] == "BinOp"
    assert init_expr["right"]["op"] == "*"
    assert init_expr["right"]["left"]["type"] == "NumLiteral"
    assert init_expr["right"]["left"]["value"] == 10


def test_parser_function_declaration() -> None:
    source = "fn int sum(int a, string b) { return a; }"
    lexer = Lexer(source)
    parser = Parser(lexer)
    program = parser.parse()

    func = program.funcs[0]
    assert func.name == "sum"
    assert func.return_type == "int"
    assert len(func.params) == 2
    assert func.params[0].name == "a"
    assert func.params[0].type_name == "int"
    assert func.params[1].name == "b"
    assert func.params[1].type_name == "string"


def test_parser_control_structures() -> None:
    source = """
    fn void test() {
        while (x < 10) {
            if (x == 5) {
                print(x);
            } else {
                x = x + 1;
            }
        }
    }
    """
    lexer = Lexer(source)
    parser = Parser(lexer)
    program = parser.parse()

    ast_dict = program.to_dict()
    statements = ast_dict["funcs"][0]["body"]["statements"]

    assert len(statements) == 1
    while_node = statements[0]
    assert while_node["type"] == "While"
    assert while_node["cond"]["type"] == "BinOp"
    assert while_node["cond"]["op"] == "<"

    if_node = while_node["body"]["statements"][0]
    assert if_node["type"] == "If"
    assert if_node["cond"]["op"] == "=="
    assert if_node["else_branch"] is not None


def test_parser_syntax_error_unclosed_paren() -> None:
    lexer = Lexer("fn void main() { int x = (5 + 10; }")
    parser = Parser(lexer)

    with pytest.raises(ValueError, match="Expected '\\)' after group expression"):
        parser.parse()


def test_parser_invalid_return_type() -> None:
    lexer = Lexer("fn float compute() { return 0; }")
    parser = Parser(lexer)

    with pytest.raises(ValueError, match="Expected return type"):
        parser.parse()
