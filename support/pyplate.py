"""
PyPlate : a simple Python-based templating program

PyPlate parses a file and replaces directives (in double square brackets [[ ... ]])
by various means using a given dictionary of variables.  Arbitrary Python code
can be run inside many of the directives, making this system highly flexible.

Usage:
# Load and parse template file
template = pyplate.Template(string)
# Execute it with a dictionary of variables
template.execute_string({str: Any})
template.execute(stream, {str: Any})

PyPlate defines the following directives:
  [[...]]       evaluate the arbitrary Python expression and insert the
                result into the output

  [[# ... #]]   comment.

  [[exec ...]]  execute arbitrary Python code in the sandbox namespace

  [[if ...]]    conditional expressions with usual Python semantics
  [[elif ...]]
  [[else]]
  [[end]]

  [[for ... in ...]]  for-loop with usual Python semantics
  [[end]]
"""

#
# Copyright (C) 2002 Michael Droettboom
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#

from __future__ import annotations

import ast
import io
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TextIO, TypeAlias

try:
    import astpretty

    def astdump(info: str, aa: ast.AST) -> str:
        return f"{info}\n{astpretty.pformat(aa, show_offsets=False)}\n"

except OSError:

    def astdump(info: str, aa: ast.AST) -> str:
        return f"{info}\n{ast.dump(aa, indent=4)}\n"


stream_t: TypeAlias = TextIO
node_t: TypeAlias = "TemplateNode"
eval_data_t: TypeAlias = dict[str, Any]
tmpl_param_t: TypeAlias = list[eval_data_t]
tmpl_item_t: TypeAlias = str
tmpl_data_t: TypeAlias = list[eval_data_t]
fun_t: TypeAlias = Callable[[Any, eval_data_t], Any]
func_t: TypeAlias = Callable[[Any, eval_data_t, Any], Any]
funn_t: TypeAlias = Callable[[Any, eval_data_t], None]
expr_result_t: TypeAlias = tuple[Literal[False], None] | tuple[Literal[True], funn_t | fun_t]

re_directive = re.compile(r"\[\[(.*)\]\]")
re_for_loop = re.compile(r"for (.*) in (.*)")
re_if = re.compile(r"if (.*)")
re_elif = re.compile(r"elif (.*)")
re_def = re.compile(r"def (.*?)\((.*)\)")
re_call = re.compile(r"call (.*?)\((.*)\)")
re_exec = re.compile(r"exec (.*)")
re_comment = re.compile(r"#(.*)#")


############################################################
# Template parser
class ParseError(Exception):
    def __init__(self, file_name: str, lineno: int, s: str) -> None:
        Exception.__init__(self, f"{file_name}:{lineno:d}: {s}")


AST_CACHE: dict[str, ast.Module] = {}
AST_FUNS: dict[str, funn_t | fun_t] = {}


def _ast_parse(s: str) -> tuple[bool, ast.Module, funn_t | fun_t | None]:
    if s in AST_CACHE:
        return True, AST_CACHE[s], AST_FUNS[s]
    aa = ast.parse(s)
    AST_CACHE[s] = aa
    return False, aa, None


def _ast_set(s: str, fun: funn_t | fun_t) -> None:
    AST_FUNS[s] = fun


@dataclass
class TemplateInput:
    file_name: str
    content: str = field(init=False)

    def __post_init__(self) -> None:
        with open(self.file_name) as f:
            self.content = f.read()


class TemplateManager:
    def __init__(self) -> None:
        self.templates: dict[str, Template] = {}

    def set(self, name: str, file_name: str) -> None:
        self.templates[name] = Template(TemplateInput(file_name))

    def get(self, name: str) -> Template:
        return self.templates[name]


