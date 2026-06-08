from __future__ import annotations

import pytest

from lab4.lexer import Lexer, TokenType


def test_lexer_math_expressions() -> None:
    source = "a = 5 + 10 * x % 2;"
    lexer = Lexer(source)

    expected = [
        (TokenType.IDENTIFIER, "a"),
        (TokenType.ASSIGN, "="),
        (TokenType.NUMBER, "5"),
        (TokenType.PLUS, "+"),
        (TokenType.NUMBER, "10"),
        (TokenType.MUL, "*"),
        (TokenType.IDENTIFIER, "x"),
        (TokenType.MOD, "%"),
        (TokenType.NUMBER, "2"),
        (TokenType.SEMICOLON, ";"),
        (TokenType.EOF, ""),
    ]

    for expected_type, expected_val in expected:
        token = lexer.next_token()
        assert token.type == expected_type
        assert token.value == expected_val


def test_lexer_keywords_and_types() -> None:
    source = 'fn void main() { int x = 42; string s = "hello"; }'
    lexer = Lexer(source)

    expected = [
        (TokenType.FN, "fn"),
        (TokenType.VOID, "void"),
        (TokenType.IDENTIFIER, "main"),
        (TokenType.LPAREN, "("),
        (TokenType.RPAREN, ")"),
        (TokenType.LBRACE, "{"),
        (TokenType.INT, "int"),
        (TokenType.IDENTIFIER, "x"),
        (TokenType.ASSIGN, "="),
        (TokenType.NUMBER, "42"),
        (TokenType.SEMICOLON, ";"),
        (TokenType.STRING_KEYWORD, "string"),
        (TokenType.IDENTIFIER, "s"),
        (TokenType.ASSIGN, "="),
        (TokenType.STRING_LITERAL, "hello"),
        (TokenType.SEMICOLON, ";"),
        (TokenType.RBRACE, "}"),
        (TokenType.EOF, ""),
    ]

    for expected_type, expected_val in expected:
        token = lexer.next_token()
        assert token.type == expected_type
        assert token.value == expected_val


def test_lexer_comparisons() -> None:
    source = "if (x == y != z <= 10) {}"
    lexer = Lexer(source)

    expected = [
        (TokenType.IF, "if"),
        (TokenType.LPAREN, "("),
        (TokenType.IDENTIFIER, "x"),
        (TokenType.EQ, "=="),
        (TokenType.IDENTIFIER, "y"),
        (TokenType.NE, "!="),
        (TokenType.IDENTIFIER, "z"),
        (TokenType.LE, "<="),
        (TokenType.NUMBER, "10"),
        (TokenType.RPAREN, ")"),
        (TokenType.LBRACE, "{"),
        (TokenType.RBRACE, "}"),
        (TokenType.EOF, ""),
    ]

    for expected_type, expected_val in expected:
        token = lexer.next_token()
        assert token.type == expected_type
        assert token.value == expected_val


def test_lexer_ignores_comments() -> None:
    source = """
    // This is a comment
    int x = 10; /* Multi-line
    comment */
    return x;
    """
    lexer = Lexer(source)

    expected = [
        (TokenType.INT, "int"),
        (TokenType.IDENTIFIER, "x"),
        (TokenType.ASSIGN, "="),
        (TokenType.NUMBER, "10"),
        (TokenType.SEMICOLON, ";"),
        (TokenType.RETURN, "return"),
        (TokenType.IDENTIFIER, "x"),
        (TokenType.SEMICOLON, ";"),
        (TokenType.EOF, ""),
    ]

    for expected_type, expected_val in expected:
        token = lexer.next_token()
        assert token.type == expected_type
        assert token.value == expected_val


def test_lexer_invalid_character() -> None:
    lexer = Lexer("int x = 10 @ 5;")
    lexer.next_token()  # int
    lexer.next_token()  # x
    lexer.next_token()  # =
    lexer.next_token()  # 10

    with pytest.raises(ValueError, match="Unexpected character: '@'"):
        lexer.next_token()


def test_lexer_unterminated_string() -> None:
    lexer = Lexer('string s = "hello')
    lexer.next_token()  # string
    lexer.next_token()  # s
    lexer.next_token()  # =

    with pytest.raises(ValueError, match="Unterminated string literal"):
        lexer.next_token()
