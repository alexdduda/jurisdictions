"""Tokenizer for scopelang."""

from dataclasses import dataclass

KEYWORDS = {
    "scope", "in", "law", "shared", "show", "explain", "defer", "to",
    "if", "else", "true", "false", "and", "or", "not",
}

# Longest operators first so "+=" wins over "+".
OPERATORS = [
    "+=", "-=", "==", "!=", "<=", ">=",
    "{", "}", "(", ")", ",", ":", "=", "+", "-", "*", "/", "<", ">",
]


class LexError(Exception):
    pass


@dataclass(frozen=True)
class Token:
    kind: str  # NUMBER, STRING, IDENT, KEYWORD, OP, EOF
    value: object
    line: int
    col: int


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i, line, col = 0, 1, 1
    n = len(source)

    while i < n:
        c = source[i]

        if c == "\n":
            i, line, col = i + 1, line + 1, 1
            continue
        if c in " \t\r;":
            i, col = i + 1, col + 1
            continue
        if c == "#" or source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue

        start = col
        if c.isdigit() or (c == "." and i + 1 < n and source[i + 1].isdigit()):
            j = i
            while j < n and (source[j].isdigit() or source[j] in "._"):
                j += 1
            text = source[i:j].replace("_", "")
            try:
                value = float(text) if "." in text else int(text)
            except ValueError:
                raise LexError(f"line {line}: bad number {source[i:j]!r}") from None
            tokens.append(Token("NUMBER", value, line, start))
            i, col = j, col + (j - i)
            continue

        if c.isalpha() or c == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            kind = "KEYWORD" if word in KEYWORDS else "IDENT"
            tokens.append(Token(kind, word, line, start))
            i, col = j, col + (j - i)
            continue

        if c == '"':
            j = i + 1
            while j < n and source[j] != '"':
                if source[j] == "\n":
                    break
                j += 1
            if j >= n or source[j] != '"':
                raise LexError(f"line {line}: unterminated string")
            tokens.append(Token("STRING", source[i + 1:j], line, start))
            i, col = j + 1, col + (j + 1 - i)
            continue

        for op in OPERATORS:
            if source.startswith(op, i):
                tokens.append(Token("OP", op, line, start))
                i, col = i + len(op), col + len(op)
                break
        else:
            raise LexError(f"line {line}, col {col}: unexpected character {c!r}")

    tokens.append(Token("EOF", None, line, col))
    return tokens