class Template:
    def __init__(self, template_input: TemplateInput) -> None:
        self.template_input = template_input
        self.file = io.StringIO(self.template_input.content)
        self.line = self.file.read()
        self.file.close()
        self.lineno = 0
        self.tree: TemplateNode = TopLevelTemplateNode(self)
        self.stack_variables: list[eval_data_t] = []

    def parser_get(self) -> str | None:
        if self.line == "":
            return None
        return self.line

    def parser_eat(self, chars: int) -> None:
        self.lineno += self.line[:chars].count("\n")
        self.line = self.line[chars:]

    def parser_exception(self, s: str) -> ParseError:
        return ParseError(self.template_input.file_name, self.lineno, s)

    def execute_string(self, data: eval_data_t) -> str:
        s = io.StringIO()
        self.execute(s, data)
        return s.getvalue()

    def execute(self, stream: stream_t, data: eval_data_t) -> None:
        self.stack_variables.clear()
        self.tree.execute(stream, data)

    def __repr__(self) -> str:
        return repr(self.tree)


############################################################
# NODES
class TemplateNode:
    def __init__(self, parent: Template, s: str) -> None:
        self.parent = parent
        self.s = s
        self.node_list: list[node_t] = []
        while True:
            new_node = TemplateNodeFactory(parent)
            if self.add_node(new_node):
                break

    def add_node(self, node: None | node_t) -> bool:
        if isinstance(node, EndTemplateNode):
            return True
        if node is None:
            msg = f"[[{self.s}]] does not have a matching [[end]]"
            raise self.parent.parser_exception(msg)
        self.node_list.append(node)
        return False

    def execute(self, stream: stream_t, data: eval_data_t) -> None:
        for node in self.node_list:
            node.execute(stream, data)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} {" ".join(repr(i) for i in self.node_list)}>"
        )

    @staticmethod
    def f_constant(value) -> fun_t:
        def _(_self, _data: eval_data_t) -> Any:
            return value

        return _

    @staticmethod
    def f_name_load(key: Any) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            for parent_data in reversed(self.parent.stack_variables):
                if key in parent_data:
                    return parent_data[key]
            return data[key]

        return _

    @staticmethod
    def f_add(l_fun: fun_t, r_fun: fun_t) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            return l_fun(self, data) + r_fun(self, data)

        return _

    @staticmethod
    def f_add_rc(l_fun: fun_t, value: Any) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            return l_fun(self, data) + value

        return _

    @staticmethod
    def f_subscript(v_fun: fun_t, s_fun: fun_t) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            return v_fun(self, data)[s_fun(self, data)]

        return _

    @staticmethod
    def f_subscript_c(v_fun: fun_t, value: Any) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            return v_fun(self, data)[value]

        return _

    @staticmethod
    def f_in(c_fun: fun_t) -> func_t:
        def _(self, data: eval_data_t, value: Any) -> Any:  # bool:
            return value in c_fun(self, data)

        return _

    @staticmethod
    def f_noteq(c_fun: fun_t) -> func_t:
        def _(self, data: eval_data_t, value: Any) -> Any:  # bool:
            return value != c_fun(self, data)

        return _

    @staticmethod
    def f_eq(c_fun: fun_t) -> func_t:
        def _(self, data: eval_data_t, value: Any) -> Any:  # bool:
            return value == c_fun(self, data)

        return _

    @staticmethod
    def f_in_lc(value: Any, c_fun: fun_t) -> func_t:
        def _(self, data: eval_data_t) -> Any:  # bool:
            return value in c_fun(self, data)

        return _

    @staticmethod
    def f_noteq_c(c_fun: fun_t, value: Any) -> func_t:
        def _(self, data: eval_data_t) -> Any:  # bool:
            return value != c_fun(self, data)

        return _

    @staticmethod
    def f_eq_c(c_fun: fun_t, value: Any) -> func_t:
        def _(self, data: eval_data_t) -> Any:  # bool:
            return value == c_fun(self, data)

        return _

    @staticmethod
    def f_compare(l_fun: fun_t, lst: tuple[func_t, ...]) -> fun_t:
        def _(self, data: eval_data_t) -> Any:  # bool:
            value = l_fun(self, data)
            return all(elem(self, data, value) for elem in lst)

        return _

    @staticmethod
    def f_and(lst: tuple[fun_t, ...]) -> fun_t:
        def _(self, data: eval_data_t) -> Any:  # bool:
            return all(elem(self, data) for elem in lst)

        return _

    @staticmethod
    def f_or(lst: tuple[fun_t, ...]) -> fun_t:
        def _(self, data: eval_data_t) -> Any:  # bool:
            return any(elem(self, data) for elem in lst)

        return _

    @staticmethod
    def f_not(o_fun: fun_t) -> fun_t:
        def _(self, data: eval_data_t) -> Any:  # bool:
            return not o_fun(self, data)

        return _

    @staticmethod
    def f_uadd(o_fun: fun_t) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            return +o_fun(self, data)

        return _

    @staticmethod
    def f_usub(o_fun: fun_t) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            return -o_fun(self, data)

        return _

    @staticmethod
    def f_invert(o_fun: fun_t) -> fun_t:
        def _(self, data: eval_data_t) -> Any:
            return ~o_fun(self, data)

        return _

    @staticmethod
    def f_name_store(v_fun: fun_t, name: str) -> funn_t:
        def _(self, data: eval_data_t) -> None:
            self.parent.stack_variables[-1][name] = v_fun(self, data)

        return _

    @staticmethod
    def f_stmts(lst: list[funn_t]) -> funn_t:
        def _(self, data: eval_data_t) -> None:
            for elem in lst:
                elem(self, data)

        return _

    def op_assign(self, assign: ast.Assign) -> expr_result_t:
        ok, v_fun = self.op_expr(assign.value)
        if not (ok and v_fun):
            return False, None
        lst = []
        for tgt in assign.targets:
            if not (isinstance(tgt, ast.Name) and isinstance(tgt.ctx, ast.Store)):
                return False, None
            assert v_fun is not None
            lst.append(TemplateNode.f_name_store(v_fun, tgt.id))
        fun = lst[0] if len(lst) == 1 else TemplateNode.f_stmts(lst)
        return True, fun

    def op_expr(self, expr: ast.expr) -> expr_result_t:
        if isinstance(expr, ast.Constant):  # implemented fully
            return True, TemplateNode.f_constant(expr.value)
        if isinstance(expr, ast.Name):
            name = expr.id
            if name is None:
                return False, None
            if not isinstance(expr.ctx, ast.Load):
                return False, None
            return True, TemplateNode.f_name_load(name)
        if isinstance(expr, ast.BinOp):
            l_ok, l_fun = self.op_expr(expr.left)
            if not (l_ok and l_fun):
                return False, None
            if isinstance(expr.right, ast.Constant):
                return True, TemplateNode.f_add_rc(l_fun, expr.right.value)
            r_ok, r_fun = self.op_expr(expr.right)
            if not (r_ok and r_fun):
                return False, None
            if isinstance(expr.op, ast.Add):
                funb = TemplateNode.f_add
            else:
                return False, None
            return True, funb(l_fun, r_fun)
        if isinstance(expr, ast.Subscript):  # implemented fully
            v_ok, v_fun = self.op_expr(expr.value)
            if not (v_ok and v_fun):
                return False, None
            if isinstance(expr.slice, ast.Constant):
                return True, TemplateNode.f_subscript_c(v_fun, expr.slice.value)
            s_ok, s_fun = self.op_expr(expr.slice)
            if not (s_ok and s_fun):
                return False, None

            return True, TemplateNode.f_subscript(v_fun, s_fun)
        if isinstance(expr, ast.Compare):
            if isinstance(expr.left, ast.Constant) and len(expr.ops) == 1:
                c_ok, c_fun = self.op_expr(expr.comparators[0])
                if c_ok and c_fun:
                    return True, TemplateNode.f_in_lc(expr.left.value, c_fun)
            l_ok, l_fun = self.op_expr(expr.left)
            if not (l_ok and l_fun):
                return False, None
            if len(expr.ops) == 1 and isinstance(expr.comparators[0], ast.Constant):
                op = expr.ops[0]
                if isinstance(op, ast.NotEq):
                    return True, TemplateNode.f_noteq_c(l_fun, expr.comparators[0].value)
                elif isinstance(op, ast.Eq):
                    return True, TemplateNode.f_eq_c(l_fun, expr.comparators[0].value)
            funac = []
            for idx, op in enumerate(expr.ops):
                c_ok, c_fun = self.op_expr(expr.comparators[idx])
                if not (c_ok and c_fun):
                    return False, None
                if isinstance(op, ast.In):
                    ffc = TemplateNode.f_in
                elif isinstance(op, ast.NotEq):
                    ffc = TemplateNode.f_noteq
                elif isinstance(op, ast.Eq):
                    ffc = TemplateNode.f_eq
                else:
                    return False, None
                funac.append(ffc(c_fun))
            return True, TemplateNode.f_compare(l_fun, tuple(funac))
        if isinstance(expr, ast.BoolOp):  # implemented fully
            funa = []
            if isinstance(expr.op, ast.And):
                ffb = TemplateNode.f_and
            elif isinstance(expr.op, ast.Or):
                ffb = TemplateNode.f_or
            else:
                return False, None
            for v in expr.values:
                v_ok, v_fun = self.op_expr(v)
                if not (v_ok and v_fun):
                    return False, None
                funa.append(v_fun)
            return True, ffb(tuple(funa))
        if isinstance(expr, ast.UnaryOp):  # implemented fully
            o_ok, o_fun = self.op_expr(expr.operand)
            if not (o_ok and o_fun):
                return False, None
            if isinstance(expr.op, ast.Not):
                ffu = TemplateNode.f_not
            elif isinstance(expr.op, ast.UAdd):
                ffu = TemplateNode.f_uadd
            elif isinstance(expr.op, ast.USub):
                ffu = TemplateNode.f_usub
            elif isinstance(expr.op, ast.Invert):
                ffu = TemplateNode.f_invert
            else:
                return False, None
            return True, ffu(o_fun)
        return False, None

    def eval(self, s: str, data: eval_data_t, msg: str) -> Any:
        ok, aa, fun = _ast_parse(s)
        if not ok:
            # check for Expr needed for typing
            if (
                isinstance(aa, ast.Module)
                and len(aa.body) == 1
                and isinstance(aa.body[0], ast.Expr)
            ):
                ok, fun = self.op_expr(aa.body[0].value)
                if fun:
                    _ast_set(s, fun)
        if fun:
            return fun(self, data)
        sys.stderr.write(astdump(f"eval {msg} {s}", aa))
        sys.stderr.write(
            f"stack={self.parent.stack_variables}\ndata={data.keys()} {data}\n"
        )
        msg = f"eval: {msg} '{s}' stack={self.parent.stack_variables} data keys={data.keys()}"
        raise self.parent.parser_exception(msg)

    def exec(self, s: str, data: eval_data_t, msg: str) -> None:
        ok, aa, fun = _ast_parse(s)
        if not ok:
            # check for Assign needed for typing
            if (
                isinstance(aa, ast.Module)
                and len(aa.body) == 1
                and isinstance(aa.body[0], ast.Assign)
            ):
                ok, fun = self.op_assign(aa.body[0])
                if fun:
                    _ast_set(s, fun)
        if fun:
            fun(self, data)
            return
        sys.stderr.write(astdump(f"exec {msg} {s}", aa))
        sys.stderr.write(
            f"stack={self.parent.stack_variables}\ndata={data.keys()} {data}\n"
        )
        msg = f"exec: {msg} '{s}' stack={self.parent.stack_variables} data keys={data.keys()}"
        raise self.parent.parser_exception(msg)


