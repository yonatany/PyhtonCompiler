import ast


def get_relop(op):
    if isinstance(op, ast.Eq):
        return "=="
    if isinstance(op, ast.NotEq):
        return "!="
    if isinstance(op, ast.Lt):
        return "<"
    if isinstance(op, ast.LtE):
        return "<="
    if isinstance(op, ast.Gt):
        return ">"
    if isinstance(op, ast.GtE):
        return ">="
    if isinstance(op, ast.Is):
        return "Is"
    if isinstance(op, ast.IsNot):
        return "Is Not"
    if isinstance(op, ast.In):
        return "In"
    if isinstance(op, ast.NotIn):
        return "Not In"


def get_ops(ops):
    oplist = []
    for op in ops:
        oplist.append(get_relop(op))
    return oplist


def get_binop(op):
    if isinstance(op, ast.Add):
        return "+"
    if isinstance(op, ast.Sub):
        return "-"
    if isinstance(op, ast.Mult):
        return "*"
    if isinstance(op, ast.Div):
        return ":"
    if isinstance(op, ast.FloorDiv):
        return ":"
    if isinstance(op, ast.Mod):
        return "mod"
    if isinstance(op, ast.Pow):
        return "**"
    if isinstance(op, ast.LShift):
        return "<<"
    if isinstance(op, ast.RShift):
        return ">>"
    if isinstance(op, ast.BitOr):
        return "|"
    if isinstance(op, ast.BitXor):
        return "xor"
    if isinstance(op, ast.BitAnd):
        return "&"
    if isinstance(op, ast.MatMult):
        return "*"


def type_of_val(value):
    if isinstance(value, int):
        return "i64"
    # TODO: add more cases


def merge_dict(true_dict, false_dict, true_end_node, false_end_node, merge_node):
    new_dict = {}
    for key in true_dict:
        if key in false_dict:
            if true_dict[key] == false_dict[key]:
                new_dict[key] = true_dict[key]
            else:
                new_dict[key] = ([(true_dict[key], true_end_node),
                                  (false_dict[key], false_end_node)], merge_node)
        else:
            new_dict[key] = (
                [(true_dict[key], true_end_node), ("None", false_end_node)], merge_node)
    for key in false_dict:
        if key not in new_dict:
            new_dict[key] = (
                [(false_dict[key], false_end_node), ("None", true_end_node)], merge_node)
    return new_dict
