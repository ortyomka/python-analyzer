import astor
import ast

if __name__ == "__main__":
    files = astor.code_to_ast.find_py_files("./projects")

    results = dict()
    accept_list = ["For", "AsyncFor", "While", "If",
                   "With", "AsyncWith", "Raise", "Try", "Pass", "Break", "Continue",
                   "Lambda", "IfExp", "Dict", "Set", "ListComp", "SetComp", "DictComp",
                   "List", "Tuple", "Slice", "GeneratorExp"]

    error_files = 0
    all_files = 0
    for i in files:
        all_files += 1
        try:
            a = astor.code_to_ast.parse_file(i[0] + "/" + i[1])
        except Exception as e:
            print("ERROR", i[0] + "/" + i[1], ":", e)
            error_files += 1
            continue

        for g in ast.walk(a):
            key = type(g).__name__
            if key not in accept_list:
                continue

            if key in results:
                results[key] += 1
            else:
                results[key] = 1

    results = {k: v for k, v in sorted(results.items(), key=lambda item: item[1], reverse=True)}

    for k in results:
        print(k, ": ", results[k])

    print("From all", all_files, "will reviewed", 1 - (error_files / all_files), "%")
