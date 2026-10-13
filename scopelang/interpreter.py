"""Evaluator for scopelang: variables live in nested jurisdictions.

Ordinary programming languages resolve names with one fixed rule: the
innermost scope wins (shadowing). Real federations argue about precedence,
so scopelang lets a scope declare a *law* that picks the rule for one name:

    shadow   each level may set its own value; the nearest one wins
    preempt  only the declaring scope may set it; lower writes are struck down
    floor    lower levels may raise it, never go below what they inherit
    ceiling  lower levels may lower it, never go above what they inherit
    matched  lower levels choose freely; the declaring scope pays a share of
             the cost (the law's value is that match rate, not a level)
    equalized lower levels choose freely; the declaring scope tops up poorer
             ones' ability to pay (the value is the share of the gap closed)
    devolved the level two below decides (say, cities), skipping the one in
             between (provinces), whose writes are struck down; the value is
             the share of cost the declaring scope pays

Illegal writes are "struck down": reported and not applied, and the program
keeps running, the way a court voids one statute without stopping the state.
At the end, every surviving value is re-checked, because a higher level may
have tightened a rule after a lower level acted.

`shared` variables are a commons: any scope inside the declaring one can
change them, and the run ends with a report of who changed them and who else
lives with the result (externalities).
"""

from dataclasses import dataclass, field

from .parser import (
    Assign, Binary, Call, Defer, Explain, If, LawDecl, Literal, Name,
    Program, ScopeDecl, SharedDecl, Show, Unary, parse, unparse,
)

ROOT = "root"

MODE_MEANING = {
    "shadow": "each level may set its own value; the nearest one wins",
    "preempt": "only {owner} may set it; lower levels are struck down",
    "floor": "lower levels may raise it but never go below what they inherit",
    "ceiling": "lower levels may lower it but never go above what they inherit",
    "matched": "lower levels choose freely; {owner} pays {rate} of the cost",
    "equalized": "lower levels choose freely; {owner} closes {rate} of poorer ones' gap in ability to pay",
    "devolved": "the level below the next decides; the level in between may not; {owner} pays {rate} of the cost",
}


class ScopeError(Exception):
    def __init__(self, line: int, message: str, kind: str = "error"):
        super().__init__(message)
        self.line = line
        self.message = message
        self.kind = kind


@dataclass
class Binding:
    value: object
    line: int


@dataclass
class Law:
    name: str
    mode: str
    owner: "Scope"
    line: int
    rate: float | None = None  # only for `matched` and `equalized`


@dataclass
class SharedWrite:
    scope: str
    line: int
    before: object
    after: object


@dataclass
class Shared:
    name: str
    value: object
    owner: "Scope"
    line: int
    writes: list[SharedWrite] = field(default_factory=list)
    readers: set[str] = field(default_factory=set)


@dataclass
class Diagnostic:
    kind: str  # struck_down, now_invalid, dispute, error
    line: int
    scope: str
    message: str

    LABELS = {
        "struck_down": "STRUCK DOWN",
        "now_invalid": "NOW INVALID",
        "dispute": "DISPUTE",
        "error": "ERROR",
    }

    def __str__(self) -> str:
        return f"  ✗ line {self.line} {self.LABELS[self.kind]}: {self.message}"


class Scope:
    def __init__(self, name: str, parents: list["Scope"], line: int):
        self.name = name
        self.parents = parents
        self.children: list[Scope] = []
        self.line = line
        self.vars: dict[str, Binding] = {}
        self.laws: dict[str, Law] = {}
        self.shared: dict[str, Shared] = {}
        self.defers: dict[str, Scope] = {}

    def __repr__(self) -> str:
        return f"Scope({self.name})"


def fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:.6g}"
    return str(value)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


BUILTINS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": lambda x, digits=0: round(x, int(digits)),
}


