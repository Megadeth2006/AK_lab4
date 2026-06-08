from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ASTNode:
    """Базовый класс для всех узлов абстрактного синтаксического дерева (AST)."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


#  Выражения


@dataclass
class Expression(ASTNode):
    pass


@dataclass
class NumLiteral(Expression):
    value: int

    def to_dict(self) -> dict[str, Any]:
        return {"type": "NumLiteral", "value": self.value}


@dataclass
class StrLiteral(Expression):
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "StrLiteral", "value": self.value}


@dataclass
class Identifier(Expression):
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Identifier", "name": self.name}


@dataclass
class BinOp(Expression):
    op: str
    left: Expression
    right: Expression

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "BinOp",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass
class UnaryOp(Expression):
    op: str
    expr: Expression

    def to_dict(self) -> dict[str, Any]:
        return {"type": "UnaryOp", "op": self.op, "expr": self.expr.to_dict()}


@dataclass
class Call(Expression):
    name: str
    args: list[Expression]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Call",
            "name": self.name,
            "args": [arg.to_dict() for arg in self.args],
        }


# Инструкции


@dataclass
class Statement(ASTNode):
    pass


@dataclass
class Block(Statement):
    statements: list[Statement]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Block",
            "statements": [stmt.to_dict() for stmt in self.statements],
        }


@dataclass
class VarDecl(Statement):
    type_name: str
    name: str
    init: Expression | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "VarDecl",
            "type_name": self.type_name,
            "name": self.name,
            "init": self.init.to_dict() if self.init else None,
        }


@dataclass
class Assign(Statement):
    name: str
    value: Expression

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Assign", "name": self.name, "value": self.value.to_dict()}


@dataclass
class If(Statement):
    cond: Expression
    then_branch: Block
    else_branch: Block | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "If",
            "cond": self.cond.to_dict(),
            "then_branch": self.then_branch.to_dict(),
            "else_branch": self.else_branch.to_dict() if self.else_branch else None,
        }


@dataclass
class While(Statement):
    cond: Expression
    body: Block

    def to_dict(self) -> dict[str, Any]:
        return {"type": "While", "cond": self.cond.to_dict(), "body": self.body.to_dict()}


@dataclass
class Return(Statement):
    value: Expression | None

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Return", "value": self.value.to_dict() if self.value else None}


@dataclass
class ExprStmt(Statement):
    expr: Expression

    def to_dict(self) -> dict[str, Any]:
        return {"type": "ExprStmt", "expr": self.expr.to_dict()}


# Объявления верхнего уровня


@dataclass
class Param(ASTNode):
    type_name: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Param", "type_name": self.type_name, "name": self.name}


@dataclass
class Function(ASTNode):
    return_type: str
    name: str
    params: list[Param]
    body: Block

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Function",
            "return_type": self.return_type,
            "name": self.name,
            "params": [p.to_dict() for p in self.params],
            "body": self.body.to_dict(),
        }


@dataclass
class Program(ASTNode):
    funcs: list[Function]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Program", "funcs": [f.to_dict() for f in self.funcs]}
