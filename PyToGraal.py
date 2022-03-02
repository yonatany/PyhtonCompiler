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
        self.table_stack = []
        self.loop_exit = []

    def parse(self):
        tree = ast.parse(inspect.getsource(self.func))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # new func added
                self.do_func(node)

        print(self.G)

    def do_func(self, node: ast.FunctionDef):
        self.table_stack.append({})
        last_control_node = self.add_node("|StartNode", color="Red", shape="box")
        parameter_counter = 0
        for arg in node.args.args:
            self.table_stack[-1][arg.arg] = "Parameter(" + str(parameter_counter) + ")"
            parameter_counter += 1
        name_to_val = self.do_body(node.body, last_control_node)

        print(name_to_val)

    def do_body(self, body, last_control_node):
        print(self.table_stack)
        for cmd in body:
            if isinstance(cmd, ast.Assign):  # a = 1
                value, last_control_node = self.get_val(cmd.value, last_control_node)
                for lval in cmd.targets:
                    assert isinstance(lval, ast.Name), "not implemented"
                    self.table_stack[-1][lval.id] = value
            if isinstance(cmd, ast.AnnAssign):  # a:int = 1
                assert isinstance(cmd.target, ast.Name), "not implemented"
                value, last_control_node = self.get_val(cmd.value, last_control_node)
                self.table_stack[-1][cmd.target.id] = value
            if isinstance(cmd, ast.AugAssign):  # a += 1
                assert isinstance(cmd.target, ast.Name), "not implemented"
                value, last_control_node = self.get_val(ast.BinOp(left=cmd.target, op=cmd.op, right=cmd.value),
                                                        last_control_node)
                self.table_stack[-1][cmd.target.id] = value
            if isinstance(cmd, ast.Raise):  # raise x from y
                last_control_node = self.do_raise(cmd, last_control_node)
            if isinstance(cmd, ast.Assert):  # assert x,y
                last_control_node = self.do_assert(cmd, last_control_node)
            if isinstance(cmd, ast.If):
                last_control_node = self.do_if(cmd, last_control_node)
            if isinstance(cmd, ast.For):
                last_control_node = self.do_for(cmd, last_control_node)
            if isinstance(cmd, ast.While):
                last_control_node = self.do_while(cmd, last_control_node)
            if isinstance(cmd, ast.Break):
                last_control_node = self.do_break(cmd, last_control_node)
            if isinstance(cmd, ast.Continue):
                last_control_node = self.do_continue(cmd, last_control_node)
            if isinstance(cmd, ast.Return):
                last_control_node = self.do_return(cmd, last_control_node)
        print(self.table_stack)

        return last_control_node

    def do_while(self, cmd, last_control_node):
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
        self.loop_exit.append(loop_exit_node)
        self.G.edge(str(if_node), str(loop_exit_node), label="F", color="Red")
        self.G.edge(str(loop_exit_node), str(loop_begin_node), style="dashed")

        table_start_loop = self.make_while_dict()  # prepare the dict to the while loop
        self.table_stack.append(table_start_loop.copy())
        self.print_condition(cmd.test, if_node)  # print the while condition
        last_loop_node = self.do_body(cmd.body, begin_node)  # make the while body
        loop_end_node = begin_node
        if last_loop_node != -1:
            loop_end_node = self.add_node("|LoopEnd", color="Red", shape="box")
            self.G.edge(str(last_loop_node), str(loop_end_node), color="Red")
            self.G.edge(str(loop_end_node), str(loop_begin_node), color="Red")
        self.merge_while_dict(table_start_loop, end_before_loop_node, loop_end_node, loop_begin_node)
        self.loop_exit.pop()
        # self.table_stack.pop()
        # TODO: check this func
        return loop_exit_node

    def do_for(self, cmd, last_control_node):
        # print all For nodes and edges:
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

        loop_end_node = self.add_node("|LoopEnd", color="Red", shape="box")

        table_start_loop = self.make_while_dict()  # prepare the dict to the while loop
        self.table_stack.append(table_start_loop.copy())
        self.print_condition(cmd.test, if_node)  # print the while condition
        last_loop_node = self.do_body(cmd.body, begin_node)  # make the while body

        self.G.edge(str(last_loop_node), str(loop_end_node), color="Red")
        self.G.edge(str(loop_end_node), str(loop_begin_node), color="Red")
        self.merge_while_dict(table_start_loop, end_before_loop_node, loop_end_node, loop_begin_node)
        # self.table_stack.pop()
        # TODO: check this func
        return loop_exit_node

    # try push
    def do_if(self, cmd: ast.If, last_control_node):
        if_node = self.add_node("|If", color="Red", shape="box")
        self.G.edge(str(last_control_node), str(if_node), color="Red")
        self.print_condition(cmd.test, if_node)

        begin_true_node = self.add_node("|Begin", color="Red", shape="box")  # begin true
        self.G.edge(str(if_node), str(begin_true_node), label="T", color="Red")

        table_before_loop = self.table_stack[-1].copy()
        self.table_stack.append(table_before_loop.copy())
        last_true_node = self.do_body(cmd.body, begin_true_node)  # body true
        table_after_true = self.table_stack.pop()
        self.table_stack.append(table_before_loop.copy())
        last_false_node = begin_false_node = self.add_node("|Begin", color="Red", shape="box")  # begin false
        self.G.edge(str(if_node), str(begin_false_node), label="F", color="Red")
        if cmd.orelse:
            #print(cmd.orelse)

            last_false_node = self.do_body(cmd.orelse, begin_false_node)  # body false
        table_after_false = self.table_stack.pop()

        last_node, self.table_stack[-1] = self.do_merge(begin_false_node, last_true_node, last_false_node, table_after_true,
                                                        table_after_false, table_before_loop)  # merge paths and return

        return last_node

    def do_merge(self, begin_false_node, last_true_node, last_false_node, name_to_val_true: dict, name_to_val_false: dict, prev_dict):
        # make merge of paths in if cmd. then merge the dict
        # if node is none, we had return node in that case, so no need to end and merge this path
        end_true_node = -1
        end_false_node = last_false_node

        if last_true_node == -1:
            if last_false_node == -1:
                return -1, prev_dict
            else:
                if last_false_node != begin_false_node:
                    end_false_node = self.add_node("|End", color="Red", shape="box")
                    self.G.edge(str(last_false_node), str(end_false_node), color="Red")
                return end_false_node, name_to_val_false
        else:

            end_true_node = self.add_node("|End", color="Red", shape="box")
            self.G.edge(str(last_true_node), str(end_true_node), color="Red")
            if last_false_node == -1:
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

    def do_return(self, cmd: ast.Return, last_control_node):
        # print val to return then the node and edge
        val, last_control_node = self.get_val_and_print(cmd.value, last_control_node)
        ret_node = self.add_node("|Return", color="Red", shape="box")
        self.G.edge(str(val), str(ret_node), label="result", color="Turquoise")
        self.G.edge(str(last_control_node), str(ret_node), color="Red")
        return -1

    def do_break(self, cmd, last_control_node):
        # print the node and edge
        break_node = self.add_node("|Break", color="Red", shape="box")
        self.G.edge(str(last_control_node), str(break_node), color="Red")
        self.G.edge(str(break_node), str(self.loop_exit[-1]), color="Red")

        return -1

    def do_continue(self, cmd, last_control_node):
        # print the node and edge
        continue_node = self.add_node("|Continue", color="Red", shape="box")
        self.G.edge(str(last_control_node), str(continue_node), color="Red")
        return continue_node

    def do_raise(self, cmd, last_control_node):
        # print val to raise then the node and edge
        previous_node = last_control_node
        val, last_control_node = self.get_val_and_print(cmd.exc, last_control_node)
        raise_node = self.add_node("|Raise", color="Red", shape="box")
        self.G.edge(str(val), str(raise_node), label="exception", color="Turquoise")
        self.G.edge(str(previous_node), str(raise_node), color="Red")
        if cmd.cause is not None:
            val, last_control_node = self.get_val_and_print(cmd.cause, last_control_node)
            self.G.edge(str(val), str(raise_node), label="cause", color="Turquoise")
        return raise_node

    def do_assert(self, cmd, last_control_node):
        # print condition to assert then the node and edge
        previous_node = last_control_node
        assert_node = self.add_node("|Assert", color="Red", shape="box")
        self.print_condition(cmd.test, assert_node, last_control_node)
        self.G.edge(str(previous_node), str(assert_node), color="Red")
        if cmd.msg is not None:
            msg, last_control_node = self.get_val_and_print(cmd.msg, last_control_node)
            self.G.edge(str(msg), str(assert_node), label="msg", color="Turquoise")
        return assert_node

    def do_delete(self, cmd: ast.Delete, last_control_node):
        # print condition to assert then the node and edge
        delete_node = self.add_node("|Delete", color="Red", shape="box")
        self.G.edge(str(last_control_node), str(delete_node), color="Red")
        for target in cmd.targets:
            to_delete, last_control_node = self.get_val_and_print(target, last_control_node)
            self.G.edge(str(to_delete), str(delete_node), label="to_delete", color="Turquoise")
        return delete_node

    def get_val(self, value, last_control_node):
        # case variable node
        if isinstance(value, ast.Name):
            # print(self.table_stack)
            return self.table_stack[-1][value.id], last_control_node
        # case constant node
        elif isinstance(value, ast.Constant):
            return "Constant(" + str(value.value) + ", " + type_of_val(value.value) + ")", last_control_node
        elif isinstance(value, ast.JoinedStr):  # case f"sin({a}) is {sin(a):.3}"
            joinedstr_node = self.add_node("|JoinedStr ", color="Turquoise")
            for idx, val in enumerate(value.values):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.G.edge(str(node), str(joinedstr_node), color="Turquoise", label="str" + str(idx))
            return joinedstr_node, last_control_node
        elif isinstance(value, ast.List):  # case [1,2,3]
            list_node = self.add_node("|List ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.G.edge(str(node), str(list_node), color="Turquoise", label="element " + str(idx))
            return list_node, last_control_node
        elif isinstance(value, ast.Tuple):  # case (1,2,3)
            tuple_node = self.add_node("|Tuple ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.G.edge(str(node), str(tuple_node), color="Turquoise", label="element " + str(idx))
            return tuple_node, last_control_node
        elif isinstance(value, ast.Set):  # case {1,2,3}
            set_node = self.add_node("|Set ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.G.edge(str(node), str(set_node), color="Turquoise", label="element " + str(idx))
            return set_node, last_control_node
        elif isinstance(value, ast.Dict):  # case {k1:1,k2:2,k3:3}
            dict_node = self.add_node("|Dict ", color="Turquoise")
            for idx, key, val in enumerate(zip(value.keys, value.values)):
                key_node, last_control_node = self.get_val_and_print(key, last_control_node)
                val_node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.G.edge(str(key_node), str(dict_node), color="Turquoise", label="key " + str(idx))
                self.G.edge(str(val_node), str(dict_node), color="Turquoise", label="val " + str(idx))
            return dict_node, last_control_node
        elif isinstance(value, ast.Starred):  # case *b
            ref_node = self.add_node("|Reference ", color="Turquoise")
            node, last_control_node = self.get_val_and_print(value.value, last_control_node)
            self.G.edge(str(node), str(ref_node), color="Turquoise", label="ref")
            return ref_node, last_control_node
        elif isinstance(value, ast.Expr):  # case expr
            return self.get_val_and_print(value.value, last_control_node)
        elif isinstance(value, ast.UnaryOp):  # case +b/-b/not b/ ~b
            unary_op_node = self.add_node("|" + get_unop(value.op), color="Turquoise")
            node, last_control_node = self.get_val_and_print(value.operand, last_control_node)
            self.G.edge(str(node), str(unary_op_node), color="Turquoise", label="operand")
            return unary_op_node, last_control_node

        # case binop node
        elif isinstance(value, ast.BinOp):
            left, last_control_node = self.get_val_and_print(value.left, last_control_node)
            right, last_control_node = self.get_val_and_print(value.right, last_control_node)
            op_node = self.add_node("|" + get_binop(value.op), color="Turquoise")
            self.G.edge(str(left), str(op_node), color="Turquoise", label="x")
            self.G.edge(str(right), str(op_node), color="Turquoise", label="y")
            return op_node, last_control_node

        # case relop node
        elif isinstance(value, ast.Compare):
            return self.do_compare(value, last_control_node, True)

        # case func
        elif isinstance(value, ast.Call):
            args_count = 0
            func_node = self.add_node("|MethodCallTarget", shape="box")
            if isinstance(value.func, ast.Name):  # case reg func
                name = value.func.id
            elif isinstance(value.func, ast.Attribute):  # case class method func
                object = value.func.value
                name = "Class." + value.func.attr
                object_node, last_control_node = self.get_val_and_print(object, last_control_node)
                self.G.edge(str(object_node), str(func_node), label="arg[" + str(args_count) + "]", color="Turquoise")
                args_count += 1
            call_node = self.add_node("|Call " + name, color="Red", shape="box")
            self.G.edge(str(call_node), str(func_node), style="dashed")
            self.G.edge(str(last_control_node), str(call_node), color="Red")
            last_control_node = call_node

            for arg in value.args:
                val_node, last_control_node = self.get_val_and_print(arg, last_control_node)
                self.G.edge(str(val_node), str(func_node), label="arg[" + str(args_count) + "]", color="Turquoise")
                args_count += 1
            if isinstance(value.func, ast.Attribute):
                return last_control_node, last_control_node
            return last_control_node, last_control_node

        elif isinstance(value, ast.IfExp):  # case a if b else c
            if_exp_node = self.add_node("|If Exp", color="Turquoise")
            self.print_condition(value.test, if_exp_node, last_control_node)
            then_node, last_control_node = self.get_val_and_print(value.body, last_control_node)
            else_node, last_control_node = self.get_val_and_print(value.orelse, last_control_node)
            self.G.edge(str(then_node), str(if_exp_node), color="Turquoise", label="then")
            self.G.edge(str(else_node), str(if_exp_node), color="Turquoise", label="else")
            return if_exp_node, last_control_node

        elif isinstance(value, ast.Attribute):  # case snake.colour
            assert value.ctx == ast.Load(), "store and del attribute not implemented"
            previous_node = last_control_node
            obj_node, last_control_node = self.get_val_and_print(value.value, last_control_node)
            att_node, last_control_node = self.get_val_and_print(value.attr, last_control_node)
            load_node = self.add_node("|Load Attribute", color="Red", shape="Box")
            self.G.edge(str(previous_node), str(load_node), color="Red")
            self.G.edge(str(obj_node), str(load_node), color="Turquoise", label="object")
            self.G.edge(str(att_node), str(load_node), color="Turquoise", label="attribute")
            return load_node, load_node

        elif isinstance(value, ast.NamedExpr):  # case x:=4
            assert False, "NamedExpr not implemented"

        elif isinstance(value, ast.Subscript):  # case l[1:2,3]
            assert value.ctx == ast.Load(), "store and del subscript not implemented"
            previous_node = last_control_node
            obj_node, last_control_node = self.get_val_and_print(value.value, last_control_node)

            load_node = self.add_node("|Load indices", color="Red", shape="Box")
            self.G.edge(str(previous_node), str(load_node), color="Red")
            self.G.edge(str(obj_node), str(load_node), color="Turquoise", label="object")
            for idx in value.slice:
                index_node, last_control_node = self.get_val_and_print(idx, last_control_node)
                self.G.edge(str(index_node), str(load_node), color="Turquoise", label="index")
            return load_node, load_node
        elif isinstance(value, ast.Slice):  # case l[1:3]
            range_node = self.add_node("|indices range", color="Turquoise")
            lower_node, last_control_node = self.get_val_and_print(value.lower, last_control_node)
            upper_node, last_control_node = self.get_val_and_print(value.upper, last_control_node)
            self.G.edge(str(lower_node), str(range_node), color="Turquoise", label="lower")
            self.G.edge(str(upper_node), str(range_node), color="Turquoise", label="upper")
            if value.step is not None:
                step_node, last_control_node = self.get_val_and_print(value.step, last_control_node)
                self.G.edge(str(step_node), str(range_node), color="Turquoise", label="index")
            return range_node, last_control_node
        elif isinstance(value, ast.Index):
            return self.get_val_and_print(value.value, last_control_node)
        # TODO: add more cases

    def print_value(self, value):
        if type(value) is tuple:  # phi case
            phi_node = node = self.add_node("|phi", shape="box")
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

    def get_val_and_print(self, object, last_control_node):
        object_node, last_control_node = self.get_val(object, last_control_node)
        if type(object_node) != int:
            object_node = self.print_value(object_node)
        return object_node, last_control_node

    def add_node(self, text, color="black", shape="ellipse"):
        self.G.node(str(self.counter), str(self.counter) + text, color=color, shape=shape)
        node = self.counter
        self.counter += 1
        return node

    def do_compare(self, compare: ast.Compare, last_control_node, print_val=False):
        sum_node = None
        left, last_control_node = self.get_val_and_print(compare.left, last_control_node)
        rights = compare.comparators
        ops = get_ops(compare.ops)
        conditions = []
        for val, op in zip(rights, ops):
            right, last_control_node = self.get_val_and_print(val, last_control_node)
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

    def print_condition(self, test, if_node, label="condition"):
        # cases like "if condition:"
        if isinstance(test, ast.Name):
            to_compare = ast.Compare(left=test, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)])
            comp_node, _ = self.do_compare(to_compare, if_node)

        # cases like "if cond1 > cond2:"
        elif isinstance(test, ast.Compare):
            to_compare = test
            comp_node, _ = self.do_compare(to_compare, if_node)

        # cases like "if cond1 or cond2:"
        elif isinstance(test, ast.BoolOp):
            if isinstance(test.op, ast.And):
                boolop = "|and"
            else:  # or
                boolop = "|or"

            comp_node = self.add_node(boolop, color="Turquoise", shape="ellipse")
            self.print_condition(test.values[0], comp_node, label="first cond")
            self.print_condition(test.values[1], comp_node, label="second cond")

        self.G.edge(str(comp_node), str(if_node), label=label, color="Turquoise")

        # TODO: add more if cases

    def make_while_dict(self):
        new_dict = {}
        used_keys = []
        for key in self.table_stack[-1]:
            # if key not in used_keys:
            #    key_in_val = [key]

            # new_dict[key] = self.counter
            # for next_key in orig_dict:

            #   if key != next_key and orig_dict[key] == orig_dict[next_key]:
            #      key_in_val.append(next_key)
            #     new_dict[next_key] = self.counter
            new_dict[key] = self.counter
            self.counter += 1
            # used_keys += key_in_val
        return new_dict

    def merge_while_dict(self, dict_before, before_loop_node, end_loop_node, loop_begin_node):
        # print(self.table_stack)
        dict_after_loop = self.table_stack.pop()
        pre_dict = self.table_stack.pop()
        # print("dict_before", dict_before)
        # print("dict_after_loop", dict_after_loop)
        # print("pre_dict", pre_dict)
        # print("table_stack", self.table_stack)
        new_dict = {}
        for key in dict_before:
            if dict_before[key] == dict_after_loop[key]:
                new_dict[key] = pre_dict[key]
            else:
                phi_node = dict_before[key]
                val_before_node = self.print_value(pre_dict[key])
                self.G.node(str(phi_node), str(phi_node) + "|phi", shape="box")
                self.G.edge(str(dict_after_loop[key]), str(phi_node), label="from " + str(end_loop_node),
                            color="Turquoise")
                self.G.edge(str(val_before_node), str(phi_node), label="from " + str(before_loop_node),
                            color="Turquoise")
                self.G.edge(str(phi_node), str(loop_begin_node), style="dashed")
                new_dict[key] = phi_node
        # print("new_dict", new_dict)
        self.table_stack.append(new_dict)
