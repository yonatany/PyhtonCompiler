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

    def print_pdf(self, filename=""):
        self.G.render(filename)
        # print(self.G)

    def do_func(self, node: ast.FunctionDef):
        self.table_stack.append({})
        last_control_node = self.add_node("|StartNode", color="Red", shape="box")
        parameter_counter = 0
        for arg in node.args.args:
            self.table_stack[-1][arg.arg] = "Parameter(" + str(parameter_counter) + ")"
            parameter_counter += 1
        last_control_node = self.do_body(node.body, last_control_node)

    def do_body(self, body, last_control_node):
        # print(self.table_stack)
        for cmd in body:
            if isinstance(cmd, ast.Assign):  # a = 1
                value, last_control_node = self.get_val(cmd.value, last_control_node)
                for lval in cmd.targets:
                    # assert isinstance(lval, ast.Name), "not implemented"
                    if isinstance(lval, ast.Name):
                        self.table_stack[-1][lval.id] = value
                    else:
                        value, last_control_node = self.get_val_and_print(lval, last_control_node)
                        print(lval)
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
        #            if isinstance(cmd, ast.Match):
        #                last_control_node = self.do_match(cmd, last_control_node)
        # print(self.table_stack)

        return last_control_node

    def do_while(self, cmd, last_control_node):
        # print all while nodes and edges:
        previous_node = last_control_node

        loop_begin_node = last_control_node = self.add_node("|LoopBegin", color="Red", shape="box")

        self.add_edge(previous_node, loop_begin_node, color="Red")

        if_node = self.add_node("|If", color="Red", shape="box")
        self.add_edge(last_control_node, if_node, color="Red")

        begin_node = self.add_node("|Begin", color="Red", shape="box")
        self.add_edge(if_node, begin_node, color="Red", label="T")

        loop_exit_node = self.add_node("|LoopExit", color="Red", shape="box")
        self.loop_exit.append(loop_exit_node)
        self.add_edge(if_node, loop_exit_node, color="Red", label="F")
        self.add_edge(loop_exit_node, loop_begin_node)

        table_start_loop = self.make_while_dict()  # prepare the dict to the while loop
        self.table_stack.append(table_start_loop.copy())
        self.print_condition(cmd.test, if_node)  # print the while condition
        last_loop_node = self.do_body(cmd.body, begin_node)  # make the while body
        loop_end_node = begin_node
        if last_loop_node != -1:
            loop_end_node = self.add_node("|LoopEnd", color="Red", shape="box")
            self.add_edge(last_loop_node, loop_end_node, color="Red")
            self.add_edge(loop_end_node, loop_begin_node, color="Red")
        self.merge_while_dict(table_start_loop, previous_node, loop_end_node, loop_begin_node)
        self.loop_exit.pop()
        # self.table_stack.pop()
        # TODO: check this func
        return loop_exit_node

    def do_for(self, cmd: ast.For, last_control_node):
        # print all For nodes and edges:
        end_before_loop_node = self.add_node("|End", color="Red", shape="box")
        self.add_edge(last_control_node, end_before_loop_node, color="Red")

        loop_begin_node = last_control_node = self.add_node("|ForLoopBegin", color="Red", shape="box")
        self.add_edge(end_before_loop_node, loop_begin_node, color="Red")

        iter_node, last_control_node = self.get_val_and_print(cmd.iter, last_control_node)

        loop_exit_node = self.add_node("|LoopExit", color="Red", shape="box")
        self.add_edge(loop_exit_node, loop_begin_node, color="Red")

        loop_end_node = self.add_node("|LoopEnd", color="Red", shape="box")
        self.table_stack[-1][cmd.target.id] = iter_node

        table_start_loop = self.make_while_dict()  # prepare the dict to the while loop
        self.table_stack.append(table_start_loop.copy())
        last_loop_node = self.do_body(cmd.body, loop_begin_node)  # make the while body

        self.add_edge(last_loop_node, loop_end_node, color="Red")
        self.add_edge(loop_end_node, loop_begin_node, color="Red")
        self.merge_while_dict(table_start_loop, end_before_loop_node, loop_end_node, loop_begin_node)
        # self.table_stack.pop()
        # TODO: check this func
        return loop_exit_node

    # try push
    def do_if(self, cmd: ast.If, last_control_node):
        if_node = self.add_node("|If", color="Red", shape="box")
        self.add_edge(last_control_node, if_node, color="Red")
        self.print_condition(cmd.test, if_node)

        begin_true_node = self.add_node("|Begin", color="Red", shape="box")  # begin true
        self.add_edge(if_node, begin_true_node, color="Red", label="T")

        table_before_loop = self.table_stack[-1].copy()
        self.table_stack.append(table_before_loop.copy())
        last_true_node = self.do_body(cmd.body, begin_true_node)  # body true
        table_after_true = self.table_stack.pop()
        self.table_stack.append(table_before_loop.copy())
        last_false_node = begin_false_node = self.add_node("|Begin", color="Red", shape="box")  # begin false
        self.add_edge(if_node, begin_false_node, color="Red", label="F")
        if cmd.orelse:
            last_false_node = self.do_body(cmd.orelse, begin_false_node)  # body false
        table_after_false = self.table_stack.pop()

        last_node, self.table_stack[-1] = self.do_merge(begin_false_node, last_true_node, last_false_node,
                                                        table_after_true,
                                                        table_after_false, table_before_loop)  # merge paths and return

        return last_node

    def do_match(self, cmd, last_control_node):
        raise "not_implemnted"
    #        match_node = self.add_node("|Pattern Match", color="Red", shape="box")
    #        self.G.edge(str(last_control_node), str(match_node), color="Red")
    #        subject_node, last_control_node = self.get_val_and_print(cmd.subject, match_node)
    #        self.G.edge(str(subject_node), str(match_node), color="Turquoise", label="subject")
    #
    #        table_before_match = self.table_stack[-1].copy()
    #
    #        begin_case_nodes = []
    #        for case in cmd.cases:
    #            print(case)
    #            self.table_stack.append(table_before_match.copy())
    #            begin_case_nodes.append(self.add_node("|Begin", color="Red", shape="box"))  # begin case
    #            self.do_match_case(case.body, begin_case_nodes[-1], match_node)
    #            self.G.edge(str(match_node), str(begin_case_nodes[-1]), label="T", color="Red")
    #
    #        table_before_loop = self.table_stack[-1].copy()
    #        self.table_stack.append(table_before_loop.copy())
    #        last_true_node = self.do_body(cmd.body, begin_case_nodes[-1])  # body true
    #        table_after_true = self.table_stack.pop()
    #        self.table_stack.append(table_before_loop.copy())

    # last_node, self.table_stack[-1] = self.do_merge(begin_false_node, last_true_node, last_false_node, table_after_true, table_after_false, table_before_loop)  # merge paths and return

    #        return last_true_node

    # def do_match_case(self, case, param, match_node):
    # if isinstance(case, )

    def do_merge(self, begin_false_node, last_true_node, last_false_node, name_to_val_true: dict,
                 name_to_val_false: dict, prev_dict):
        # make merge of paths in if cmd. then merge the dict
        # if node is -1, we had return or break node in that case, so no need to end and merge this path
        end_false_node = last_false_node

        if last_true_node == -1:
            if last_false_node == -1:
                return -1, prev_dict
            else:
                if last_false_node != begin_false_node:
                    end_false_node = self.add_node("|End", color="Red", shape="box")
                    self.add_edge(last_false_node, end_false_node, color="Red")

                return end_false_node, name_to_val_false
        else:

            end_true_node = self.add_node("|End", color="Red", shape="box")
            self.add_edge(last_true_node, end_true_node, color="Red")
            if last_false_node == -1:
                return end_true_node, name_to_val_true

            end_false_node = self.add_node("|End", color="Red", shape="box")
            self.add_edge(last_false_node, end_false_node, color="Red")

            # merge paths
            merge_node = self.add_node("|Merge", color="Red", shape="box")
            self.add_edge(end_true_node, merge_node, color="Red")
            self.add_edge(end_false_node, merge_node, color="Red")
            # merge dicts
            name_to_val = merge_dict(name_to_val_true, name_to_val_false, end_true_node, end_false_node, merge_node)
            return merge_node, name_to_val

    def do_return(self, cmd: ast.Return, last_control_node):
        # print val to return then the node and edge
        ret_node = self.add_node("|Return", color="Red", shape="box")

        if cmd.value is not None:
            val, last_control_node = self.get_val_and_print(cmd.value, last_control_node)
            self.add_edge(val, ret_node, label="result", color="Red")

        self.add_edge(last_control_node, ret_node, color="Red")
        return -1

    def do_break(self, cmd, last_control_node):
        # print the node and edge
        break_node = self.add_node("|Break", color="Red", shape="box")
        self.add_edge(last_control_node, break_node, color="Red")
        self.add_edge(break_node, self.loop_exit[-1], color="Red")
        return -1

    def do_continue(self, cmd, last_control_node):
        # print the node and edge
        continue_node = self.add_node("|Continue", color="Red", shape="box")
        self.add_edge(last_control_node, continue_node, color="Red")
        return continue_node

    def do_raise(self, cmd, last_control_node):
        # print val to raise then the node and edge
        previous_node = last_control_node
        val, last_control_node = self.get_val_and_print(cmd.exc, last_control_node)
        raise_node = self.add_node("|Raise", color="Red", shape="Turquoise")
        self.add_edge(val, raise_node, label="exception", color="Turquoise")
        self.add_edge(previous_node, raise_node, color="Red")

        if cmd.cause is not None:
            val, last_control_node = self.get_val_and_print(cmd.cause, last_control_node)
            self.add_edge(val, raise_node, label="cause", color="Turquoise")
        return raise_node

    def do_assert(self, cmd, last_control_node):
        # print condition to assert then the node and edge
        previous_node = last_control_node
        assert_node = self.add_node("|Assert", color="Red", shape="box")
        self.print_condition(cmd.test, assert_node, last_control_node)
        self.add_edge(previous_node, assert_node, color="Red")
        if cmd.msg is not None:
            msg, last_control_node = self.get_val_and_print(cmd.msg, last_control_node)
            self.add_edge(msg, assert_node, label="msg", color="Turquoise")
        return assert_node

    def do_delete(self, cmd: ast.Delete, last_control_node):
        # print condition to assert then the node and edge
        delete_node = self.add_node("|Delete", color="Red", shape="box")
        for target in cmd.targets:
            to_delete, last_control_node = self.get_val_and_print(target, last_control_node)
            self.add_edge(to_delete, delete_node, label="to_delete", color="Turquoise")
        self.add_edge(last_control_node, delete_node, color="Red")
        return delete_node

    def get_val(self, value, last_control_node):
        # case variable node
        if isinstance(value, ast.Name):
            # print(self.table_stack)
            return self.table_stack[-1][value.id], last_control_node
        # case constant node
        elif isinstance(value, str):
            return "Constant(" + str(value) + ", str)", last_control_node
        elif isinstance(value, ast.Constant):
            return "Constant(" + str(value.value) + ", " + type_of_val(value.value) + ")", last_control_node
        elif isinstance(value, ast.JoinedStr):  # case f"sin({a}) is {sin(a):.3}"
            joinedstr_node = self.add_node("|JoinedStr ", color="Turquoise")
            for idx, val in enumerate(value.values):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node, joinedstr_node, color="Turquoise", label="str" + str(idx))
            return joinedstr_node, last_control_node
        elif isinstance(value, ast.List):  # case [1,2,3]
            list_node = self.add_node("|List ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node, list_node, color="Turquoise", label="element " + str(idx))
            return list_node, last_control_node
        elif isinstance(value, ast.Tuple):  # case (1,2,3)
            tuple_node = self.add_node("|Tuple ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node, tuple_node, color="Turquoise", label="element " + str(idx))
            return tuple_node, last_control_node
        elif isinstance(value, ast.Set):  # case {1,2,3}
            set_node = self.add_node("|Set ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node, set_node, color="Turquoise", label="element " + str(idx))
            return set_node, last_control_node
        elif isinstance(value, ast.Dict):  # case {k1:1,k2:2,k3:3}
            dict_node = self.add_node("|Dict ", color="Turquoise")
            for idx, key, val in enumerate(zip(value.keys, value.values)):
                key_node, last_control_node = self.get_val_and_print(key, last_control_node)
                val_node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(key_node, dict_node, color="Turquoise", label="key " + str(idx))
                self.add_edge(val_node, dict_node, color="Turquoise", label="val " + str(idx))
            return dict_node, last_control_node
        elif isinstance(value, ast.Starred):  # case *b
            ref_node = self.add_node("|Reference ", color="Turquoise")
            node, last_control_node = self.get_val_and_print(value.value, last_control_node)
            self.add_edge(node, ref_node, color="Turquoise", label="ref")
            return ref_node, last_control_node
        elif isinstance(value, ast.Expr):  # case expr
            return self.get_val_and_print(value.value, last_control_node)
        elif isinstance(value, ast.UnaryOp):  # case +b/-b/not b/ ~b
            unary_op_node = self.add_node("|" + get_unop(value.op), color="Turquoise")
            node, last_control_node = self.get_val_and_print(value.operand, last_control_node)
            self.add_edge(node, unary_op_node, color="Turquoise", label="operand")
            return unary_op_node, last_control_node

        # case binop node
        elif isinstance(value, ast.BinOp):
            left, last_control_node = self.get_val_and_print(value.left, last_control_node)
            right, last_control_node = self.get_val_and_print(value.right, last_control_node)
            op_node = self.add_node("|" + get_binop(value.op), color="Turquoise")
            self.add_edge(left, op_node, color="Turquoise", label="x")
            self.add_edge(right, op_node, color="Turquoise", label="y")
            return op_node, last_control_node

        # case relop node
        elif isinstance(value, ast.Compare):
            return self.do_compare(value, last_control_node, True)
        # case boolop node
        elif isinstance(value, ast.BoolOp):

            op_node = self.add_node("|" + get_boolop(value.op), color="Turquoise")
            for idx, val in enumerate(value.values):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node, op_node, color="Turquoise", label="x" + str(idx))

            return op_node, last_control_node
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
                self.add_edge(object_node, func_node, color="Turquoise", label="arg[" + str(args_count) + "]")
                args_count += 1
            call_node = self.add_node("|Call " + name, color="Red", shape="box")
            self.add_edge(call_node, func_node, color="Red")
            self.add_edge(last_control_node, call_node)
            last_control_node = call_node

            for arg in value.args:
                val_node, last_control_node = self.get_val_and_print(arg, last_control_node)
                self.add_edge(val_node, func_node, color="Turquoise", label="arg[" + str(args_count) + "]")
                args_count += 1
            if isinstance(value.func, ast.Attribute):
                return last_control_node, last_control_node
            return last_control_node, last_control_node

        elif isinstance(value, ast.IfExp):  # case a if b else c
            if_exp_node = self.add_node("|If Exp", color="Turquoise")
            self.print_condition(value.test, if_exp_node, last_control_node)
            then_node, last_control_node = self.get_val_and_print(value.body, last_control_node)
            else_node, last_control_node = self.get_val_and_print(value.orelse, last_control_node)
            self.add_edge(then_node, if_exp_node, color="Turquoise", label="then")
            self.add_edge(else_node, if_exp_node, color="Turquoise", label="else")
            return if_exp_node, last_control_node

        elif isinstance(value, ast.Attribute):  # case snake.colour
            assert isinstance(value.ctx, ast.Load), "store and del attribute not implemented"
            previous_node = last_control_node
            obj_node, last_control_node = self.get_val_and_print(value.value, last_control_node)
            att_node, last_control_node = self.get_val_and_print(value.attr, last_control_node)
            load_node = self.add_node("|Load Attribute", color="Red", shape="Box")
            self.add_edge(previous_node, load_node, color="Red")
            self.add_edge(obj_node, load_node, color="Turquoise", label="object")
            self.add_edge(att_node, load_node, color="Turquoise", label="attribute")
            return load_node, load_node

        elif isinstance(value, ast.NamedExpr):  # case x:=4
            assert False, "NamedExpr not implemented"

        elif isinstance(value, ast.Subscript):  # case l[1:2,3]
            # assert isinstance(value.ctx, ast.Load), str(value.value.id)+str(value.slice.value.id)+str(value.ctx)+" store and del subscript not implemented"

            previous_node = last_control_node
            obj_node, last_control_node = self.get_val_and_print(value.value, last_control_node)
            text = "|Load indices"
            if isinstance(value.ctx, ast.Store):
                text = "|Store indices"
            elif isinstance(value.ctx, ast.Del):
                text = "|Del indices"
            load_node = self.add_node(text, color="Red", shape="Box")
            self.add_edge(previous_node, load_node, color="Red")
            self.add_edge(obj_node, load_node, color="Turquoise", label="object")
            if isinstance(value.slice, ast.Index):
                idx = value.slice
                index_node, last_control_node = self.get_val_and_print(idx, last_control_node)
                self.add_edge(index_node, load_node, color="Turquoise", label="index")
            else:
                for idx in value.slice:
                    index_node, last_control_node = self.get_val_and_print(idx, last_control_node)
                    self.add_edge(index_node, load_node, color="Turquoise", label="index")
            return load_node, load_node
        elif isinstance(value, ast.Slice):  # case l[1:3]
            range_node = self.add_node("|indices range", color="Turquoise")
            lower_node, last_control_node = self.get_val_and_print(value.lower, last_control_node)
            upper_node, last_control_node = self.get_val_and_print(value.upper, last_control_node)
            self.add_edge(lower_node, range_node, color="Turquoise", label="lower")
            self.add_edge(upper_node, range_node, color="Turquoise", label="upper")
            if value.step is not None:
                step_node, last_control_node = self.get_val_and_print(value.step, last_control_node)
                self.add_edge(step_node, range_node, color="Turquoise", label="index")
            return range_node, last_control_node
        elif isinstance(value, ast.Index):

            return self.get_val_and_print(value.value, last_control_node)
        # TODO: add more cases

    def print_value(self, value):
        if type(value) is tuple:  # phi case
            phi_node = node = self.add_node("|phi", shape="box")
            merge_node = value[1]
            self.add_edge(phi_node, merge_node)
            for val, node_num in value[0]:
                val_node = self.print_value(val)
                self.add_edge(val_node, phi_node, label="from " + str(node_num), color="Turquoise")
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
        # print(object, type(object))
        object_node, last_control_node = self.get_val(object, last_control_node)
        if type(object_node) != int:
            object_node = self.print_value(object_node)
        return object_node, last_control_node

    def add_node(self, text, color="black", shape="ellipse"):
        # print(text)
        self.G.node(str(self.counter), str(self.counter) + text, color=color, shape=shape)
        node = self.counter
        self.counter += 1
        return node

    def add_edge(self, node1, node2, label="", color="Black"):
        # print(text)
        style = ""
        att = ""
        if color == "Red":
            att = "Control"
        elif color == "Turquoise":
            att = "Data"
        else:  # black
            style = "dashed"
        self.G.edge(str(node1), str(node2), label=label, color=color, att=att, style=style)
        return

    def do_compare(self, compare: ast.Compare, last_control_node, print_val=False):
        sum_node = None
        left, last_control_node = self.get_val_and_print(compare.left, last_control_node)
        rights = compare.comparators
        ops = get_ops(compare.ops)
        conditions = []
        for val, op in zip(rights, ops):
            right, last_control_node = self.get_val_and_print(val, last_control_node)
            comp_node = self.add_node("|" + op, color="Turquoise", shape="diamond")
            self.add_edge(left, comp_node, label="x", color="Turquoise")
            self.add_edge(right, comp_node, label="y", color="Turquoise")
            if print_val:
                zero = self.print_value("Constant(" + str(0) + ", " + type_of_val(0) + ")")
                one = self.print_value("Constant(" + str(1) + ", " + type_of_val(1) + ")")
                conditional_node = self.add_node("|Conditional", color="Turquoise", shape="diamond")
                self.add_edge(comp_node, conditional_node, label="?", color="Turquoise")
                self.add_edge(one, conditional_node, label="trueValue", color="Turquoise")
                self.add_edge(zero, conditional_node, label="falseValue", color="Turquoise")
                conditions.append(conditional_node)
                sum_node = conditional_node
            else:
                conditions.append(comp_node)
                sum_node = comp_node
            left = right
        if len(conditions) > 1:
            sum_node = self.add_node("|&", color="Turquoise", shape="diamond")
            for cond in conditions:
                self.add_edge(cond, sum_node, color="Turquoise")

        return sum_node, last_control_node

    def print_condition(self, test, if_node, label="condition"):
        # cases like "if condition:"
        if isinstance(test, ast.Name) or isinstance(test, ast.Constant):
            to_compare = ast.Compare(left=test, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)])
            comp_node, _ = self.do_compare(to_compare, if_node)

        # cases like "if True:"
        # elif isinstance(test, ast.Constant):
        #    to_compare = ast.Compare(left=test, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)])
        #    comp_node, _ = self.do_compare(to_compare, if_node)

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

        # print(test)
        self.add_edge(comp_node, if_node, label=label, color="Turquoise")

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
                node_1 = self.print_value(dict_after_loop[key])
                node_2 = self.print_value(val_before_node)
                self.add_edge(node_1, phi_node, label="from " + str(end_loop_node), color="Turquoise")
                self.add_edge(node_2, phi_node, label="from " + str(before_loop_node), color="Turquoise")
                self.add_edge(phi_node, loop_begin_node, label="from " + str(end_loop_node))

                new_dict[key] = phi_node
        # print("new_dict", new_dict)
        self.table_stack.append(new_dict)
