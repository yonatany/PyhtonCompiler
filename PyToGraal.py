import ast
import inspect

from typing import Tuple

from helpers import *
from graphviz import Digraph


class VarNode:

    def __init__(self, name=None, ann=None):
        self.name = name
        self.ann = ann


def merge_dict(true_dict, false_dict, true_end_node, false_end_node, merge_node):
    new_dict = {}
    for key in true_dict:
        if key in false_dict:
            if true_dict[key].name == false_dict[key].name:
                new_dict[key] = true_dict[key]
            else:
                new_dict[key] = VarNode(name=([(true_dict[key], true_end_node),
                                               (false_dict[key], false_end_node)], merge_node))
        else:
            new_dict[key] = VarNode(name=([(true_dict[key], true_end_node), ("None", false_end_node)], merge_node))
    for key in false_dict:
        if key not in new_dict:
            new_dict[key] = VarNode(name=([(false_dict[key], false_end_node), ("None", true_end_node)], merge_node))
    return new_dict


class PyToGraal:

    def __init__(self, func):
        self.counter = 0
        # self.board = array()
        self.func = func
        self.G = Digraph()
        self.name_to_node = {}
        self.table_stack = []
        self.loop_exit = []
        self.for_index = 0

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
            name = "Parameter(" + str(parameter_counter) + ")"
            ann = None
            if arg.annotation is not None:
                ann = arg.annotation
            self.table_stack[-1][arg.arg] = VarNode(name=name, ann=ann)
            parameter_counter += 1
        last_control_node = self.do_body(node.body, last_control_node)

    def do_body(self, body, last_control_node):
        for cmd in body:
            if isinstance(cmd, ast.Assign):  # a = 1
                value, last_control_node = self.get_val(cmd.value, last_control_node)
                for lval in cmd.targets:
                    # assert isinstance(lval, ast.Name), "not implemented"
                    if isinstance(lval, ast.Name):
                        self.table_stack[-1][lval.id] = VarNode(name=value, ann=None)
                    else:
                        value, last_control_node = self.get_val_and_print(lval, last_control_node)
                    # raise NotImplementedError
            if isinstance(cmd, ast.AnnAssign):  # a:int = 1
                assert isinstance(cmd.target, ast.Name), "not implemented"
                value, last_control_node = self.get_val(cmd.value, last_control_node)
                ann = None
                if cmd.annotation is not None:
                    ann = cmd.annotation
                self.table_stack[-1][cmd.target.id] = VarNode(name=value, ann=ann)
            if isinstance(cmd, ast.AugAssign):  # a += 1
                assert isinstance(cmd.target, ast.Name), "not implemented"
                value, last_control_node = self.get_val(ast.BinOp(left=cmd.target, op=cmd.op, right=cmd.value),
                                                        last_control_node)
                self.table_stack[-1][cmd.target.id] = VarNode(name=value, ann=None)
            if isinstance(cmd, ast.Raise):  # raise x from y
                last_control_node = self.do_raise(cmd, last_control_node)
            if isinstance(cmd, ast.Assert):  # assert x,y
                last_control_node = self.do_assert(cmd, last_control_node)
            if isinstance(cmd, ast.Pass):
                self.do_pass(cmd, last_control_node)
            if isinstance(cmd, ast.Import):
                last_control_node = self.do_import(cmd, last_control_node)
            if isinstance(cmd, ast.ImportFrom):
                last_control_node = self.do_importfrom(cmd, last_control_node)
            if isinstance(cmd, ast.Try):
                last_control_node = self.do_try(cmd, last_control_node)
            if isinstance(cmd, ast.With):
                last_control_node = self.do_with(cmd, last_control_node)
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
            if isinstance(cmd, ast.Yield):
                last_control_node = self.do_yield(cmd, last_control_node)
            if isinstance(cmd, ast.ListComp):
                last_control_node = self.do_list_comp(cmd, last_control_node)
            # if isinstance(cmd, ast.Match):
            #    last_control_node = self.do_match(cmd, last_control_node)

        return last_control_node

    def do_while(self, cmd, last_control_node, over_dict=None):
        # print all while nodes and edges:
        previous_node = last_control_node

        loop_begin_node = last_control_node = self.add_node("|LoopBegin", color="Red", shape="box")

        self.add_edge(previous_node, loop_begin_node, color="Red")

        if_node = self.add_node("|If", color="Red", shape="box")

        begin_node = self.add_node("|Begin", color="Red", shape="box")
        self.add_edge(if_node, begin_node, color="Red", label="T")

        loop_exit_node = self.add_node("|LoopExit", color="Red", shape="box")
        self.loop_exit.append(loop_exit_node)
        self.add_edge(if_node, loop_exit_node, color="Red", label="F")
        self.add_edge(loop_exit_node, loop_begin_node)
        table_start_loop = self.make_while_dict(over_dict)  # prepare the dict to the while loop
        self.table_stack.append(table_start_loop.copy())
        last_control_node = self.print_condition(cmd.test, if_node, last_control_node)  # print the while condition
        self.add_edge(last_control_node, if_node, color="Red")

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

    def do_for(self, cmd: ast.For, last_control_node, over_dict=None):
        # convert for to while:
        # For x in list:
        #   Body
        #
        # =>
        #
        # i = 0;
        # While i < list.len:
        #   x = list[i]
        #   Body
        #   i += 1

        for_idx_name = "for_idx_" + str(self.for_index)
        self.for_index += 1
        value, last_control_node = self.get_val(ast.Constant(value=0), last_control_node)
        lst_node, last_control_node = self.get_val_and_print(cmd.iter, last_control_node)

        self.table_stack[-1][for_idx_name] = value
        for_test = ast.Compare(left=ast.Name(id=for_idx_name), ops=[ast.Lt()],
                               comparators=[ast.Call(func=ast.Name(id='len'), args=[cmd.iter])])
        for_init = [ast.Assign(targets=[cmd.target],
                               value=ast.Subscript(value=cmd.iter, slice=ast.Index(ast.Name(id=for_idx_name)),
                                                   ctx=ast.Load()))]
        for_end = [ast.AugAssign(target=ast.Name(id=for_idx_name), op=ast.Add(), value=ast.Constant(value=1))]
        for_body = for_init + cmd.body + for_end
        while_cmd = ast.While(test=for_test, body=for_body, orelse=cmd.orelse)
        if over_dict is None:
            over_dict = {}

        over_dict[cmd.iter.id] = lst_node

        return self.do_while(while_cmd, last_control_node, over_dict=over_dict)

    #
    def do_list_comp(self, cmd, last_control_node):
        # convert list_comp to for:
        # [f(x) for x in lst]
        #
        # =>
        #
        # New_lst = []
        # For x in lst:
        #   New_lst.append(f(x))
        # Return new_lst

        for generator in cmd.generators:
            previous_node = last_control_node
            last_control_node = lst_node = self.add_node("|NewList", color="Red")
            self.add_edge(previous_node, lst_node, color="Red")
            list_comp_name = "list_comp_" + str(self.for_index)
            self.for_index += 1
            # value, last_control_node = self.get_val(ast.List(elts=[]), last_control_node)
            self.table_stack[-1][list_comp_name] = VarNode(name=lst_node, ann=None)
            for_body = [ast.Call(func=ast.Attribute(value=ast.Name(id=list_comp_name), attr='append'), args=[cmd.elt])]
            for_cmd = ast.For(target=generator.target, iter=generator.iter, body=for_body, orelse=[])

            return VarNode(name=lst_node), self.do_for(for_cmd, last_control_node,
                                                       over_dict={list_comp_name: VarNode(name=lst_node, ann=None)})

    def do_if(self, cmd: ast.If, last_control_node):
        if_node = self.add_node("|If", color="Red", shape="box")
        last_control_node = self.print_condition(cmd.test, if_node, last_control_node)
        self.add_edge(last_control_node, if_node, color="Red")

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

    def do_call(self, cmd, last_control_node):
        args_count = 0
        func_node = self.add_node("|MethodCallTarget", shape="box")
        if isinstance(cmd.func, ast.Name):  # case reg func
            name = cmd.func.id
        elif isinstance(cmd.func, ast.Attribute):  # case class method func
            object = cmd.func.value
            name = "Class." + cmd.func.attr
            object_node, last_control_node = self.get_val_and_print(object, last_control_node)
            self.add_edge(object_node.name, func_node, color="Turquoise", label="arg[" + str(args_count) + "]")
            args_count += 1
        call_node = self.add_node("|Call " + name, color="Red", shape="box")
        self.add_edge(call_node, func_node)
        self.add_edge(last_control_node, call_node, color="Red")
        last_control_node = call_node

        for arg in cmd.args:
            val_node, last_control_node = self.get_val_and_print(arg, last_control_node)
            self.add_edge(val_node.name, func_node, color="Turquoise", label="arg[" + str(args_count) + "]")
            args_count += 1
        return last_control_node

    def do_match(self, cmd, last_control_node):
        raise NotImplementedError

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
            self.add_edge(val.name, ret_node, label="result", color="Turquoise")

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
        self.add_edge(val.name, raise_node, label="exception", color="Turquoise")
        self.add_edge(previous_node, raise_node, color="Red")

        if cmd.cause is not None:
            val, last_control_node = self.get_val_and_print(cmd.cause, last_control_node)
            self.add_edge(val.name, raise_node, label="cause", color="Turquoise")
        return raise_node

    def do_assert(self, cmd, last_control_node):
        # print condition to assert then the node and edge
        previous_node = last_control_node
        assert_node = self.add_node("|Assert", color="Red", shape="box")
        self.print_condition(cmd.test, assert_node, last_control_node)
        self.add_edge(previous_node, assert_node, color="Red")
        if cmd.msg is not None:
            msg, last_control_node = self.get_val_and_print(cmd.msg, last_control_node)
            self.add_edge(msg.name, assert_node, label="msg", color="Turquoise")
        return assert_node

    def do_delete(self, cmd: ast.Delete, last_control_node):
        # print condition to assert then the node and edge
        delete_node = self.add_node("|Delete", color="Red", shape="box")
        for target in cmd.targets:
            to_delete, last_control_node = self.get_val_and_print(target, last_control_node)
            self.add_edge(to_delete.name, delete_node, label="to_delete", color="Turquoise")
        self.add_edge(last_control_node, delete_node, color="Red")
        return delete_node

    def get_val(self, value, last_control_node) -> Tuple[VarNode, int]:  # all literal handlers
        # case variable node
        if isinstance(value, ast.Name):
            # print(self.table_stack)
            return self.table_stack[-1][value.id], last_control_node
        # case constant node
        elif isinstance(value, str):
            return VarNode(name="Constant(" + str(value) + ", str)"), last_control_node
        elif isinstance(value, ast.Constant):
            return VarNode(
                name="Constant(" + str(value.value) + ", " + type_of_val(value.value) + ")"), last_control_node
        elif isinstance(value, ast.FormattedValue):
            raise NotImplementedError
        elif isinstance(value, ast.JoinedStr):  # case f"sin({a}) is {sin(a):.3}"
            raise NotImplementedError
            # joinedstr_node = self.add_node("|JoinedStr ", color="Turquoise")
            # for idx, val in enumerate(value.values):
            #    node, last_control_node = self.get_val_and_print(val, last_control_node)
            #    self.add_edge(node, joinedstr_node, color="Turquoise", label="str" + str(idx))
            # return joinedstr_node, last_control_node
        elif isinstance(value, ast.List):  # case [1,2,3]
            list_node = self.add_node("|List ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node.name, list_node, color="Turquoise", label="element " + str(idx))
            return VarNode(name=list_node), last_control_node
        elif isinstance(value, ast.Tuple):  # case (1,2,3)
            tuple_node = self.add_node("|Tuple ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node.name, tuple_node, color="Turquoise", label="element " + str(idx))
            return VarNode(name=tuple_node), last_control_node
        elif isinstance(value, ast.Set):  # case {1,2,3}
            set_node = self.add_node("|Set ", color="Turquoise")
            for idx, val in enumerate(value.elts):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node.name, set_node, color="Turquoise", label="element " + str(idx))
            return VarNode(name=set_node), last_control_node
        elif isinstance(value, ast.Dict):  # case {k1:1,k2:2,k3:3}
            dict_node = self.add_node("|Dict ", color="Turquoise")
            for idx, key, val in enumerate(zip(value.keys, value.values)):
                key_node, last_control_node = self.get_val_and_print(key, last_control_node)
                val_node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(key_node.name, dict_node, color="Turquoise", label="key " + str(idx))
                self.add_edge(val_node.name, dict_node, color="Turquoise", label="val " + str(idx))
            return VarNode(name=dict_node), last_control_node
        elif isinstance(value, ast.Starred):  # case *b
            ref_node = self.add_node("|Reference ", color="Turquoise")
            node, last_control_node = self.get_val_and_print(value.value, last_control_node)
            self.add_edge(node.name, ref_node, color="Turquoise", label="ref")
            return VarNode(name=ref_node), last_control_node
        elif isinstance(value, ast.Expr):  # case expr
            return self.get_val_and_print(value.value, last_control_node)
        elif isinstance(value, ast.UnaryOp):  # case +b/-b/not b/ ~b
            unary_op_node = self.add_node("|" + get_unop(value.op), color="Turquoise")
            node, last_control_node = self.get_val_and_print(value.operand, last_control_node)
            self.add_edge(node.name, unary_op_node, color="Turquoise", label="operand")
            return VarNode(name=unary_op_node), last_control_node

        # case binop node
        elif isinstance(value, ast.BinOp):
            left, last_control_node = self.get_val_and_print(value.left, last_control_node)
            right, last_control_node = self.get_val_and_print(value.right, last_control_node)
            op_node = self.add_node("|" + get_binop(value.op), color="Turquoise")
            self.add_edge(left.name, op_node, color="Turquoise", label="x")
            self.add_edge(right.name, op_node, color="Turquoise", label="y")
            return VarNode(name=op_node), last_control_node

        # case relop node
        elif isinstance(value, ast.Compare):
            return self.do_compare(value, last_control_node, True)
        # case boolop node
        elif isinstance(value, ast.BoolOp):

            op_node = self.add_node("|" + get_boolop(value.op), color="Turquoise")
            for idx, val in enumerate(value.values):
                node, last_control_node = self.get_val_and_print(val, last_control_node)
                self.add_edge(node.name, op_node, color="Turquoise", label="x" + str(idx))

            return VarNode(name=op_node), last_control_node
        # case func
        elif isinstance(value, ast.Call):
            last_control_node = self.do_call(value, last_control_node)
            return VarNode(name=last_control_node), last_control_node
        elif isinstance(value, ast.keyword):
            raise NotImplementedError
        elif isinstance(value, ast.IfExp):  # case a if b else c
            if_exp_node = self.add_node("|If Exp", color="Turquoise")
            self.print_condition(value.test, if_exp_node, last_control_node)
            then_node, last_control_node = self.get_val_and_print(value.body, last_control_node)
            else_node, last_control_node = self.get_val_and_print(value.orelse, last_control_node)
            self.add_edge(then_node.name, if_exp_node, color="Turquoise", label="then")
            self.add_edge(else_node.name, if_exp_node, color="Turquoise", label="else")
            return VarNode(name=if_exp_node), last_control_node

        elif isinstance(value, ast.Attribute):  # case snake.colour
            assert isinstance(value.ctx, ast.Load), "store and del attribute not implemented"
            previous_node = last_control_node
            obj_node, last_control_node = self.get_val_and_print(value.value, last_control_node)
            att_node, last_control_node = self.get_val_and_print(value.attr, last_control_node)
            load_node = self.add_node("|Load Attribute", color="Red", shape="Box")
            self.add_edge(previous_node, load_node, color="Red")
            self.add_edge(obj_node.name, load_node, color="Turquoise", label="object")
            self.add_edge(att_node.name, load_node, color="Turquoise", label="attribute")
            return VarNode(name=load_node), load_node

        elif isinstance(value, ast.NamedExpr):  # case x:=4
            raise NotImplementedError
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
            self.add_edge(obj_node.name, load_node, color="Turquoise", label="object")
            if isinstance(value.slice, ast.Index):
                idx = value.slice
                index_node, last_control_node = self.get_val_and_print(idx, last_control_node)
                self.add_edge(index_node.name, load_node, color="Turquoise", label="index")
            else:
                for idx in value.slice:
                    index_node, last_control_node = self.get_val_and_print(idx, last_control_node)
                    self.add_edge(index_node.name, load_node, color="Turquoise", label="index")
            return VarNode(name=load_node), load_node
        elif isinstance(value, ast.Slice):  # case l[1:3]
            range_node = self.add_node("|indices range", color="Turquoise")
            lower_node, last_control_node = self.get_val_and_print(value.lower, last_control_node)
            upper_node, last_control_node = self.get_val_and_print(value.upper, last_control_node)
            self.add_edge(lower_node.name, range_node, color="Turquoise", label="lower")
            self.add_edge(upper_node.name, range_node, color="Turquoise", label="upper")
            if value.step is not None:
                step_node, last_control_node = self.get_val_and_print(value.step, last_control_node)
                self.add_edge(step_node.name, range_node, color="Turquoise", label="index")
            return VarNode(name=range_node), last_control_node
        elif isinstance(value, ast.Index):
            return self.get_val_and_print(value.value, last_control_node)
        elif isinstance(value, ast.ListComp):
            return self.do_list_comp(value, last_control_node)
        # TODO: add more cases

    def print_value(self, nd: VarNode, over_node=None) -> VarNode:
        value = nd.name
        if type(value) is tuple:  # phi case
            phi_node = self.add_node("|phi", shape="box")
            merge_node = value[1]
            self.add_edge(phi_node, merge_node)
            for val, node_num in value[0]:
                val_node = self.print_value(val)
                self.add_edge(val_node.name, phi_node, label="from " + str(node_num), color="Turquoise")
                self.name_to_node[val.name] = VarNode(name=phi_node)
            node = VarNode(name=phi_node)

        else:
            if isinstance(value, VarNode):
                return self.print_value(value,over_node)
            if type(value) is int:  # val is already node
                node = nd
            elif value in self.name_to_node:  # val is already printed
                node = self.name_to_node[value]
            else:  # value is ready to print
                self.name_to_node[value] = node = VarNode(name=self.add_node("|" + str(value), color="Turquoise",
                                                                over_node=over_node))

        return node

    def get_val_and_print(self, object, last_control_node) -> Tuple[VarNode, int]:
        object_node, last_control_node = self.get_val(object, last_control_node)
        if type(object_node.name) != int:
            object_node = self.print_value(object_node)
        return object_node, last_control_node

    def add_node(self, text, color="black", shape="ellipse", over_node=None):
        if over_node is not None:
            self.G.node(str(over_node), str(over_node) + text, color=color, shape=shape)
            return over_node
        self.G.node(str(self.counter), str(self.counter) + text, color=color, shape=shape)
        node = self.counter
        self.counter += 1
        return node

    def add_edge(self, node1: int, node2: int, label="", color="Black"):
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
            self.add_edge(left.name, comp_node, label="x", color="Turquoise")
            self.add_edge(right.name, comp_node, label="y", color="Turquoise")
            if print_val:
                zero = self.print_value(VarNode(name="Constant(" + str(0) + ", " + type_of_val(0) + ")"))
                one = self.print_value(VarNode(name="Constant(" + str(1) + ", " + type_of_val(1) + ")"))
                conditional_node = self.add_node("|Conditional", color="Turquoise", shape="diamond")
                self.add_edge(comp_node, conditional_node, label="?", color="Turquoise")
                self.add_edge(one.name, conditional_node, label="trueValue", color="Turquoise")
                self.add_edge(zero.name, conditional_node, label="falseValue", color="Turquoise")
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

        return VarNode(name=sum_node), last_control_node

    def print_condition(self, test, if_node, last_control_node, label="condition"):
        # cases like "if condition:"
        if isinstance(test, ast.Name) or isinstance(test, ast.Constant):
            to_compare = ast.Compare(left=test, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)])
            comp_node, last_control_node = self.do_compare(to_compare, last_control_node)
            comp_node = comp_node.name
        # cases like "if cond1 > cond2:"
        elif isinstance(test, ast.Compare):
            to_compare = test
            comp_node, last_control_node = self.do_compare(to_compare, last_control_node)
            comp_node = comp_node.name
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
        return last_control_node

    def make_while_dict(self, over_dict=None):
        new_dict = {}
        for key in self.table_stack[-1]:
            new_dict[key] = VarNode(name=self.counter, ann=None)
            self.counter += 1
        if over_dict is not None:
            for key in over_dict:
                new_dict[key] = over_dict[key]
        return new_dict

    def merge_while_dict(self, dict_before, before_loop_node, end_loop_node, loop_begin_node):
        dict_after_loop = self.table_stack.pop()
        pre_dict = self.table_stack.pop()
        new_dict = {}
        for key in dict_before:
            if dict_before[key].name == dict_after_loop[key].name:
                new_dict[key] = pre_dict[key]
                if '\t' + str(dict_before[key].name) + ' [' not in self.G.source:
                    for n in range(self.counter):
                        if '\t' + str(dict_before[key].name) + ' -> ' + str(n) in self.G.source:
                            if pre_dict[key].name != dict_before[key].name:
                                val = pre_dict[key]
                                self.print_value(val, over_node=dict_before[key])
                                new_dict[key] = val
                                break
            else:
                phi_node = dict_before[key].name
                val_before_node = self.print_value(pre_dict[key])
                self.G.node(str(phi_node), str(phi_node) + "|phi", shape="box")
                node_1 = self.print_value(dict_after_loop[key])
                node_2 = self.print_value(val_before_node)
                self.add_edge(node_1.name, phi_node, label="from " + str(end_loop_node), color="Turquoise")
                self.add_edge(node_2.name, phi_node, label="from " + str(before_loop_node), color="Turquoise")
                self.add_edge(phi_node, loop_begin_node)

                new_dict[key] = VarNode(name=phi_node)
        # print("new_dict", new_dict)
        self.table_stack.append(new_dict)

    def do_pass(self, cmd, last_control_node):
        pass

    def do_import(self, cmd, last_control_node):
        raise NotImplementedError

    def do_importfrom(self, cmd, last_control_node):
        raise NotImplementedError

    def do_try(self, cmd, last_control_node):
        raise NotImplementedError

    def do_with(self, cmd, last_control_node):
        raise NotImplementedError

    def do_yield(self, cmd, last_control_node):
        raise NotImplementedError
