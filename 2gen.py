from typing import Any, Tuple
import astor
import ast
import re
from enum import Enum


# from https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


negative_op = [ast.NotEq, ast.NotIn, ast.IsNot]


class Order(Enum):
    Single = 1
    Semi = 2
    Decr = 3
    Incr = 4
    Equal = 5


class Type(Enum):
    Negative = 1
    Semi = 2
    Positive = 3


class IfVertical(ast.NodeVisitor):
    def __init__(self):
        self.negative = 0
        self.all = 0

        self.complex = dict()

        self.vertical = dict()
        self.elses = 0

        self.single = 0
        self.decr = 0
        self.semi = 0
        self.incr = 0
        self.equal = 0

    def check_negative_in(self, node: ast.Expr) -> Type:
        if type(node) == ast.UnaryOp:
            if type(node.op) == ast.Not:
                return Type.Negative
            return self.check_negative_in(node.operand)
        if type(node) == ast.Compare:
            global negative_op
            for op in node.ops:
                if type(op) in negative_op:
                    return Type.Negative
            return Type.Positive
        if type(node) == ast.BoolOp:
            result = []
            for v in node.values:
                result.append(self.check_negative_in(v))
            if Type.Semi in result:
                return Type.Semi

            if Type.Negative not in result:
                return Type.Positive

            if Type.Positive in result:
                return Type.Semi

            return Type.Negative
        return Type.Positive

    def check_complex_in(self, node: ast.Expr) -> int:
        if type(node) == ast.UnaryOp:
            return 1 + self.check_complex_in(node.operand)
        if type(node) == ast.BinOp:
            return 1 + self.check_complex_in(node.left) + self.check_complex_in(node.right)
        if type(node) == ast.BoolOp:
            result = 1
            for expr in node.values:
                result += self.check_complex_in(expr)
            return result
        if type(node) == ast.Compare:
            result = len(node.ops) + self.check_complex_in(node.left)
            for expr in node.comparators:
                result += self.check_complex_in(expr)
            return result
        if type(node) == ast.IfExp:
            return 1 + self.check_complex_in(node.test)
        return 0

    def check_negative(self, node: ast.Expr):
        self.all += 1
        r = self.check_negative_in(node)
        if r == Type.Negative:
            self.negative += 1
        elif r == Type.Semi:
            self.negative += 1

    def check_complex(self, node: ast.Expr):
        com = self.check_complex_in(node)
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

        t, size = self.check_body_else(node)
        if t == Order.Single:
            self.single += 1
        elif t == Order.Decr:
            self.decr += 1
        elif t == Order.Incr:
            self.incr += 1
        elif t == Order.Semi:
            self.semi += 1
        elif t == Order.Equal:
            self.equal += 1

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

    def check_body_else(self, node: ast.If) -> Tuple[Order, int]:
        first = node.body[0]
        last = node.body[-1]
        try:
            while True:
                try:
                    temp = last.orelse[-1]
                except Exception:
                    temp = last.body[-1]
                if temp:
                    last = temp
                    continue
                break
        except Exception:
            var = 1  # nothing here
        body_size = last.lineno - first.lineno + 1

        if len(node.orelse) == 0:
            return Order.Single, body_size

        if len(node.orelse) == 1 and type(node.orelse[0]) == ast.If:
            order, size = self.check_body_else(node.orelse[0])
            if order == Order.Semi:
                return Order.Semi, body_size

            if order == Order.Equal or order == Order.Single:
                if size < body_size:
                    return Order.Decr, body_size
                elif size > body_size:
                    return Order.Incr, body_size
                else:
                    return Order.Equal, body_size

            if order == Order.Decr:
                if size <= body_size:
                    return Order.Decr, body_size
                else:
                    return Order.Semi, body_size
            if order == Order.Incr:
                if size >= body_size:
                    return Order.Incr, body_size
                else:
                    return Order.Semi, body_size

        first = node.orelse[0]
        last = node.orelse[-1]
        try:
            while True:
                try:
                    temp = last.orelse[-1]
                except Exception:
                    temp = last.body[-1]
                if temp:
                    last = temp
                    continue
                break
        except Exception:
            var = 1  # nothing here
        else_size = last.lineno - first.lineno + 1

        if else_size < body_size:
            return Order.Decr, body_size
        elif else_size > body_size:
            return Order.Incr, body_size
        else:
            return Order.Equal, body_size

    def visit_If(self, node: ast.If) -> Any:
        self.check_vertical(node)
        return node


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

        self.arg_types = 0

        self.len_args = dict()

        self.body_size = dict()

    def check_length_of_names(self, name):
        if re.match(r'^[A-Z0-9]+$', name):
            size = 1
            if name == 'ISTERMINAL' or name == 'ISNONTERMINAL' or name == 'ISEOF' or name == "BBIBOLL":
                size = 2
            if size in self.len_names:
                self.len_names[size] += 1
            else:
                self.len_names[size] = 1
        else:
            elements = camel_to_snake(name).split('_')
            size = len(list(filter(None, elements)))
            if size in self.len_names:
                self.len_names[size] += 1
            else:
                self.len_names[size] = 1

    def check_name_pep8(self, name):
        if re.match(r'^[a-z0-9_]+$', name):
            self.pep8_names["pep8"] += 1
        elif re.match(r'^[A-Z0-9]+$', name):
            self.pep8_names["no"] += 1
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
        big_a_list = ["POOLIN", "POLLOUT", "POLLERR"]
        for arg in temp:
            if re.match(r'^[A-Z0-9]+$', arg.arg):
                size = 1
                if arg.arg in big_a_list:
                    size = 2
                if size in self.len_args:
                    self.len_args[size] += 1
                else:
                    self.len_args[size] = 1
            else:
                elements = camel_to_snake(arg.arg).split('_')
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
            elif re.match(r'^[A-Z0-9]+$', arg.arg):
                self.pep8_args["no"] += 1
            elif re.match(r'^[A-Za-z0-9]+$', arg.arg):
                self.pep8_args["camel_case"] += 1
            elif re.match(r'^[A-Za-z0-9_]+$', arg.arg):
                self.pep8_args["pep8C"] += 1
            else:
                self.pep8_args["no"] += 1

    def check_body(self, node: ast.FunctionDef):
        if len(node.body) != 0:
            first = node.body[0]
            last = node.body[-1]
            try:
                while True:
                    try:
                        temp = last.orelse[-1]
                    except Exception:
                        temp = last.body[-1]
                    if temp:
                        last = temp
                        continue
                    break
            except Exception:
                var = 1  # nothing here
            size = last.lineno - first.lineno + 1
            if size not in self.body_size:
                self.body_size[size] = 0

            self.body_size[size] += 1

    def check_types(self, args):
        temp = list(args.args)
        if len(temp) > 0:
            if temp[0].arg == 'self':
                temp = temp[1:]
            elif temp[0].arg == 'cls':
                temp = temp[1:]
        for arg in temp:
            if arg.annotation:
                self.arg_types += 1

    def check_function_def(self, node: ast.FunctionDef):
        self.count += 1
        self.check_types(node.args)
        self.count_args(node.args)
        self.check_args_pep8(node.args)
        self.check_args_len(node.args)
        self.check_name_pep8(node.name)
        self.check_length_of_names(node.name)
        self.check_body(node)

    def generic_visit(self, node: ast.AST) -> Any:
        if type(node) == ast.FunctionDef:
            self.check_function_def(node)

        return ast.NodeVisitor.generic_visit(self, node)