class EndTemplateNode(TemplateNode):
    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        pass


class TopLevelTemplateNode(TemplateNode):
    def __init__(self, parent: Template) -> None:
        TemplateNode.__init__(self, parent, "")

    def add_node(self, node: None | node_t) -> bool:
        if node is None:
            return True
        self.node_list.append(node)
        return False


class ForTemplateNode(TemplateNode):
    def __init__(self, parent: Template, s: str) -> None:
        TemplateNode.__init__(self, parent, s)
        match = re_for_loop.match(s)
        if match is None:
            msg = f"[[{self.s}]] is not a valid for-loop expression"
            raise self.parent.parser_exception(msg)
        self.vars = [v.strip() for v in match.group(1).split(",")]
        self.expression = match.group(2)

    def execute(self, stream: stream_t, data: eval_data_t) -> None:
        self.parent.stack_variables.append({})
        gen = self.eval(self.expression, data, "for")
        for lst in gen:
            if isinstance(lst, (list, tuple)):
                for index, value in enumerate(lst):
                    self.parent.stack_variables[-1][self.vars[index]] = value
            else:
                self.parent.stack_variables[-1][self.vars[0]] = lst
            TemplateNode.execute(self, stream, data)
        self.parent.stack_variables.pop()


class IfTemplateNode(TemplateNode):
    def __init__(self, parent: Template, s: str) -> None:
        self.else_node: None | TemplateNode = None
        TemplateNode.__init__(self, parent, s)
        match = re_if.match(s)
        if match is None:
            msg = f"[[{self.s}]] is not a valid if expression"
            raise self.parent.parser_exception(msg)
        self.expression = match.group(1)

    def add_node(self, node: None | node_t) -> bool:
        if isinstance(node, EndTemplateNode):
            return True
        if isinstance(node, ElseTemplateNode):
            self.else_node = node
            return True
        if isinstance(node, ElifTemplateNode):
            self.else_node = node
            return True
        if node is None:
            msg = f"[[{self.s}]] does not have a matching [[end]]"
            raise self.parent.parser_exception(msg)
        self.node_list.append(node)
        return False

    def execute(self, stream: stream_t, data: eval_data_t) -> None:
        gen = self.eval(self.expression, data, "if")
        if gen:
            TemplateNode.execute(self, stream, data)
        elif self.else_node is not None:
            self.else_node.execute(stream, data)


