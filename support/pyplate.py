"""
PyPlate : a simple Python-based templating program

PyPlate parses a file and replaces directives (in double square brackets [[ ... ]])
by various means using a given dictionary of variables.  Arbitrary Python code
can be run inside many of the directives, making this system highly flexible.

Usage:
# Load and parse template file
template = pyplate.Template("output") (filename or string)
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

import io
import re

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
    def __init__(self, lineno: int, s: str) -> None:
        Exception.__init__(self, f"line {lineno:d}: {s}")


class Template:
    def __init__(self, template: str) -> None:
        self.file = io.StringIO(template)
        self.line = self.file.read()
        self.lineno = 0
        self.tree = TopLevelTemplateNode(self)
        self.file.close()

    def parser_get(self):
        if self.line == "":
            return None
        return self.line

    def parser_eat(self, chars):
        self.lineno = self.lineno + self.line[:chars].count("\n")
        self.line = self.line[chars:]

    def parser_exception(self, s: str) -> ParseError:
        return ParseError(self.lineno, s)

    def execute_string(self, data):
        s = io.StringIO()
        self.execute(s, data)
        return s.getvalue()

    def execute(self, stream, data):
        self.tree.execute(stream, data)

    def __repr__(self):
        return repr(self.tree)


############################################################
# NODES
class TemplateNode:
    def __init__(self, parent, s):
        self.parent = parent
        self.s = s
        self.node_list = []
        while True:
            new_node = TemplateNodeFactory(parent)
            if self.add_node(new_node):
                break

    def add_node(self, node):
        if isinstance(node, EndTemplateNode):
            return True
        if node is None:
            msg = f"[[{self.s}]] does not have a matching [[end]]"
            raise self.parent.parser_exception(msg)
        self.node_list.append(node)
        return False

    def execute(self, stream, data):
        for node in self.node_list:
            node.execute(stream, data)

    def __repr__(self):
        r = "<" + self.__class__.__name__ + " "
        for i in self.node_list:
            r = r + repr(i)
        return r + ">"


class EndTemplateNode(TemplateNode):
    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        pass


class TopLevelTemplateNode(TemplateNode):
    def __init__(self, parent):
        TemplateNode.__init__(self, parent, "")

    def add_node(self, node):
        if node is None:
            return True
        self.node_list.append(node)
        return False


class ForTemplateNode(TemplateNode):
    def __init__(self, parent, s):
        TemplateNode.__init__(self, parent, s)
        match = re_for_loop.match(s)
        if match is None:
            msg = f"[[{self.s}]] is not a valid for-loop expression"
            raise self.parent.parser_exception(msg)
        self.vars_temp = match.group(1).split(",")
        self.vars = []
        for v in self.vars_temp:
            self.vars.append(v.strip())
        # print(self.vars)
        self.expression = match.group(2)

    def execute(self, stream, data):
        remember_vars = {}
        for var in self.vars:
            if var in data:
                remember_vars[var] = data[var]
        # pylint: disable=eval-used
        for lst in eval(self.expression, globals(), data):  # noqa: S307, PGH001
            if isinstance(lst, (list, tuple)):
                for index, value in enumerate(lst):
                    data[self.vars[index]] = value
            else:
                data[self.vars[0]] = lst
            TemplateNode.execute(self, stream, data)
        for key, value in remember_vars.items():
            data[key] = value


class IfTemplateNode(TemplateNode):
    def __init__(self, parent, s):
        self.else_node = None
        TemplateNode.__init__(self, parent, s)
        match = re_if.match(s)
        if match is None:
            msg = f"[[{self.s}]] is not a valid if expression"
            raise self.parent.parser_exception(msg)
        self.expression = match.group(1)

    def add_node(self, node):
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

    def execute(self, stream, data):
        # pylint: disable=eval-used
        if eval(self.expression, globals(), data):  # noqa: S307, PGH001
            TemplateNode.execute(self, stream, data)
        elif self.else_node is not None:
            self.else_node.execute(stream, data)


class ElifTemplateNode(IfTemplateNode):
    def __init__(self, parent, s):  # pylint: disable=super-init-not-called
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
    def __init__(self, parent, s):  # pylint: disable=super-init-not-called
        self.parent = parent
        self.s = s

    def execute(self, stream, _data):
        stream.write(self.s)

    def __repr__(self):
        return "<" + self.__class__.__name__ + ">"


class CommentTemplateNode(LeafTemplateNode):
    def execute(self, stream, data):
        pass


class ExpressionTemplateNode(LeafTemplateNode):
    def execute(self, stream, data):
        stream.write(
            # pylint: disable=eval-used
            str(eval(self.s, globals(), data))  # noqa: S307, PGH001
        )


class ExecTemplateNode(LeafTemplateNode):
    def __init__(self, parent, s):
        LeafTemplateNode.__init__(self, parent, s)
        match = re_exec.match(s)
        if match is None:
            msg = f"[[{self.s}]] is not a valid statement"
            raise self.parent.parser_exception(msg)
        self.s = match.group(1)

    def execute(self, _stream, data):
        # pylint: disable=exec-used
        exec(self.s, globals(), data)  # noqa: S102


############################################################
# Node factory
template_factory_type_map = {
    "if": IfTemplateNode,
    "for": ForTemplateNode,
    "exec": ExecTemplateNode,
    "elif": ElifTemplateNode,
    "else": ElseTemplateNode,
}


def TemplateNodeFactory(parent):
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
