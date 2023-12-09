"""
PyPlate : a simple Python-based templating program

PyPlate parses a file and replaces directives (in double square brackets [[ ... ]])
by various means using a given dictionary of variables.  Arbitrary Python code
can be run inside many of the directives, making this system highly flexible.

Usage:
# Load and parse template file
template = pyplate.Template("output") (filename or string)
# Execute it with a dictionary of variables
template.execute_file(output_stream, locals())

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

  [[def ...(...)]]  define a "function" out of other templating elements
  [[end]]

  [[call ...]]  call a templating function (not a regular Python function)
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
import sys

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
    def __init__(self, lineno, s):
        Exception.__init__(self, f"line {lineno:d}: {s}")


class Template:
    def __init__(self, filename=None):
        if filename is not None:
            try:
                self.parse_file(filename)
            except:
                self.parse_string(filename)

    def parse_file(self, filename):
        with open(filename) as file:
            self.parse(file)

    def parse_string(self, template):
        file = io.StringIO(template)
        self.parse(file)
        file.close()

    def parse(self, file):
        self.file = file
        self.line = self.file.read()
        self.lineno = 0
        self.functions = {}
        self.tree = TopLevelTemplateNode(self)

    def parser_get(self):
        if self.line == "":
            return None
        return self.line

    def parser_eat(self, chars):
        self.lineno = self.lineno + self.line[:chars].count("\n")
        self.line = self.line[chars:]

    def parser_exception(self, s):
        raise ParseError(self.lineno, s)

    def execute_file(self, filename, data):
        with open(filename, "w") as file:
            self.execute(file, data)

    def execute_string(self, data):
        s = io.StringIO()
        self.execute(s, data)
        return s.getvalue()

    def execute_stdout(self, data):
        self.execute(sys.stdout, data)

    def execute(self, stream=sys.stdout, data=None):
        if data is None:
            data = {}
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
        while 1:
            new_node = TemplateNodeFactory(parent)
            if self.add_node(new_node):
                break

    def add_node(self, node):
        if node == "end":
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
        else:
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
        for list in eval(self.expression, globals(), data):
            if is_sequence(list):
                for index, value in enumerate(list):
                    data[self.vars[index]] = value
            else:
                data[self.vars[0]] = list
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
        else:
            self.expression = match.group(1)

    def add_node(self, node):
        if node == "end":
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
        if eval(self.expression, globals(), data):
            TemplateNode.execute(self, stream, data)
        elif self.else_node is not None:
            self.else_node.execute(stream, data)


class ElifTemplateNode(IfTemplateNode):
    def __init__(self, parent, s):
        self.else_node = None
        TemplateNode.__init__(self, parent, s)
        match = re_elif.match(s)
        if match is None:
            self.parent.parser_exception(f"[[{self.s}]] is not a valid elif expression")
        else:
            self.expression = match.group(1)


class ElseTemplateNode(TemplateNode):
    pass


class FunctionTemplateNode(TemplateNode):
    def __init__(self, parent, s):
        TemplateNode.__init__(self, parent, s)
        match = re_def.match(s)
        if match is None:
            self.parent.parser_exception(
                f"[[{self.s}]] is not a valid function definition"
            )
        self.function_name = match.group(1)
        self.vars_temp = match.group(2).split(",")
        self.vars = []
        for v in self.vars_temp:
            self.vars.append(v.strip())
        # print(self.vars)
        self.parent.functions[self.function_name] = self

    def execute(self, stream, data):
        pass

    def call(self, args, stream, data):
        remember_vars = {}
        for index, var in enumerate(self.vars):
            if var in data:
                remember_vars[var] = data[var]
            data[var] = args[index]
        TemplateNode.execute(self, stream, data)
        for key, value in remember_vars.items():
            data[key] = value


class LeafTemplateNode(TemplateNode):
    def __init__(self, parent, s):
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
        stream.write(str(eval(self.s, globals(), data)))


class ExecTemplateNode(LeafTemplateNode):
    def __init__(self, parent, s):
        LeafTemplateNode.__init__(self, parent, s)
        match = re_exec.match(s)
        if match is None:
            self.parent.parser_exception(f"[[{self.s}]] is not a valid statement")
        self.s = match.group(1)

    def execute(self, _stream, data):
        exec(self.s, globals(), data)
        pass


class CallTemplateNode(LeafTemplateNode):
    def __init__(self, parent, s):
        LeafTemplateNode.__init__(self, parent, s)
        match = re_call.match(s)
        if match is None:
            self.parent.parser_exception(f"[[{self.s}]] is not a valid function call")
        self.function_name = match.group(1)
        self.vars = "(" + match.group(2).strip() + ",)"

    def execute(self, stream, data):
        self.parent.functions[self.function_name].call(
            eval(self.vars, globals(), data), stream, data
        )


############################################################
# Node factory
template_factory_type_map = {
    "if": IfTemplateNode,
    "for": ForTemplateNode,
    "elif": ElifTemplateNode,
    "else": ElseTemplateNode,
    "def": FunctionTemplateNode,
    "call": CallTemplateNode,
    "exec": ExecTemplateNode,
}
template_factory_types = template_factory_type_map.keys()


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
    if directive == "end":
        return "end"
    if re_comment.match(directive):
        return CommentTemplateNode(parent, directive)
    for i in template_factory_types:
        if directive[0 : len(i)] == i:
            return template_factory_type_map[i](parent, directive)
    return ExpressionTemplateNode(parent, directive)


def is_sequence(obj):
    return bool(isinstance(obj, (list, tuple)))
