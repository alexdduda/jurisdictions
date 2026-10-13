"""Recursive-descent parser for scopelang.

Grammar (statements need no separators; newlines and `;` are whitespace):

    program    := stmt*
    stmt       := scope | law | shared | assign | show | explain | defer | if
    scope      := "scope" NAME ("in" NAME ("," NAME)*)? "{" stmt* "}"
    law        := "law" NAME ":" MODE ("=" expr)?
    shared     := "shared" NAME "=" expr
    assign     := NAME ("=" | "+=" | "-=") expr
    show       := "show" expr
    explain    := "explain" NAME
    defer      := "defer" NAME "to" NAME
    if         := "if" expr "{" stmt* "}" ("else" "{" stmt* "}")?

    expr       := or
    or         := and ("or" and)*
    and        := not ("and" not)*
    not        := "not" not | compare
    compare    := sum (("==" | "!=" | "<" | "<=" | ">" | ">=") sum)?
    sum        := product (("+" | "-") product)*
    product    := unary (("*" | "/") unary)*
    unary      := "-" unary | primary
    primary    := NUMBER | STRING | "true" | "false" | NAME | NAME "(" args ")" | "(" expr ")"
"""

from dataclasses import dataclass, field

from .lexer import Token, tokenize

MODES = ("shadow", "preempt", "floor", "ceiling", "matched", "equalized")


class ParseError(Exception):
    pass


# --- expressions ---------------------------------------------------------

@dataclass
class Literal:
    value: object


@dataclass
class Name:
    name: str
    line: int


@dataclass
class Unary:
    op: str
    operand: object


@dataclass
class Binary:
    op: str
    left: object
    right: object


@dataclass
class Call:
    func: str
    args: list
    line: int


# --- statements ----------------------------------------------------------

@dataclass
class ScopeDecl:
    name: str
    parents: list[str] | None  # None means "the enclosing scope"
    body: list
    line: int


@dataclass
class LawDecl:
    name: str
    mode: str
    value: object | None
    line: int


@dataclass
class SharedDecl:
    name: str
    value: object
    line: int


@dataclass
class Assign:
    name: str
    op: str
    value: object
    line: int


@dataclass
class Show:
    expr: object
    line: int


@dataclass
class Explain:
    name: str
    line: int


@dataclass
class Defer:
    name: str
    parent: str
    line: int


@dataclass
class If:
    cond: object
    then: list
    otherwise: list
    line: int