class ForHelper(ast.NodeVisitor):
    def __init__(self):
        self.continue_ = 0
        self.break_ = 0
        self.return_ = 0

        self.whiles = list()

        self.fors = list()

    def visit_Continue(self, node: ast.Continue) -> Any:
        self.continue_ += 1
        return node

    def visit_Break(self, node: ast.Break) -> Any:
        self.break_ += 1
        return node

    def visit_Return(self, node: ast.Return) -> Any:
        self.return_ += 1
        return node

    def visit_While(self, node: ast.While) -> Any:
        self.whiles.append(node)
        return node

    def visit_For(self, node: ast.For) -> Any:
        self.fors.append(node)
        return node


class For(ast.NodeVisitor):
    def __init__(self):
        self.all = 0
        self.with_else = 0

        self.num_while = 0
        self.num_continue = 0
        self.num_break = 0
        self.num_return = 0

        self.temp = dict()

        self.body_size = dict()

    def check_else(self, node: ast.For):
        if len(node.orelse) != 0:
            self.with_else += 1

    def visit_For(self, node: ast.For) -> Any:
        self.all += 1

        self.check_else(node)

        self.visit(node.target)

        key = type(node.iter).__name__
        if key not in self.temp:
            self.temp[key] = 0

        self.temp[key] += 1

        self.visit(node.iter)

        if len(node.body) != 0:
            first = node.body[0]
            last = node.body[-1]
            try:
                while True:
                    try:
                        temp = last.orelse[-1]
                    except Exception:
                        temp = last.body[-1]
                    if temp:
                        last = temp
                        continue
                    break
            except Exception:
                var = 1  # nothing here
            size = last.lineno - first.lineno + 1
            if size not in self.body_size:
                self.body_size[size] = 0

            self.body_size[size] += 1

        helper = ForHelper()
        for stmt in node.body:
            helper.visit(stmt)

        while len(helper.whiles) != 0:
            helper2 = ForHelper()
            whiles = list(helper.whiles)
            for nwhile in whiles:
                for n in nwhile.body:
                    helper2.visit(n)
                for n in nwhile.orelse:
                    helper2.visit(n)
                whiles += helper2.whiles
                helper2.whiles = []
            self.num_while += len(whiles)
            helper.whiles = []
            for nfor in helper2.fors:
                helper.visit(nfor)

        self.num_continue += helper.continue_
        self.num_break += helper.break_
        self.num_return += helper.return_

        for fn in helper.fors:
            self.visit(fn)

        for stmt in node.orelse:
            self.visit(stmt)