class ElifTemplateNode(IfTemplateNode):
    def __init__(  # pylint: disable=super-init-not-called
        self, parent: Template, s: str
    ) -> None:
        self.else_node = None
        TemplateNode.__init__(self, parent, s)  # pylint: disable=non-parent-init-called
        match = re_elif.match(s)
        if match is None:
            msg = f"[[{self.s}]] is not a valid elif expression"
            raise self.parent.parser_exception(msg)
        self.expression = match.group(1)


class ElseTemplateNode(TemplateNode):
    pass


class LeafTemplateNode(TemplateNode):
    def __init__(  # pylint: disable=super-init-not-called
        self, parent: Template, s: str
    ) -> None:
        self.parent = parent
        self.s = s

    def execute(self, stream: stream_t, _data: eval_data_t) -> None:
        stream.write(self.s)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


class CommentTemplateNode(LeafTemplateNode):
    def execute(self, stream: stream_t, data: eval_data_t) -> None:
        pass


class ExpressionTemplateNode(LeafTemplateNode):
    def execute(self, stream: stream_t, data: eval_data_t) -> None:
        gen = self.eval(self.s, data, "expression")
        stream.write(str(gen))


class ExecTemplateNode(LeafTemplateNode):
    def __init__(self, parent: Template, s: str) -> None:
        LeafTemplateNode.__init__(self, parent, s)
        match = re_exec.match(s)
        if match is None:
            msg = f"[[{self.s}]] is not a valid statement"
            raise self.parent.parser_exception(msg)
        self.s = match.group(1)

    def execute(self, _stream: stream_t, data: eval_data_t) -> None:
        self.exec(self.s, data, "exec")


############################################################
# Node factory
template_factory_type_map = {
    "if": IfTemplateNode,
    "for": ForTemplateNode,
    "exec": ExecTemplateNode,
    "elif": ElifTemplateNode,
    "else": ElseTemplateNode,
}


def TemplateNodeFactory(parent: Template) -> None | TemplateNode:
    src = parent.parser_get()

    if src is None:
        return None
    match = re_directive.search(src)
    if match is None:
        parent.parser_eat(len(src))
        return LeafTemplateNode(parent, src)
    if src == "" or match.start() != 0:
        parent.parser_eat(match.start())
        return LeafTemplateNode(parent, src[: match.start()])
    directive = match.group()[2:-2].strip()
    parent.parser_eat(match.end())
    # most common, slight speedup
    if directive == "end":
        return EndTemplateNode()
    if re_comment.match(directive):
        return CommentTemplateNode(parent, directive)
    for key, typ in template_factory_type_map.items():
        if directive.startswith(key):
            return typ(parent, directive)
    return ExpressionTemplateNode(parent, directive)