@dataclass
class Program:
    body: list = field(default_factory=list)


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # --- helpers ---

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def check(self, kind: str, value=None) -> bool:
        tok = self.peek()
        return tok.kind == kind and (value is None or tok.value == value)

    def match(self, kind: str, value=None) -> Token | None:
        if self.check(kind, value):
            return self.advance()
        return None

    def expect(self, kind: str, value=None, what: str | None = None) -> Token:
        if self.check(kind, value):
            return self.advance()
        tok = self.peek()
        wanted = what or (repr(value) if value is not None else kind.lower())
        found = "end of file" if tok.kind == "EOF" else repr(tok.value)
        raise ParseError(f"line {tok.line}: expected {wanted}, found {found}")

    # --- statements ---

    def program(self) -> Program:
        body = []
        while not self.check("EOF"):
            body.append(self.statement())
        return Program(body)

    def block(self) -> list:
        self.expect("OP", "{")
        body = []
        while not self.check("OP", "}"):
            if self.check("EOF"):
                raise ParseError(f"line {self.peek().line}: unclosed '{{'")
            body.append(self.statement())
        self.expect("OP", "}")
        return body

    def statement(self):
        tok = self.peek()
        if tok.kind == "KEYWORD":
            handler = {
                "scope": self.scope_decl,
                "law": self.law_decl,
                "shared": self.shared_decl,
                "show": self.show,
                "explain": self.explain,
                "defer": self.defer,
                "if": self.if_stmt,
            }.get(tok.value)
            if handler:
                return handler()
        if tok.kind == "IDENT":
            return self.assign()
        found = "end of file" if tok.kind == "EOF" else repr(tok.value)
        raise ParseError(f"line {tok.line}: expected a statement, found {found}")

    def scope_decl(self) -> ScopeDecl:
        line = self.advance().line
        name = self.expect("IDENT", what="scope name").value
        parents = None
        if self.match("KEYWORD", "in"):
            parents = [self.expect("IDENT", what="parent scope name").value]
            while self.match("OP", ","):
                parents.append(self.expect("IDENT", what="parent scope name").value)
        return ScopeDecl(name, parents, self.block(), line)

    def law_decl(self) -> LawDecl:
        line = self.advance().line
        name = self.expect("IDENT", what="law name").value
        self.expect("OP", ":")
        mode_tok = self.expect("IDENT", what="a mode (" + ", ".join(MODES) + ")")
        if mode_tok.value not in MODES:
            raise ParseError(
                f"line {mode_tok.line}: unknown mode {mode_tok.value!r}; "
                f"expected one of {', '.join(MODES)}"
            )
        value = self.expr() if self.match("OP", "=") else None
        return LawDecl(name, mode_tok.value, value, line)

    def shared_decl(self) -> SharedDecl:
        line = self.advance().line
        name = self.expect("IDENT", what="shared variable name").value
        self.expect("OP", "=")
        return SharedDecl(name, self.expr(), line)

    def assign(self) -> Assign:
        tok = self.advance()
        op_tok = self.peek()
        if not (op_tok.kind == "OP" and op_tok.value in ("=", "+=", "-=")):
            found = "end of file" if op_tok.kind == "EOF" else repr(op_tok.value)
            raise ParseError(f"line {op_tok.line}: expected '=', '+=' or '-=' after {tok.value!r}, found {found}")
        self.advance()
        return Assign(tok.value, op_tok.value, self.expr(), tok.line)

    def show(self) -> Show:
        line = self.advance().line
        return Show(self.expr(), line)

    def explain(self) -> Explain:
        line = self.advance().line
        return Explain(self.expect("IDENT", what="variable name").value, line)

    def defer(self) -> Defer:
        line = self.advance().line
        name = self.expect("IDENT", what="variable name").value
        self.expect("KEYWORD", "to")
        parent = self.expect("IDENT", what="parent scope name").value
        return Defer(name, parent, line)

    def if_stmt(self) -> If:
        line = self.advance().line
        cond = self.expr()
        then = self.block()
        otherwise = []
        if self.match("KEYWORD", "else"):
            otherwise = [self.if_stmt()] if self.check("KEYWORD", "if") else self.block()
        return If(cond, then, otherwise, line)

    # --- expressions ---

    def expr(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.match("KEYWORD", "or"):
            left = Binary("or", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.match("KEYWORD", "and"):
            left = Binary("and", left, self.not_expr())
        return left

    def not_expr(self):
        if self.match("KEYWORD", "not"):
            return Unary("not", self.not_expr())
        return self.compare()

    def compare(self):
        left = self.sum()
        tok = self.peek()
        if tok.kind == "OP" and tok.value in ("==", "!=", "<", "<=", ">", ">="):
            self.advance()
            return Binary(tok.value, left, self.sum())
        return left

    def sum(self):
        left = self.product()
        while self.peek().kind == "OP" and self.peek().value in ("+", "-"):
            op = self.advance().value
            left = Binary(op, left, self.product())
        return left

    def product(self):
        left = self.unary()
        while self.peek().kind == "OP" and self.peek().value in ("*", "/"):
            op = self.advance().value
            left = Binary(op, left, self.unary())
        return left

    def unary(self):
        if self.match("OP", "-"):
            return Unary("-", self.unary())
        return self.primary()

    def primary(self):
        tok = self.peek()
        if tok.kind in ("NUMBER", "STRING"):
            self.advance()
            return Literal(tok.value)
        if tok.kind == "KEYWORD" and tok.value in ("true", "false"):
            self.advance()
            return Literal(tok.value == "true")
        if tok.kind == "IDENT":
            self.advance()
            if self.match("OP", "("):
                args = []
                if not self.check("OP", ")"):
                    args.append(self.expr())
                    while self.match("OP", ","):
                        args.append(self.expr())
                self.expect("OP", ")")
                return Call(tok.value, args, tok.line)
            return Name(tok.value, tok.line)
        if self.match("OP", "("):
            inner = self.expr()
            self.expect("OP", ")")
            return inner
        found = "end of file" if tok.kind == "EOF" else repr(tok.value)
        raise ParseError(f"line {tok.line}: expected an expression, found {found}")


def parse(source: str) -> Program:
    return Parser(tokenize(source)).program()


def unparse(node) -> str:
    """Render an expression back to source, for `show` output."""
    match node:
        case Literal(value=bool() as b):
            return "true" if b else "false"
        case Literal(value=str() as s):
            return f'"{s}"'
        case Literal(value=v):
            return str(v)
        case Name(name=n):
            return n
        case Unary(op="not", operand=o):
            return f"not {unparse(o)}"
        case Unary(op=op, operand=o):
            return f"{op}{unparse(o)}"
        case Binary(op=op, left=l, right=r):
            return f"{_wrap(l)} {op} {_wrap(r)}"
        case Call(func=f, args=args):
            return f"{f}({', '.join(unparse(a) for a in args)})"
    return "?"


def _wrap(node) -> str:
    text = unparse(node)
    return f"({text})" if isinstance(node, Binary) else text
