import astor
import ast

if __name__ == "__main__":
    files = astor.code_to_ast.find_py_files("./projects")

    results = dict()
    ignore_list = ["load", "store", "del",
                   "module", "interactive", "expression", "functiontype",
                   "mod", "stmt", "expr", "expr_context", "boolop",
                   "operator", "unaryop", "cmpop", "excepthandler",
                   "arguments", "arg", "keyword", "withitem", "type_ignore",
                   "name", "attribute", "call",
                   "importfrom", "import",
                   "num", "str", "bytes", "nameconstant", "ellipsis"
                   ]

    for i in files:
        try:
            a = astor.code_to_ast.parse_file(i[0] + "/" + i[1])
        except Exception as e:
            print("ERROR", i[0] + "/" + i[1], ":", e)
            continue

        for g in ast.walk(a):
            key = type(g).__name__.capitalize()
            if key.lower() in ignore_list:
                continue

            if key in results:
                results[key] += 1
            else:
                results[key] = 1

    results = {k: v for k, v in sorted(results.items(), key=lambda item: item[1], reverse=True)}

    for k in results:
        print(k, ": ", results[k])