class Interpreter:
    def __init__(self):
        self.root = Scope(ROOT, [], 0)
        self.scopes: dict[str, Scope] = {ROOT: self.root}
        self.order: list[Scope] = []  # creation order, root excluded
        self.log: list[str] = []
        self.diagnostics: list[Diagnostic] = []

    # --- running ----------------------------------------------------------

    def run(self, program: Program) -> "Result":
        self.exec_block(program.body, self.root)
        self.validate()
        return Result(self)

    def exec_block(self, body: list, scope: Scope) -> None:
        for stmt in body:
            try:
                self.exec(stmt, scope)
            except ScopeError as err:
                self.report(err.kind, err.line or stmt.line, scope, err.message)

    def report(self, kind: str, line: int, scope: Scope, message: str) -> None:
        diag = Diagnostic(kind, line, scope.name, message)
        self.diagnostics.append(diag)
        self.log.append(str(diag))

    def exec(self, stmt, scope: Scope) -> None:
        match stmt:
            case ScopeDecl():
                self.exec_scope(stmt, scope)
            case LawDecl():
                self.exec_law(stmt, scope)
            case SharedDecl():
                self.exec_shared(stmt, scope)
            case Assign():
                self.exec_assign(stmt, scope)
            case Show():
                self.exec_show(stmt, scope)
            case Explain():
                self.log.extend(self.explain(scope, stmt.name))
            case Defer():
                self.exec_defer(stmt, scope)
            case If():
                branch = stmt.then if self.truthy(self.eval(stmt.cond, scope)) else stmt.otherwise
                self.exec_block(branch, scope)
            case _:
                raise ScopeError(0, f"unknown statement {stmt!r}")

    def exec_scope(self, stmt: ScopeDecl, current: Scope) -> None:
        if stmt.name == ROOT:
            raise ScopeError(stmt.line, f"'{ROOT}' is reserved for the outermost scope")
        if stmt.parents is None:
            parents = [current]
        else:
            parents = []
            for pname in stmt.parents:
                if pname not in self.scopes:
                    raise ScopeError(stmt.line, f"scope {stmt.name} names unknown parent {pname}")
                parents.append(self.scopes[pname])

        existing = self.scopes.get(stmt.name)
        if existing is not None:
            reopening = (
                current in existing.parents if stmt.parents is None
                else {p.name for p in parents} == {p.name for p in existing.parents}
            )
            if not reopening:
                where = ", ".join(p.name for p in existing.parents)
                raise ScopeError(stmt.line, f"scope {stmt.name} already exists under {where}")
            target = existing
        else:
            target = Scope(stmt.name, parents, stmt.line)
            for parent in parents:
                parent.children.append(target)
            self.scopes[stmt.name] = target
            self.order.append(target)

        self.exec_block(stmt.body, target)

    def exec_law(self, stmt: LawDecl, scope: Scope) -> None:
        if self.find_shared(scope, stmt.name):
            raise ScopeError(stmt.line, f"{stmt.name} is a shared commons and cannot also be a law")
        for law in self.ancestor_laws(scope, stmt.name):
            if law.mode != "shadow":
                raise ScopeError(
                    stmt.line,
                    f"{scope.name} cannot redeclare {stmt.name}: it is already a "
                    f"{law.mode} law of {law.owner.name} (line {law.line})",
                    "struck_down",
                )

        law = Law(stmt.name, stmt.mode, scope, stmt.line)
        if stmt.value is not None:
            value = self.eval(stmt.value, scope)
            if stmt.mode in ("matched", "equalized", "devolved"):
                if not _is_number(value) or not 0 <= value <= 1:
                    raise ScopeError(stmt.line, f"a {stmt.mode} law's value is a rate between 0 and 1, got {fmt(value)}")
                law.rate = float(value)
            else:
                scope.vars[stmt.name] = Binding(value, stmt.line)
        scope.laws[stmt.name] = law

    def exec_shared(self, stmt: SharedDecl, scope: Scope) -> None:
        if stmt.name in scope.vars or stmt.name in scope.laws:
            raise ScopeError(stmt.line, f"{stmt.name} is already an ordinary variable in {scope.name}")
        scope.shared[stmt.name] = Shared(stmt.name, self.eval(stmt.value, scope), scope, stmt.line)

    def exec_assign(self, stmt: Assign, scope: Scope) -> None:
        commons = self.find_shared(scope, stmt.name)
        if commons is not None:
            before = commons.value
            after = self.combine(stmt.op, before, self.eval(stmt.value, scope), stmt.line)
            commons.value = after
            commons.writes.append(SharedWrite(scope.name, stmt.line, before, after))
            return

        if stmt.op == "=":
            value = self.eval(stmt.value, scope)
        else:
            current, _, _ = self.resolve(scope, stmt.name, stmt.line)
            value = self.combine(stmt.op, current, self.eval(stmt.value, scope), stmt.line)

        problem = self.violation(scope, stmt.name, value)
        if problem:
            raise ScopeError(
                stmt.line, f"{scope.name} cannot set {stmt.name} = {fmt(value)}: {problem}", "struck_down"
            )
        scope.vars[stmt.name] = Binding(value, stmt.line)

    def exec_show(self, stmt: Show, scope: Scope) -> None:
        if isinstance(stmt.expr, Name):
            value, source, kind = self.resolve(scope, stmt.expr.name, stmt.line)
            if kind == "shared":
                where = f"shared commons of {source.name}"
            elif source is scope:
                where = f"set here, line {scope.vars[stmt.expr.name].line}"
            else:
                where = f"inherited from {source.name}"
            self.log.append(f"[{scope.name}] {stmt.expr.name} = {fmt(value)}  ({where})")
        elif isinstance(stmt.expr, Literal) and isinstance(stmt.expr.value, str):
            self.log.append(f"[{scope.name}] {stmt.expr.value}")
        else:
            value = self.eval(stmt.expr, scope)
            self.log.append(f"[{scope.name}] {unparse(stmt.expr)} = {fmt(value)}")

    def exec_defer(self, stmt: Defer, scope: Scope) -> None:
        for parent in scope.parents:
            if parent.name == stmt.parent:
                scope.defers[stmt.name] = parent
                return
        raise ScopeError(
            stmt.line,
            f"{scope.name} can only defer to a direct parent "
            f"({', '.join(p.name for p in scope.parents)}), not {stmt.parent}",
        )

    # --- name resolution ----------------------------------------------------

    def candidates(self, scope: Scope, name: str, use_defer: bool = True) -> list[tuple]:
        """Every (value, source scope, kind) visible for `name`, one per source."""
        if name in scope.vars:
            return [(scope.vars[name].value, scope, "var")]
        if name in scope.shared:
            return [(scope.shared[name].value, scope, "shared")]
        parents = scope.parents
        if use_defer and name in scope.defers:
            parents = [scope.defers[name]]
        found, seen = [], set()
        for parent in parents:
            for cand in self.candidates(parent, name, use_defer):
                if cand[1].name not in seen:
                    seen.add(cand[1].name)
                    found.append(cand)
        return found

    def resolve(self, scope: Scope, name: str, line: int, track: bool = True) -> tuple:
        found = self.candidates(scope, name)
        if not found:
            raise ScopeError(line, f"{name} is not defined in {scope.name}")
        if len({repr(value) for value, _, _ in found}) > 1:
            claims = ", ".join(f"{src.name} says {fmt(v)}" for v, src, _ in found)
            raise ScopeError(
                line,
                f"{scope.name} inherits conflicting values of {name} ({claims}); "
                f"settle it with `defer {name} to <parent>`",
                "dispute",
            )
        value, source, kind = found[0]
        if kind == "shared" and track:
            source.shared[name].readers.add(scope.name)
        return value, source, kind

    def find_shared(self, scope: Scope, name: str) -> Shared | None:
        for cand_value, source, kind in self.candidates(scope, name, use_defer=False):
            if kind == "shared":
                return source.shared[name]
        return None

    def ancestors(self, scope: Scope) -> list[Scope]:
        seen, out, stack = set(), [], list(scope.parents)
        while stack:
            s = stack.pop(0)
            if s.name in seen:
                continue
            seen.add(s.name)
            out.append(s)
            stack.extend(s.parents)
        return out

    def ancestor_laws(self, scope: Scope, name: str) -> list[Law]:
        return [a.laws[name] for a in self.ancestors(scope) if name in a.laws]

    def violation(self, scope: Scope, name: str, value) -> str | None:
        """Why `scope` may not hold `value` for `name` (a short reason), or None."""
        for law in self.ancestor_laws(scope, name):
            if law.mode == "preempt":
                return f"preempted by {law.owner.name} (law at line {law.line})"
            if law.mode == "devolved" and law.owner in scope.parents:
                return f"devolved by {law.owner.name} past {scope.name} to the level below (law at line {law.line})"
            if law.mode not in ("floor", "ceiling"):
                continue
            inherited = [
                (v, src) for v, src, _ in self.candidates_from_parents(scope, name)
                if _is_number(v)
            ]
            if not inherited:
                continue
            if not _is_number(value):
                return f"{name} is a {law.mode} law, so it must be a number"
            pick = max if law.mode == "floor" else min
            bound, source = pick(inherited, key=lambda item: item[0])
            if law.mode == "floor" and value < bound:
                return (
                    f"below the floor of {fmt(bound)} from {source.name} "
                    f"(floor law of {law.owner.name}, line {law.line})"
                )
            if law.mode == "ceiling" and value > bound:
                return (
                    f"above the ceiling of {fmt(bound)} from {source.name} "
                    f"(ceiling law of {law.owner.name}, line {law.line})"
                )
        return None

    def candidates_from_parents(self, scope: Scope, name: str) -> list[tuple]:
        """What `scope` would inherit if it set nothing itself.

        Constraints ignore `defer`: deferring settles which value you read,
        not which governments' rules you are bound by.
        """
        found, seen = [], set()
        for parent in scope.parents:
            for cand in self.candidates(parent, name, use_defer=False):
                if cand[1].name not in seen:
                    seen.add(cand[1].name)
                    found.append(cand)
        return found

    # --- end-of-run checks and reports --------------------------------------

    def validate(self) -> None:
        for scope in self.order:
            for name, binding in scope.vars.items():
                problem = self.violation(scope, name, binding.value)
                if problem:
                    self.report(
                        "now_invalid", binding.line, scope,
                        f"{scope.name}.{name} = {fmt(binding.value)} is now {problem}",
                    )

    def subtree(self, scope: Scope) -> list[Scope]:
        seen, out, stack = set(), [], [scope]
        while stack:
            s = stack.pop(0)
            if s.name in seen:
                continue
            seen.add(s.name)
            out.append(s)
            stack.extend(s.children)
        return out

    def externalities(self) -> list[str]:
        lines = []
        for scope in [self.root, *self.order]:
            for commons in scope.shared.values():
                if not commons.writes:
                    continue
                lines.append(f"{commons.name} (commons of {scope.name}) is now {fmt(commons.value)}")
                for w in commons.writes:
                    change = (
                        f"{'+' if w.after - w.before >= 0 else ''}{fmt(w.after - w.before)}"
                        if _is_number(w.before) and _is_number(w.after)
                        else f"{fmt(w.before)} -> {fmt(w.after)}"
                    )
                    lines.append(f"  changed by {w.scope} ({change}, line {w.line})")
                writers = {w.scope for w in commons.writes}
                others = [s.name for s in self.subtree(scope) if s.name not in writers and s is not self.root]
                if others:
                    lines.append(f"  also lived with by: {', '.join(others)}")
                readers = sorted(commons.readers - writers)
                if readers:
                    lines.append(f"  read (and so affected) by: {', '.join(readers)}")
        return lines

    def explain(self, scope: Scope, name: str) -> list[str]:
        out = [f"explain {name} in {scope.name}:"]
        try:
            value, source, kind = self.resolve(scope, name, 0, track=False)
            origin = "set here" if source is scope else f"from {source.name}"
            out.append(f"  value: {fmt(value)} ({origin})")
        except ScopeError as err:
            out.append(f"  value: none ({err.message})")

        laws = list(self.ancestor_laws(scope, name))
        if name in scope.laws:
            laws.insert(0, scope.laws[name])
        if not laws:
            out.append("  no law governs it: ordinary shadowing, the nearest value wins")
        for law in laws:
            meaning = MODE_MEANING[law.mode].format(
                owner=law.owner.name,
                rate=f"{law.rate:.0%}" if law.rate is not None else "a share",
            )
            out.append(f"  law: {law.mode}, declared by {law.owner.name} (line {law.line}): {meaning}")

        for path in self.paths_to_root(scope)[:6]:
            steps = []
            for s in path:
                if name in s.vars:
                    steps.append(f"{s.name} = {fmt(s.vars[name].value)}")
                elif name in s.shared:
                    steps.append(f"{s.name} = {fmt(s.shared[name].value)} (shared)")
                elif s is not self.root:
                    steps.append(f"{s.name} (unset)")
            out.append("  chain: " + " -> ".join(steps))
        return out

    def paths_to_root(self, scope: Scope) -> list[list[Scope]]:
        if not scope.parents:
            return [[scope]]
        return [[scope, *rest] for parent in scope.parents for rest in self.paths_to_root(parent)]

    def tree(self) -> list[str]:
        lines = [ROOT + self._annotations(self.root)]

        def walk(scope: Scope, prefix: str) -> None:
            for i, child in enumerate(scope.children):
                last = i == len(scope.children) - 1
                branch = "└── " if last else "├── "
                if child.parents[0] is scope:
                    others = [p.name for p in child.parents[1:]]
                    also = f"  (also under {', '.join(others)})" if others else ""
                    lines.append(prefix + branch + child.name + also + self._annotations(child))
                    walk(child, prefix + ("    " if last else "│   "))
                else:
                    lines.append(prefix + branch + f"{child.name}  (shown under {child.parents[0].name})")

        walk(self.root, "")
        return lines

    def _annotations(self, scope: Scope) -> str:
        parts = []
        for name, law in scope.laws.items():
            if law.mode in ("matched", "equalized", "devolved"):
                parts.append(f"law {name}: {law.mode} {fmt(law.rate) if law.rate is not None else ''}".rstrip())
            elif name in scope.vars:
                parts.append(f"law {name}: {law.mode} = {fmt(scope.vars[name].value)}")
            else:
                parts.append(f"law {name}: {law.mode}")
        for name, binding in scope.vars.items():
            if name not in scope.laws:
                parts.append(f"{name} = {fmt(binding.value)}")
        for name, commons in scope.shared.items():
            parts.append(f"shared {name} = {fmt(commons.value)}")
        return ("    " + "; ".join(parts)) if parts else ""

    # --- expressions ---------------------------------------------------------

    def eval(self, node, scope: Scope):
        match node:
            case Literal(value=v):
                return v
            case Name(name=n, line=line):
                return self.resolve(scope, n, line)[0]
            case Unary(op="not", operand=o):
                return not self.truthy(self.eval(o, scope))
            case Unary(op="-", operand=o):
                value = self.eval(o, scope)
                if not _is_number(value):
                    raise ScopeError(0, f"cannot negate {fmt(value)}")
                return -value
            case Binary(op="and", left=l, right=r):
                return self.truthy(self.eval(l, scope)) and self.truthy(self.eval(r, scope))
            case Binary(op="or", left=l, right=r):
                return self.truthy(self.eval(l, scope)) or self.truthy(self.eval(r, scope))
            case Binary(op=op, left=l, right=r):
                return self.binary(op, self.eval(l, scope), self.eval(r, scope))
            case Call(func=f, args=args, line=line):
                if f not in BUILTINS:
                    raise ScopeError(line, f"unknown function {f}; available: {', '.join(BUILTINS)}")
                values = [self.eval(a, scope) for a in args]
                try:
                    return BUILTINS[f](*values)
                except TypeError as err:
                    raise ScopeError(line, f"bad call to {f}: {err}") from None
        raise ScopeError(0, f"cannot evaluate {node!r}")

    def combine(self, op: str, current, delta, line: int):
        try:
            return self.binary("+" if op == "+=" else "-", current, delta) if op != "=" else delta
        except ScopeError as err:
            raise ScopeError(line, err.message) from None

    def binary(self, op: str, a, b):
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == "+" and isinstance(a, str) and isinstance(b, str):
            return a + b
        if not (_is_number(a) and _is_number(b)):
            raise ScopeError(0, f"cannot apply {op} to {fmt(a)} and {fmt(b)}")
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise ScopeError(0, "division by zero")
            return a / b
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]

    @staticmethod
    def truthy(value) -> bool:
        return bool(value)


