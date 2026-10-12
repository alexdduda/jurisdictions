"""scopelang: a toy language whose variable scoping follows federal politics."""

from .interpreter import Interpreter, Result, run
from .lexer import LexError
from .parser import MODES, ParseError, parse

__all__ = ["Interpreter", "LexError", "MODES", "ParseError", "Result", "parse", "run"]
