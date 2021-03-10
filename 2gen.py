from typing import Any
import astor
import ast
import re
import astunparse
from enum import Enum


class Type(Enum):
    Negative = 1
    Semi = 2
    Positive = 3


negative_op = [ast.NotEq, ast.NotIn, ast.IsNot]


def check_negative(node: ast.Expr) -> Type:
    if type(node) == ast.UnaryOp:
        if type(node.op) == ast.Not:
            return Type.Negative
        return check_negative(node.operand)
    if type(node) == ast.Compare:
        global negative_op
        for op in node.ops:
            if type(op) in negative_op:
                return Type.Negative
        return Type.Positive
    if type(node) == ast.BoolOp:
        result = []
        for v in node.values:
            result.append(check_negative(v))
        if Type.Semi in result:
            return Type.Semi

        if Type.Negative not in result:
            return Type.Positive

        if Type.Positive in result:
            return Type.Semi

        return Type.Negative
    return Type.Positive


def check_complex(node: ast.Expr) -> int:
    if type(node) == ast.UnaryOp:
        return 1 + check_complex(node.operand)
    if type(node) == ast.BinOp:
        return 1 + check_complex(node.left) + check_complex(node.right)
    if type(node) == ast.BoolOp:
        result = 1
        for expr in node.values:
            result += check_complex(expr)
        return result
    if type(node) == ast.Compare:
        result = len(node.ops) + check_complex(node.left)
        for expr in node.comparators:
            result += check_complex(expr)
        return result
    if type(node) == ast.IfExp:
        return 1 + check_complex(node.test)
    return 0


class IfVertical(ast.NodeVisitor):
    def __init__(self):
        self.negative = 0
        self.all = 0

        self.complex = dict()

        self.vertical = dict()
        self.elses = 0

    def check_negative(self, node: ast.Expr):
        self.all += 1
        r = check_negative(node)
        if r == Type.Negative:
            self.negative += 1
        elif r == Type.Semi:
            self.negative += 1

    def check_complex(self, node: ast.Expr):
        com = check_complex(node)
        if com in self.complex:
            self.complex[com] += 1
        else:
            self.complex[com] = 1

    def check_vertical(self, node: ast.If):
        r = self.getIfVertical(node)
        if r in self.vertical:
            self.vertical[r] += 1
        else:
            self.vertical[r] = 1

    def getIfVertical(self, node: ast.If) -> int:
        self.check_negative(node.test)
        self.check_complex(node.test)
        result = 1

        for n in node.body:
            self.visit(n)

        if len(node.orelse) == 0:
            return result

        if len(node.orelse) == 1 and type(node.orelse[0]) == ast.If:
            return result + self.getIfVertical(node.orelse[0])

        for n in node.orelse:
            self.visit(n)

        self.elses += 1
        result += 1

        return result

    def visit_If(self, node: ast.If) -> Any:
        self.check_vertical(node)
        return node


class IfWidth(ast.NodeVisitor):
    def __init__(self):
        self.width = dict()
        self.ifs = 0
        self.shadow = 0
        self.elses = 0


