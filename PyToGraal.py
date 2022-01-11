import ast
import inspect
from helpers import *
from graphviz import Digraph


class PyToGraal:

    def __init__(self, func):
        self.counter = 0
        self.func = func
        self.G = Digraph()
        self.name_to_node = {}

    def parse(self):
        tree = ast.parse(inspect.getsource(self.func))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # new func added
                self.do_func(node)

        print(self.G)

    def do_func(self, node: ast.FunctionDef):
        name_to_val = {}
        last_control_node = self.add_node("|StartNode", color="Red", shape="box")
        parameter_counter = 0
        for arg in node.args.args:
            name_to_val[arg.arg] = "Parameter(" + str(parameter_counter) + ")"
            parameter_counter += 1
        name_to_val = self.do_body(node.body, last_control_node, name_to_val.copy())
        print(name_to_val)

    def do_body(self, body, last_control_node, name_to_val: dict):
        for cmd in body:
            if isinstance(cmd, ast.Assign):
                value, last_control_node = self.get_val(cmd.value, name_to_val, last_control_node)
                for lval in cmd.targets:
                    name_to_val[lval.id] = value
            if isinstance(cmd, ast.If):
                last_control_node, name_to_val = self.do_if(cmd, last_control_node, name_to_val.copy())
            if isinstance(cmd, ast.While):
                last_control_node, name_to_val = self.do_while(cmd, last_control_node, name_to_val.copy())
            if isinstance(cmd, ast.Return):
                last_control_node, name_to_val = self.do_return(cmd, last_control_node, name_to_val.copy())
        return last_control_node, name_to_val

    def do_while(self, cmd, last_control_node, name_to_val):
        name_to_val_before = name_to_val.copy()
        # print all while nodes and edges:
        end_before_loop_node = self.add_node("|End", color="Red", shape="box")
        self.G.edge(str(last_control_node), str(end_before_loop_node), color="Red")

        loop_begin_node = last_control_node = self.add_node("|LoopBegin", color="Red", shape="box")
        self.G.edge(str(end_before_loop_node), str(loop_begin_node), color="Red")

        if_node = self.add_node("|If", color="Red", shape="box")
        self.G.edge(str(last_control_node), str(if_node), color="Red")

        begin_node = self.add_node("|Begin", color="Red", shape="box")
        self.G.edge(str(if_node), str(begin_node), label="T", color="Red")

        loop_exit_node = self.add_node("|LoopExit", color="Red", shape="box")
        self.G.edge(str(if_node), str(loop_exit_node), label="F", color="Red")
        self.G.edge(str(loop_exit_node), str(loop_begin_node), style="dashed")

        last_loop_node, name_to_val_loop = self.do_body(cmd.body, begin_node, name_to_val.copy())

        loop_end_node = self.add_node("|LoopEnd", color="Red", shape="box")
        self.G.edge(str(last_loop_node), str(loop_end_node), color="Red")
        self.G.edge(str(loop_end_node), str(loop_begin_node), color="Red")

        name_to_val = merge_dict(name_to_val_loop, name_to_val_before, loop_end_node, end_before_loop_node,
                                 loop_begin_node)

        if isinstance(cmd.test, ast.Compare):
            comp_node, _ = self.do_compare(cmd.test, name_to_val, if_node)
            self.G.edge(str(comp_node), str(if_node), label="condition", color="Turquoise")

        # TODO: add more compare cases
        # TODO: fix the "phi problem"
        return loop_exit_node, name_to_val

    def do_if(self, cmd: ast.If, last_control_node, name_to_val: dict):
        if_node = self.add_node("|If", color="Red", shape="box")
        self.G.edge(str(last_control_node), str(if_node), label="next", color="Red")
        self.print_condition(cmd.test, name_to_val, if_node)

        begin_true_node = self.add_node("|Begin", color="Red", shape="box")  # begin true
        self.G.edge(str(if_node), str(begin_true_node), label="T", color="Red")
        begin_false_node = self.add_node("|Begin", color="Red", shape="box")  # begin false
        self.G.edge(str(if_node), str(begin_false_node), label="F", color="Red")
        last_true_node, name_to_val_true = self.do_body(cmd.body, begin_true_node, name_to_val.copy())  # body true
        last_false_node, name_to_val_false = self.do_body(cmd.orelse, begin_false_node,
                                                          name_to_val.copy())  # body false

        return self.do_merge(last_true_node, last_false_node, name_to_val_true.copy(), name_to_val_false.copy(),
                             name_to_val.copy())  # merge paths and return

    def do_merge(self, last_true_node, last_false_node, name_to_val_true: dict, name_to_val_false: dict, prev_dict):
        # make merge of paths in if cmd. then merge the dict
        # if node is none, we had return node in that case, so no need to end and merge this path
        if last_true_node is None:
            if last_false_node is None:
                return None, prev_dict
            else:
                end_false_node = self.add_node("|End", color="Red", shape="box")
                self.G.edge(str(last_false_node), str(end_false_node), color="Red")
                return end_false_node, name_to_val_false
        else:
            end_true_node = self.add_node("|End", color="Red", shape="box")
            self.G.edge(str(last_true_node), str(end_true_node), color="Red")
            if last_false_node is None:
                return end_true_node, name_to_val_true
            end_false_node = self.add_node("|End", color="Red", shape="box")
            self.G.edge(str(last_false_node), str(end_false_node), color="Red")

            # merge paths
            merge_node = self.add_node("|Merge", color="Red", shape="box")
            self.G.edge(str(end_true_node), str(merge_node), color="Red")
            self.G.edge(str(end_false_node), str(merge_node), color="Red")
            # merge dicts
            name_to_val = merge_dict(name_to_val_true, name_to_val_false, end_true_node, end_false_node, merge_node)
            return merge_node, name_to_val

    def do_return(self, cmd: ast.Return, last_control_node, name_to_val: dict):
        # print val to return then the node and edge
        val, last_control_node = self.get_val_and_print(cmd.value, name_to_val, last_control_node)
        ret_node = self.add_node("|Return", color="Red", shape="box")
        self.G.edge(str(val), str(ret_node), label="result", color="Turquoise")
        self.G.edge(str(last_control_node), str(ret_node), color="Red")
        return None, name_to_val

    def get_val(self, value, name_to_val: dict, last_control_node):
        # case variable node
        if isinstance(value, ast.Name):
            return name_to_val[value.id], last_control_node
        # case constant node
        elif isinstance(value, ast.Constant):
            return "Constant(" + str(value.value) + ", " + type_of_val(value.value) + ")", last_control_node
        # case binop node
        elif isinstance(value, ast.BinOp):
            left, last_control_node = self.get_val_and_print(value.left, name_to_val, last_control_node)
            right, last_control_node = self.get_val_and_print(value.right, name_to_val, last_control_node)
            op_node = self.add_node("|" + get_binop(value.op), color="Turquoise")
            self.G.edge(str(left), str(op_node), color="Turquoise", label="x")
            self.G.edge(str(right), str(op_node), color="Turquoise", label="y")
            return op_node, last_control_node

        # case relop node
        elif isinstance(value, ast.Compare):
            return self.do_compare(value, name_to_val, last_control_node, True)

        # case func
        elif isinstance(value, ast.Call):
            args_count = 0
            func_node = self.add_node("|MethodCallTarget", shape="box")
            if isinstance(value.func, ast.Name):  # case reg func
                name = value.func.id
            elif isinstance(value.func, ast.Attribute):  # case class method func
                object = value.func.value
                name = "Class." + value.func.attr
                object_node, last_control_node = self.get_val_and_print(object, name_to_val, last_control_node)
                self.G.edge(str(object_node), str(func_node), label="arg[" + str(args_count) + "]", color="Turquoise")
                args_count += 1
            call_node = self.add_node("|Call " + name, color="Red", shape="box")
            self.G.edge(str(call_node), str(func_node), style="dashed")
            self.G.edge(str(last_control_node), str(call_node), color="Red")
            last_control_node = call_node

            for arg in value.args:
                val_node, last_control_node = self.get_val_and_print(arg, name_to_val, last_control_node)
                self.G.edge(str(val_node), str(func_node), label="arg[" + str(args_count) + "]", color="Turquoise")
                args_count += 1
            if isinstance(value.func, ast.Attribute):
                return last_control_node, last_control_node
            return last_control_node, last_control_node
        # TODO: add more cases

    def print_value(self, value):
        if type(value) is tuple:  # phi case
            phi_node = node = self.add_node("|phi")
            merge_node = value[1]
            self.G.edge(str(phi_node), str(merge_node), style="dashed")
            for val, node_num in value[0]:
                val_node = self.print_value(val)
                self.G.edge(str(val_node), str(phi_node), label="from " + str(node_num), color="Turquoise")
                self.name_to_node[val] = phi_node

        else:
            if type(value) is int:  # val is already node
                node = value
            elif value in self.name_to_node:
                node = self.name_to_node[value]
            else:  # value is ready to print
                self.name_to_node[value] = node = self.add_node("|" + str(value), color="Turquoise")

        return node

    def get_val_and_print(self, object, name_to_val, last_control_node):
        object_node, last_control_node = self.get_val(object, name_to_val, last_control_node)
        if type(object_node) != int:
            object_node = self.print_value(object_node)
        return object_node, last_control_node

    def add_node(self, text, color="black", shape="ellipse"):
        self.G.node(str(self.counter), str(self.counter) + text, color=color, shape=shape)
        node = self.counter
        self.counter += 1
        return node

    def do_compare(self, compare: ast.Compare, name_to_val: dict, last_control_node, print_val=False):
        sum_node = None
        left, last_control_node = self.get_val_and_print(compare.left, name_to_val, last_control_node)
        rights = compare.comparators
        ops = get_ops(compare.ops)
        conditions = []
        for val, op in zip(rights, ops):
            right, last_control_node = self.get_val_and_print(val, name_to_val, last_control_node)
            comp_node = self.add_node("|" + op, color="Turquoise", shape="diamond")
            self.G.edge(str(left), str(comp_node), label="x", color="Turquoise")
            self.G.edge(str(right), str(comp_node), label="y", color="Turquoise")
            if print_val:
                zero = self.print_value("Constant(" + str(0) + ", " + type_of_val(0) + ")")
                one = self.print_value("Constant(" + str(1) + ", " + type_of_val(1) + ")")
                conditional_node = self.add_node("|Conditional", color="Turquoise", shape="diamond")
                self.G.edge(str(comp_node), str(conditional_node), label="?", color="Turquoise")
                self.G.edge(str(one), str(conditional_node), label="trueValue", color="Turquoise")
                self.G.edge(str(zero), str(conditional_node), label="falseValue", color="Turquoise")
                conditions.append(conditional_node)
                sum_node = conditional_node
            else:
                conditions.append(comp_node)
                sum_node = comp_node
            left = right
        if len(conditions) > 1:
            sum_node = self.add_node("|&", color="Turquoise", shape="diamond")
            for cond in conditions:
                self.G.edge(str(cond), str(sum_node), color="Turquoise")

        return sum_node, last_control_node

    def print_condition(self, test, name_to_val, if_node, label="condition"):
        # cases like "if condition:"
        if isinstance(test, ast.Name):
            to_compare = ast.Compare(left=test, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)])
            comp_node, _ = self.do_compare(to_compare, name_to_val, if_node)

        # cases like "if cond1 > cond2:"
        elif isinstance(test, ast.Compare):
            to_compare = test
            comp_node, _ = self.do_compare(to_compare, name_to_val, if_node)

        # cases like "if cond1 or cond2:"
        elif isinstance(test, ast.BoolOp):
            if isinstance(test.op, ast.And):
                boolop = "|and"
            else:  # or
                boolop = "|or"

            comp_node = self.add_node(boolop, color="Turquoise", shape="ellipse")
            self.print_condition(test.values[0], name_to_val, comp_node, label="first cond")
            self.print_condition(test.values[1], name_to_val, comp_node, label="second cond")

        self.G.edge(str(comp_node), str(if_node), label=label, color="Turquoise")

        # TODO: add more if cases
