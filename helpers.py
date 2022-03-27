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


def get_unop(op):
    if isinstance(op, ast.UAdd):
        return "+"
    if isinstance(op, ast.USub):
        return "-"
    if isinstance(op, ast.Not):
        return "not"
    if isinstance(op, ast.Invert):
        return "~"

def get_boolop(op):
    if isinstance(op, ast.And):
        return "and"
    if isinstance(op, ast.Or):
        return "or"


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
    if isinstance(value, bool):
        return "i1"
    if isinstance(value, int):
        return "i64"
    if isinstance(value, str):
        return "str"
    # TODO: add more cases