class Result:
    def __init__(self, interp: Interpreter):
        self.interp = interp
        self.log = interp.log
        self.diagnostics = interp.diagnostics

    def text(self, tree: bool = False) -> str:
        sections = [*self.log]
        ext = self.interp.externalities()
        if ext:
            sections += ["", "externalities:", *("  " + line for line in ext)]
        if tree:
            sections += ["", *self.interp.tree()]
        struck = sum(d.kind == "struck_down" for d in self.diagnostics)
        other = len(self.diagnostics) - struck
        sections += ["", f"{struck} struck down, {other} other problem(s)"]
        return "\n".join(sections)

    def value(self, scope: str, name: str):
        return self.interp.resolve(self.interp.scopes[scope], name, 0, track=False)[0]

    def laws(self, scope: str) -> dict[str, tuple[str, object]]:
        """{name: (mode, value)} for the laws a scope declares.

        For a `matched` law the value is the match rate; otherwise it is the
        level the scope set (or None if it set none).
        """
        s = self.interp.scopes[scope]
        out = {}
        for name, law in s.laws.items():
            if law.mode in ("matched", "equalized", "devolved"):
                out[name] = (law.mode, law.rate)
            else:
                out[name] = (law.mode, s.vars[name].value if name in s.vars else None)
        return out


def run(source: str) -> Result:
    return Interpreter().run(parse(source))