class F:
    def __init__(self):
        self.cif = ast.If
        self.path = ""


class Width(ast.NodeVisitor):
    def __init__(self, depth=0):
        self.width = dict()
        self.current_depth = depth
        self.max_depth = depth + 1

        self.func = 0
        self.afunc = 0
        self.fors = 0
        self.afors = 0
        self.whiles = 0
        self.ifs = 0
        self.withs = 0
        self.awiths = 0
        self.trys = 0
        self.ex_h = 0
        self.classes = 0

    def check_body(self, body):
        if len(body) == 0:
            return

        w = Width(self.current_depth + 1)
        for n in body:
            w.visit(n)

        self.func += w.func
        self.afunc += w.afunc
        self.fors += w.fors
        self.afors += w.afors
        self.whiles += w.whiles
        self.ifs += w.ifs
        self.withs += w.withs
        self.awiths += w.awiths
        self.trys += w.trys
        self.ex_h += w.ex_h
        self.classes += w.classes

        if self.max_depth < w.max_depth:
            self.max_depth = w.max_depth

        if self.current_depth == 0:
            if w.max_depth not in self.width:
                self.width[w.max_depth] = 0
            self.width[w.max_depth] += 1

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.classes += 1
        self.check_body(node.body)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.func += 1
        self.check_body(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.afunc += 1
        self.check_body(node.body)
        return node

    def visit_For(self, node: ast.For) -> Any:
        self.fors += 1
        self.check_body(node.body)
        self.check_body(node.orelse)
        return node

    def visit_AsyncFor(self, node: ast.AsyncFor) -> Any:
        self.afors += 1
        self.check_body(node.body)
        self.check_body(node.orelse)
        return node

    def visit_While(self, node: ast.While) -> Any:
        self.whiles += 1
        self.check_body(node.body)
        self.check_body(node.orelse)
        return node

    def visit_If(self, node: ast.If) -> Any:
        self.ifs += 1
        self.check_body(node.body)
        self.check_body(node.orelse)
        return node

    def visit_With(self, node: ast.With) -> Any:
        self.withs += 1
        self.check_body(node.body)
        return node

    def visit_AsyncWith(self, node: ast.AsyncWith) -> Any:
        self.awiths += 1
        self.check_body(node.body)
        return node

    def visit_Try(self, node: ast.AsyncWith) -> Any:
        self.trys += 1
        self.check_body(node.body)
        self.check_body(node.orelse)
        self.check_body(node.finalbody)
        self.check_body(node.handlers)
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        self.ex_h += 1
        self.check_body(node.body)
        return node


if __name__ == "__main__":
    files = astor.code_to_ast.find_py_files("./projects")

    v = IfVertical()
    f = Func()
    fl = For()
    w = Width()
    for i in files:
        if "test" in i[1]:
            continue
        try:
            a = astor.code_to_ast.parse_file(i[0] + "/" + i[1])
        except Exception as e:
            print("ERROR", i[0] + "/" + i[1], ":", e)
            continue
        v.visit(a)
        f.visit(a)
        fl.visit(a)
        w.visit(a)

    all_for = 57083  # 231
    print("\nFor\n")

    print("All:", fl.all)
    assert fl.all == all_for
    print("Else:", fl.with_else)

    print("Inner whiles", fl.num_while)
    print("Break:", fl.num_break)
    print("Continue:", fl.num_continue)
    print("Return:", fl.num_return)

    print("Body size:")
    for_body_count = 0
    for (key, value) in sorted(fl.body_size.items()):
        print("\t", key, "\t", value)
        for_body_count += value
    assert for_body_count == fl.all

    all_func = 221050
    print("\nFunc\n")

    print("All:", f.count)
    assert all_func == f.count

    t = 0
    print("Names length:")
    for (key, value) in sorted(f.len_names.items()):
        print("\t", key, "\t", value)
        t += value
    assert t == all_func

    t = 0
    print("Names:")
    for (key, value) in sorted(f.pep8_names.items()):
        print("\t", key, "\t", value)
        t += value
    assert t == all_func

    print("Count Args:")
    t = 0
    a = 0
    for (key, value) in sorted(f.args.items()):
        print("\t", key, "\t", value)
        t += value
        a += key * value
    assert t == all_func
    print("Types Args:", f.arg_types)

    t = 0
    for (k, va) in f.args.items():
        t += va * k
    print(t)

    t = 0
    print("Names args length:")
    for (key, value) in sorted(f.len_args.items()):
        print("\t", key, "\t", value)
        t += value
    assert t == a

    r = 0
    for (k, va) in f.len_args.items():
        r += va
    print(r)

    print("Args Names:")
    t = 0
    for (key, value) in sorted(f.pep8_args.items()):
        print("\t", key, "\t", value)
        t += value
    assert t == a

    j = 0
    for (k, va) in f.pep8_args.items():
        j += va
    print(j)

    print("Body size:")
    fun_body_count = 0
    for (key, value) in sorted(f.body_size.items()):
        print("\t", key, "\t", value)
        fun_body_count += value
    assert fun_body_count == f.count

    all_if = 278613
    print("\nIf\n")

    print("Negativity")
    print("\tAll:", v.all)
    assert all_if == v.all
    print("\tNegative:", v.negative)
    print("\tPositive:", v.all - v.negative)

    print("Complexity:")
    t = 0
    for (key, value) in sorted(v.complex.items()):
        print("\t", key, "\t", value)
        t += value
    assert t == v.all

    print("Vertical:")
    for (key, value) in sorted(v.vertical.items()):
        print("\t", key, "\t", value)

    s = 0
    m = 0
    for (k, va) in v.vertical.items():
        s += k * va
        m += va
    print(v.elses, s)
    assert s - v.elses == v.all

    print("Order:")
    print("\tSingle:", v.single)
    print("\tIncr:", v.incr)
    print("\tEqual:", v.equal)
    print("\tDecr:", v.decr)
    print("\tSemi:", v.semi)
    assert v.semi + v.single + v.incr + v.equal + v.decr == m

    print("Width:")
    for (key, value) in sorted(w.width.items()):
        print("\t", key, "\t", value)

    # from first analyzer - classes nodes
    assert w.ifs == all_if
    assert w.func == all_func
    assert w.fors == all_for
    assert w.ex_h == 31487
    assert w.trys == 30040
    assert w.withs == 10338
    assert w.afunc == 9839
    assert w.whiles == 4888
    assert w.awiths == 210
    assert w.afors == 38
    assert w.classes == 45838