class Func(ast.NodeVisitor):
    def __init__(self):
        self.count = 0

        self.args = dict()

        self.pep8_names = dict()
        self.pep8_names["pep8"] = 0
        self.pep8_names["pep8C"] = 0  # Capitilize_names
        self.pep8_names["camel_case"] = 0
        self.pep8_names["no"] = 0

        self.len_names = dict()

        self.pep8_args = dict()
        self.pep8_args["pep8"] = 0
        self.pep8_args["pep8C"] = 0  # Capitilize_names
        self.pep8_args["camel_case"] = 0
        self.pep8_args["no"] = 0

        self.len_args = dict()

    def check_length_of_names(self, name):
        if re.match(r'^[a-z0-9_]+$', name):
            elements = name.split('_')
            size = len(list(filter(None, elements)))
            if size in self.len_names:
                self.len_names[size] += 1
            else:
                self.len_names[size] = 1
        elif re.match(r'^[A-Za-z0-9]+$', name):
            size = len(re.split('(?=[A-Z])', name))
            if size in self.len_names:
                self.len_names[size] += 1
            else:
                self.len_names[size] = 1
        elif re.match(r'^[A-Za-z0-9_]+$', name):
            elements = name.split('_')
            size = len(list(filter(None, elements)))
            if size in self.len_names:
                self.len_names[size] += 1
            else:
                self.len_names[size] = 1

    def check_name_pep8(self, name):
        if re.match(r'^[a-z0-9_]+$', name):
            self.pep8_names["pep8"] += 1
        elif re.match(r'^[A-Za-z0-9]+$', name):
            self.pep8_names["camel_case"] += 1
        elif re.match(r'^[A-Za-z0-9_]+$', name):
            self.pep8_names["pep8C"] += 1
        else:
            self.pep8_names["no"] += 1

    def count_args(self, args):
        count = len(args.args)
        if count > 0:
            if args.args[0].arg == 'self':
                count -= 1
            elif args.args[0].arg == 'cls':
                count -= 1
        if count in self.args:
            self.args[count] += 1
        else:
            self.args[count] = 1

    def check_args_len(self, args):
        temp = list(args.args)
        if len(temp) > 0:
            if temp[0].arg == 'self':
                temp = temp[1:]
            elif temp[0].arg == 'cls':
                temp = temp[1:]

        for arg in temp:
            if re.match(r'^[a-z0-9_]+$', arg.arg):
                elements = arg.arg.split('_')
                size = len(list(filter(None, elements)))
                if size in self.len_args:
                    self.len_args[size] += 1
                else:
                    self.len_args[size] = 1
            elif re.match(r'^[A-Za-z0-9]+$', arg.arg):
                size = len(re.split('(?=[A-Z])', arg.arg))
                if size in self.len_args:
                    self.len_args[size] += 1
                else:
                    self.len_args[size] = 1
            elif re.match(r'^[A-Za-z0-9_]+$', arg.arg):
                elements = arg.arg.split('_')
                size = len(list(filter(None, elements)))
                if size in self.len_args:
                    self.len_args[size] += 1
                else:
                    self.len_args[size] = 1

    def check_args_pep8(self, args):
        temp = list(args.args)
        if len(temp) > 0:
            if temp[0].arg == 'self':
                temp = temp[1:]
            elif temp[0].arg == 'cls':
                temp = temp[1:]

        for arg in temp:
            if re.match(r'^[a-z0-9_]+$', arg.arg):
                self.pep8_args["pep8"] += 1
            elif re.match(r'^[A-Za-z0-9]+$', arg.arg):
                self.pep8_args["camel_case"] += 1
            elif re.match(r'^[A-Za-z0-9_]+$', arg.arg):
                self.pep8_args["pep8C"] += 1
            else:
                self.pep8_args["no"] += 1

    def check_function_def(self, node: ast.FunctionDef):
        self.count += 1
        self.count_args(node.args)
        self.check_args_pep8(node.args)
        self.check_args_len(node.args)
        self.check_name_pep8(node.name)
        self.check_length_of_names(node.name)

    def generic_visit(self, node: ast.AST) -> Any:
        if type(node) == ast.FunctionDef:
            self.check_function_def(node)

        return ast.NodeVisitor.generic_visit(self, node)


if __name__ == "__main__":
    files = astor.code_to_ast.find_py_files("./projects/aiohttp")

    v = IfVertical()
    w = IfWidth()
    f = Func()
    for i in files:
        try:
            a = astor.code_to_ast.parse_file(i[0] + "/" + i[1])
        except Exception as e:
            print("ERROR", i[0] + "/" + i[1], ":", e)
            continue
        v.visit(a)
        f.visit(a)

    print("\nFunc\n")

    print("All:", f.count)

    print("Names length:")
    for (key, value) in sorted(f.len_names.items()):
        print("\t", key, ":", value)

    print("Names:")
    for (key, value) in sorted(f.pep8_names.items()):
        print("\t", key, ":", value)

    print("Count Args:")
    for (key, value) in sorted(f.args.items()):
        print("\t", key, ":", value)

    t = 0
    for (k, va) in f.args.items():
        t += va * k
    print(t)

    print("Names args length:")
    for (key, value) in sorted(f.len_args.items()):
        print("\t", key, ":", value)

    r = 0
    for (k, va) in f.len_args.items():
        r += va
    print(r)

    print("Args Names:")
    for (key, value) in sorted(f.pep8_args.items()):
        print("\t", key, ":", value)

    j = 0
    for (k, va) in f.pep8_args.items():
        j += va
    print(j)

    print("\nIf\n")

    print("Negativity")
    print("\tAll:", v.all)
    print("\tNegative:", v.negative)
    print("\tPositive:", v.all - v.negative)

    print("Complexity:")
    for (key, value) in sorted(v.complex.items()):
        print("\t", key, ":", value)

    print("Width:")
    for (key, value) in sorted(w.width.items()):
        print("\t", key, ":", value)

    g = 0
    for (k, va) in w.width.items():
        g += k * va
    print(w.ifs, w.elses, w.shadow, g)  # 1569 266 ? g

    print("Vertical:")
    for (key, value) in sorted(v.vertical.items()):
        print("\t", key, ":", value)

    s = 0
    for (k, va) in v.vertical.items():
        s += k * va
    print(v.elses, s, s - v.elses)
