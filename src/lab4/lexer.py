from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Ключевые слова (Keywords)
    FN = auto()
    INT = auto()
    STRING_KEYWORD = auto()  # Ключевое слово "string"
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    RETURN = auto()
    VOID = auto()

    # Литералы
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING_LITERAL = auto()

    # Операторы
    PLUS = auto()
    MINUS = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    ASSIGN = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()

    # Пунктуация
    SEMICOLON = auto()
    COMMA = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()

    EOF = auto()


# Словарь для быстрого поиска ключевых слов
KEYWORDS: dict[str, TokenType] = {
    "fn": TokenType.FN,
    "int": TokenType.INT,
    "string": TokenType.STRING_KEYWORD,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "return": TokenType.RETURN,
    "void": TokenType.VOID,
}


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    value: str
    line: int
    column: int


class Lexer:
    """Лексический анализатор для языка alg (посимвольный сканер)."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1
        self.length = len(source)

    def next_token(self) -> Token:
        """Получение следующего токена из исходного кода."""
        self._skip_whitespace_and_comments()

        if self.position >= self.length:
            return Token(TokenType.EOF, "", self.line, self.column)

        char = self.source[self.position]
        start_column = self.column

        # 1. Строковые литералы
        if char == '"':
            return self._read_string_literal()

        # 2. Числа (целые беззнаковые на этапе лексера, унарный минус обрабатывается парсером)
        if char.isdigit():
            return self._read_number()

        # 3. Идентификаторы и ключевые слова
        if char.isalpha() or char == "_":
            return self._read_identifier_or_keyword()

        # 4. Двухсимвольные и односимвольные операторы
        if char == "=":
            if self._peek() == "=":
                self._advance(2)
                return Token(TokenType.EQ, "==", self.line, start_column)
            self._advance()
            return Token(TokenType.ASSIGN, "=", self.line, start_column)

        if char == "!":
            if self._peek() == "=":
                self._advance(2)
                return Token(TokenType.NE, "!=", self.line, start_column)
            error_msg = f"Unexpected character: '{char}'"
            raise ValueError(error_msg)

        if char == "<":
            if self._peek() == "=":
                self._advance(2)
                return Token(TokenType.LE, "<=", self.line, start_column)
            self._advance()
            return Token(TokenType.LT, "<", self.line, start_column)

        if char == ">":
            if self._peek() == "=":
                self._advance(2)
                return Token(TokenType.GE, ">=", self.line, start_column)
            self._advance()
            return Token(TokenType.GT, ">", self.line, start_column)

        # Односимвольные операторы и пунктуация
        single_chars: dict[str, TokenType] = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.MUL,
            "/": TokenType.DIV,
            "%": TokenType.MOD,
            ";": TokenType.SEMICOLON,
            ",": TokenType.COMMA,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
        }

        if char in single_chars:
            self._advance()
            return Token(single_chars[char], char, self.line, start_column)

        error_msg = f"Unexpected character: '{char}'"
        raise ValueError(error_msg)

    def _advance(self, steps: int = 1) -> None:
        """Продвижение указателя сканера вперед."""
        for _ in range(steps):
            if self.position < self.length:
                if self.source[self.position] == "\n":
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.position += 1

    def _peek(self) -> str:
        """Посмотреть на следующий символ без сдвига указателя."""
        if self.position + 1 >= self.length:
            return ""
        return self.source[self.position + 1]

    def _skip_whitespace_and_comments(self) -> None:
        """Пропуск пробелов, табов, переводов строк и комментариев."""
        while self.position < self.length:
            char = self.source[self.position]

            # Пропуск пробелов
            if char.isspace():
                self._advance()
                continue

            # Пропуск однострочных и многострочных комментариев
            if char == "/":
                next_char = self._peek()
                if next_char == "/":
                    # Однострочный комментарий //
                    self._advance(2)
                    while self.position < self.length and self.source[self.position] != "\n":
                        self._advance()
                    continue
                if next_char == "*":
                    # Многострочный комментарий /* ... */
                    self._advance(2)
                    closed = False
                    while self.position < self.length:
                        if self.source[self.position] == "*" and self._peek() == "/":
                            self._advance(2)
                            closed = True
                            break
                        self._advance()
                    if not closed:
                        error_msg = "Unterminated multi-line comment"
                        raise ValueError(error_msg)
                    continue

            break

    def _read_string_literal(self) -> Token:
        """Чтение строкового литерала в двойных кавычках."""
        start_column = self.column
        self._advance()  # Пропускаем открывающую кавычку "
        start_pos = self.position

        while self.position < self.length and self.source[self.position] != '"':
            if self.source[self.position] == "\n":
                error_msg = "Newline is not allowed in string literal"
                raise ValueError(error_msg)

            self._advance()

        if self.position >= self.length:
            error_msg = "Unterminated string literal"
            raise ValueError(error_msg)

        value = self.source[start_pos : self.position]
        self._advance()  # Пропускаем закрывающую кавычку "
        return Token(TokenType.STRING_LITERAL, value, self.line, start_column)

    def _read_number(self) -> Token:
        """Чтение беззнакового целого числа."""
        start_column = self.column
        start_pos = self.position
        while self.position < self.length and self.source[self.position].isdigit():
            self._advance()
        value = self.source[start_pos : self.position]
        return Token(TokenType.NUMBER, value, self.line, start_column)

    def _read_identifier_or_keyword(self) -> Token:
        """Чтение идентификатора или ключевого слова."""
        start_column = self.column
        start_pos = self.position
        while self.position < self.length:
            char = self.source[self.position]
            if char.isalnum() or char == "_":
                self._advance()
            else:
                break
        value = self.source[start_pos : self.position]
        token_type = KEYWORDS.get(value, TokenType.IDENTIFIER)
        return Token(token_type, value, self.line, start_column)
