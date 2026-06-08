from __future__ import annotations

from typing import NoReturn

from lab4.ast import (
    Assign,
    BinOp,
    Block,
    Call,
    Expression,
    ExprStmt,
    Function,
    Identifier,
    If,
    NumLiteral,
    Param,
    Program,
    Return,
    Statement,
    StrLiteral,
    UnaryOp,
    VarDecl,
    While,
)
from lab4.lexer import Lexer, Token, TokenType


class Parser:
    """Синтаксический анализатор (парсер рекурсивного спуска) для языка alg."""

    def __init__(self, lexer: Lexer) -> None:
        self.lexer = lexer
        self.tokens: list[Token] = []
        self.current = 0

        # Считываем все токены до конца файла (EOF)
        token = self.lexer.next_token()
        while token.type != TokenType.EOF:
            self.tokens.append(token)
            token = self.lexer.next_token()
        self.tokens.append(token)  # Добавляем EOF токен

    def parse(self) -> Program:
        """Парсинг всей программы (списка функций)."""
        funcs: list[Function] = []
        while not self._is_at_end():
            funcs.append(self._function_decl())
        return Program(funcs)

    # Вспомогательные методы

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _peek_next(self) -> Token:
        if self._is_at_end():
            return self.tokens[-1]
        return self.tokens[self.current + 1]

    def _is_at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _check(self, token_type: TokenType) -> bool:
        if self._is_at_end():
            return False
        return self._peek().type == token_type

    def _match(self, *types: TokenType) -> bool:
        for t in types:
            if self._check(t):
                self._advance()
                return True
        return False

    def _advance(self) -> Token:
        if not self._is_at_end():
            self.current += 1
        return self.tokens[self.current - 1]

    def _consume(self, token_type: TokenType, error_message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        self._error(error_message)

    def _error(self, message: str) -> NoReturn:
        token = self._peek()
        msg = f"""Parser error at line {token.line}, column {token.column}
        near '{token.value}': {message}"""

        raise ValueError(msg)

    # Правила грамматики (Grammar Rules)

    def _function_decl(self) -> Function:
        """fn (void | int | string) IDENTIFIER '(' params? ')' block"""
        self._consume(TokenType.FN, "Expected 'fn'")

        # Возвращаемый тип
        ret_token = self._advance()
        if ret_token.type not in (TokenType.VOID, TokenType.INT, TokenType.STRING_KEYWORD):
            self._error("Expected return type ('void', 'int' or 'string')")
        return_type = ret_token.value

        name = self._consume(TokenType.IDENTIFIER, "Expected function name").value

        self._consume(TokenType.LPAREN, "Expected '('")
        params: list[Param] = []
        if not self._check(TokenType.RPAREN):
            params = self._parameters()
        self._consume(TokenType.RPAREN, "Expected ')'")

        body = self._block()
        return Function(return_type, name, params, body)

    def _parameters(self) -> list[Param]:
        """parameter (',' parameter)*"""
        params: list[Param] = [self._parameter()]
        while self._match(TokenType.COMMA):
            params.append(self._parameter())
        return params

    def _parameter(self) -> Param:
        """(int | string) IDENTIFIER"""
        type_token = self._advance()
        if type_token.type not in (TokenType.INT, TokenType.STRING_KEYWORD):
            self._error("Expected parameter type ('int' or 'string')")
        name = self._consume(TokenType.IDENTIFIER, "Expected parameter name").value
        return Param(type_token.value, name)

    def _block(self) -> Block:
        """'{' statement* '}'"""
        self._consume(TokenType.LBRACE, "Expected '{'")
        statements: list[Statement] = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            statements.append(self._statement())
        self._consume(TokenType.RBRACE, "Expected '}'")
        return Block(statements)

    def _statement(self) -> Statement:
        """Определение типа инструкции."""
        if self._match(TokenType.INT, TokenType.STRING_KEYWORD):
            # Откатываем назад на один токен, чтобы вызвать VarDecl парсинг
            self.current -= 1
            return self._var_decl()
        if self._match(TokenType.IF):
            return self._if_stmt()
        if self._match(TokenType.WHILE):
            return self._while_stmt()
        if self._match(TokenType.RETURN):
            return self._return_stmt()
        if self._match(TokenType.LBRACE):
            self.current -= 1
            return self._block()

        return self._assign_or_expr_stmt()

    def _var_decl(self) -> VarDecl:
        """(int | string) IDENTIFIER ('=' expression)? ';'"""
        type_token = self._advance()
        name = self._consume(TokenType.IDENTIFIER, "Expected variable name").value
        init: Expression | None = None

        if self._match(TokenType.ASSIGN):
            init = self._expression()

        self._consume(TokenType.SEMICOLON, "Expected ';'")
        return VarDecl(type_token.value, name, init)

    def _if_stmt(self) -> If:
        """if '(' expression ')' block (else block)?"""
        self._consume(TokenType.LPAREN, "Expected '('")
        cond = self._expression()
        self._consume(TokenType.RPAREN, "Expected ')'")

        then_branch = self._block()
        else_branch: Block | None = None

        if self._match(TokenType.ELSE):
            else_branch = self._block()

        return If(cond, then_branch, else_branch)

    def _while_stmt(self) -> While:
        """while '(' expression ')' block"""
        self._consume(TokenType.LPAREN, "Expected '('")
        cond = self._expression()
        self._consume(TokenType.RPAREN, "Expected ')'")

        body = self._block()
        return While(cond, body)

    def _return_stmt(self) -> Return:
        """return expression? ';'"""
        value: Expression | None = None
        if not self._check(TokenType.SEMICOLON):
            value = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';'")
        return Return(value)

    def _assign_or_expr_stmt(self) -> Statement:
        """Идентификация присваивания или вызова функции/выражения."""
        # Заглядываем вперед: если первый токен IDENTIFIER, а второй '=', то это присваивание
        if self._peek().type == TokenType.IDENTIFIER and self._peek_next().type == TokenType.ASSIGN:
            name = self._consume(TokenType.IDENTIFIER, "Expected identifier").value
            self._consume(TokenType.ASSIGN, "Expected '='")
            expr = self._expression()
            self._consume(TokenType.SEMICOLON, "Expected ';'")
            return Assign(name, expr)

        expr = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';'")
        return ExprStmt(expr)

    # Синтаксический анализ выражений (Expression Parsing with Precedence)

    def _expression(self) -> Expression:
        return self._equality()

    def _equality(self) -> Expression:
        """equality -> comparison (('==' | '!=') comparison)*"""
        expr = self._comparison()
        while self._match(TokenType.EQ, TokenType.NE):
            op = self.tokens[self.current - 1].value
            right = self._comparison()
            expr = BinOp(op, expr, right)
        return expr

    def _comparison(self) -> Expression:
        """comparison -> term (('<' | '<=' | '>' | '>=') term)*"""
        expr = self._term()
        while self._match(TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE):
            op = self.tokens[self.current - 1].value
            right = self._term()
            expr = BinOp(op, expr, right)
        return expr

    def _term(self) -> Expression:
        """term -> factor (('+' | '-') factor)*"""
        expr = self._factor()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            op = self.tokens[self.current - 1].value
            right = self._factor()
            expr = BinOp(op, expr, right)
        return expr

    def _factor(self) -> Expression:
        """factor -> unary (('*' | '/' | '%') unary)*"""
        expr = self._unary()
        while self._match(TokenType.MUL, TokenType.DIV, TokenType.MOD):
            op = self.tokens[self.current - 1].value
            right = self._unary()
            expr = BinOp(op, expr, right)
        return expr

    def _unary(self) -> Expression:
        """unary -> ('-')? primary"""
        if self._match(TokenType.MINUS):
            op = self.tokens[self.current - 1].value
            expr = self._unary()
            return UnaryOp(op, expr)
        return self._primary()

    def _primary(self) -> Expression:
        """Категория атомарных сущностей: скобки, константы, переменные и вызовы."""
        if self._match(TokenType.NUMBER):
            return NumLiteral(int(self.tokens[self.current - 1].value))

        if self._match(TokenType.STRING_LITERAL):
            return StrLiteral(self.tokens[self.current - 1].value)

        if self._match(TokenType.IDENTIFIER):
            name = self.tokens[self.current - 1].value

            # Если дальше идет скобка '(', то это вызов функции: id '(' args? ')'
            if self._match(TokenType.LPAREN):
                args: list[Expression] = []
                if not self._check(TokenType.RPAREN):
                    args.append(self._expression())
                    while self._match(TokenType.COMMA):
                        args.append(self._expression())
                self._consume(TokenType.RPAREN, "Expected ')' after arguments")
                return Call(name, args)

            return Identifier(name)

        if self._match(TokenType.LPAREN):
            expr = self._expression()
            self._consume(TokenType.RPAREN, "Expected ')' after group expression")
            return expr

        self._error("Expected expression")
