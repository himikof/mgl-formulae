from __future__ import annotations

import ast
import dataclasses
import json
import typing as ty
from abc import ABCMeta, abstractmethod

import lark

try:
    from typing_extensions import Protocol as _Protocol
except ImportError:
    from typing import Protocol as _Protocol

_T = ty.TypeVar('_T')
_K = ty.TypeVar('_K')
TreeMeta = lark.tree.Meta
NothingType = ty.NewType('NothingType', object)
NOTHING = NothingType(object())
NOptional = ty.Union[NothingType, _T]


class TreeMatcherProto(_Protocol):
    def first(self) -> ty.Collection[str]:
        raise NotImplementedError

    def match(self, tree_node: str, transformed_children: list, tree_meta: TreeMeta) -> NOptional:
        raise NotImplementedError

    def produce(self, tree_result) -> lark.ParseTree:
        raise NotImplementedError


class LExprMatcherProto(_Protocol):
    def first(self) -> ty.Collection[str]:
        raise NotImplementedError

    def match(self, expr_value) -> NOptional:
        raise NotImplementedError

    def produce(self, value):
        raise NotImplementedError


class Rule(_Protocol, metaclass=ABCMeta):
    def tree_first_set(self) -> ty.Collection[str]:
        raise NotImplementedError

    def expr_first_set(self) -> ty.Collection[str]:
        raise NotImplementedError

    def match_tree(self, tree_node: str, transformed_children: list, tree_meta: TreeMeta) -> NOptional[ty.Any]:
        raise NotImplementedError

    def match_expr(self, expr_value) -> NOptional[lark.ParseTree]:
        raise NotImplementedError


@dataclasses.dataclass
class GenericRule(Rule):
    tree_matcher: TreeMatcherProto
    expr_matcher: LExprMatcherProto
    tree_to_expr: ty.Optional[ty.Callable[[ty.Any], ty.Any]] = None
    expr_to_tree: ty.Optional[ty.Callable[[ty.Any], ty.Any]] = None

    def tree_first_set(self) -> ty.Collection[str]:
        return self.tree_matcher.first()

    def expr_first_set(self) -> ty.Collection[str]:
        return self.expr_matcher.first()

    def match_tree(self, tree_node: str, transformed_children: list, tree_meta: TreeMeta) -> NOptional[ty.Any]:
        tree_result = self.tree_matcher.match(tree_node, transformed_children, tree_meta)
        if tree_result is NOTHING:
            return NOTHING
        middle_result = self.tree_to_expr(tree_result) if self.tree_to_expr is not None else tree_result
        return self.expr_matcher.produce(middle_result)

    def match_expr(self, expr_value) -> NOptional[lark.ParseTree]:
        middle_result = self.expr_matcher.match(expr_value)
        if middle_result is NOTHING:
            return NOTHING
        tree_result = self.expr_to_tree(middle_result) if self.expr_to_tree is not None else middle_result
        return self.tree_matcher.produce(tree_result)


@dataclasses.dataclass(frozen=True)
class TreeNodeMatcher(TreeMatcherProto):
    node: str

    def match(self, tree_node: str, transformed_children: list, tree_meta: TreeMeta) -> NOptional[list]:
        if tree_node == self.node:
            return transformed_children
        return NOTHING

    def first(self):
        return self.node,

    def produce(self, tree_result) -> lark.ParseTree:
        assert all(isinstance(v, (str, lark.Tree)) for v in tree_result), tree_result
        return lark.ParseTree(self.node, tree_result)


@dataclasses.dataclass(frozen=True)
class ScalarTreeNodeMatcher(TreeMatcherProto):
    node: str

    def match(self, tree_node: str, transformed_children: list, tree_meta: TreeMeta):
        if tree_node == self.node and len(transformed_children) == 1:
            return transformed_children[0]
        return NOTHING

    def first(self):
        return self.node,

    def produce(self, tree_result) -> lark.ParseTree:
        assert isinstance(tree_result, (str, lark.Tree))
        return lark.ParseTree(self.node, [tree_result])


@dataclasses.dataclass(frozen=True)
class UnitTreeNodeMatcher(TreeMatcherProto, ty.Generic[_T]):
    node: str
    value: _T

    def match(self, tree_node: str, transformed_children: list, tree_meta: TreeMeta):
        if tree_node == self.node and len(transformed_children) == 0:
            return self.value
        return NOTHING

    def first(self):
        return self.node,

    def produce(self, tree_result) -> lark.ParseTree:
        assert tree_result == self.value
        return lark.ParseTree(self.node, [])


_FORCE_SP = lark.Token(type='GWS', value=' ')


@dataclasses.dataclass(frozen=True)
class CaseConditionalsTreeMatcher(TreeMatcherProto):

    def first(self) -> ty.Collection[str]:
        return 'conditional', 'if_else_chain'

    def match(self, tree_node: str, transformed_children: list, tree_meta: TreeMeta) -> NOptional:
        if tree_node == 'conditional':
            # condition, true_value, false_value
            return transformed_children
        elif tree_node == 'if_else_chain':
            assert len(transformed_children) % 2 == 1
            return transformed_children
        return NOTHING

    def produce(self, tree_result) -> lark.ParseTree:
        assert len(tree_result) % 2 == 1
        assert all(isinstance(v, (str, lark.Tree)) for v in tree_result), tree_result
        # Hardcoded formatting :(
        if len(tree_result) == 3:
            tree_result = tree_result.copy()
            tree_result.insert(2, _FORCE_SP)
            return lark.ParseTree('conditional', tree_result)
        else:
            # Whitespace insertion indices in the parse tree: 1, 2, 4, (6, 7, 8)..., -1, len
            tree_result = tree_result.copy()
            for clause_idx in range(len(tree_result) // 2):
                tree_result.insert(clause_idx * 5 + 1, _FORCE_SP)
                tree_result.insert(clause_idx * 5 + 2, _FORCE_SP)
                tree_result.insert(clause_idx * 5 + 4, _FORCE_SP)
            tree_result.insert(-1, _FORCE_SP)
            tree_result.append(_FORCE_SP)
            return lark.ParseTree('if_else_chain', tree_result)


@dataclasses.dataclass(frozen=True)
class LExprTagMatcher(LExprMatcherProto):
    tag: str
    min_arity: ty.Optional[int] = None
    max_arity: ty.Optional[int] = None

    def first(self):
        return self.tag,

    def match(self, expr_value):
        if not isinstance(expr_value, list) or len(expr_value) < 1 + (self.min_arity or 0):
            return NOTHING
        if self.max_arity is not None and len(expr_value) > 1 + self.max_arity:
            return NOTHING
        if expr_value[0] == self.tag:
            return expr_value[1:]
        return NOTHING

    def produce(self, value: list) -> list:
        return [self.tag, *value]


@dataclasses.dataclass(frozen=True)
class LExprMultiTagMatcher(LExprMatcherProto):
    tags: set[str]

    def first(self):
        return self.tags

    def match(self, expr_value):
        if not isinstance(expr_value, list) or not expr_value:
            return NOTHING
        if expr_value[0] in self.tags:
            return expr_value
        return NOTHING

    def produce(self, value: list) -> list:
        assert value and value[0] in self.tags
        return value


@dataclasses.dataclass(frozen=True)
class LExprTagScalarMatcher(LExprMatcherProto):
    tag: str
    guard: ty.Callable[[ty.Any], bool] | None = None

    def first(self):
        return self.tag,

    def match(self, expr_value):
        if not isinstance(expr_value, list) or len(expr_value) != 2:
            return NOTHING
        if expr_value[0] == self.tag:
            result = expr_value[1]
            if self.guard is None or self.guard(result):
                return result
        return NOTHING

    def produce(self, value):
        return [self.tag, value]


@dataclasses.dataclass(frozen=True)
class LExprBinOpMatcher(LExprMatcherProto):
    ops: set[str]
    op_token: str

    def first(self):
        return self.ops

    def match(self, expr_value):
        if not isinstance(expr_value, list) or len(expr_value) != 3:
            return NOTHING
        if expr_value[0] in self.ops:
            return [expr_value[1], lark.Token(self.op_token, expr_value[0]), expr_value[2]]
        return NOTHING

    def produce(self, values):
        left, op, right = values
        assert op in self.ops
        return [str(op), left, right]


@dataclasses.dataclass(frozen=True, init=False)
class LExprTypeMatcher(LExprMatcherProto):
    types: tuple[type]

    def __init__(self, *types: type):
        object.__setattr__(self, 'types', types)

    def first(self):
        return ()

    def match(self, expr_value):
        if isinstance(expr_value, self.types):
            return expr_value
        return NOTHING

    def produce(self, value):
        assert isinstance(value, self.types)
        return value


@dataclasses.dataclass(frozen=True)
class JsonToken:
    name: str

    def __call__(self, v):
        return lark.Token(type=self.name, value=json.dumps(v, ensure_ascii=False, check_circular=False))


def _parse_var_ref(v: str):
    # TODO: Use str.removeprefix on Python 3.9+
    return v[1:] if v.startswith('$') else v


def _dump_var_ref(var_id: str):
    assert isinstance(var_id, str), f"var_id={var_id}"
    return lark.Token(type='VAR_REF', value=f'${var_id}')


def _parse_let(children):
    result = []
    for var_bind in children[:-1]:
        var_name = _parse_var_ref(var_bind.children[0])
        initializer = var_bind.children[1] if len(var_bind.children) > 1 else None
        result += (var_name, initializer)
    result.append(children[-1])
    return result


def _dump_let(args):
    children = []
    for var_name, initializer in zip(args[::2], args[1::2]):
        bind_children = [_dump_var_ref(var_name)]
        if initializer.data != 'null':
            bind_children.append(initializer)
        children.append(lark.ParseTree('var_bind', bind_children))
    children.append(args[-1])
    return children


def _parse_call(children):
    func, *args = children
    if '_' in func:
        func = func[0] + func[1:].replace('_', '-')
    return [str(func), *args]


_JSON_RAW_LIT = JsonToken('RAW_LITERAL')
_STR_LIT = JsonToken('ESCAPED_STRING')


def _dump_match(args):
    result = args.copy()
    for idx, arg in enumerate(args):
        if idx % 2 == 1 and idx + 1 != len(args) and isinstance(arg, (list, dict)):
            result[idx] = _JSON_RAW_LIT(arg)
    return result


def _dump_call(children):
    func, *args = children
    if '-' in func:
        func = func.replace('-', '_')
    return [lark.Token('IDENT', func), *args]


KWARG_FUNCTIONS = {"collator", "format", "number-format"}


def _dump_call_kwargs(children):
    func, *args = children
    assert func in KWARG_FUNCTIONS
    if '-' in func:
        func = func.replace('-', '_')
    for idx, arg in enumerate(args):
        if isinstance(arg, dict):
            args[idx] = lark.ParseTree('kwargs', [lark.ParseTree('kwargs_item', [_STR_LIT(k), v])
                                                  for k, v in arg.items()])
    return [lark.Token('KWARGS_FUNC', func), *args]


GR = GenericRule

TRANSFORM_RULES = [
    GR(TreeNodeMatcher('any'), LExprTagMatcher('any', min_arity=2)),
    GR(TreeNodeMatcher('all'), LExprTagMatcher('all', min_arity=2)),
    GR(TreeNodeMatcher('coalesce'), LExprTagMatcher('coalesce', min_arity=2)),
    GR(TreeNodeMatcher('concat'), LExprTagMatcher('concat', min_arity=2)),
    GR(TreeNodeMatcher('match'), LExprTagMatcher('match', min_arity=3), None, _dump_match),
    GR(TreeNodeMatcher('binop_eq'), LExprBinOpMatcher({'==', '!='}, op_token='EQ_OP')),
    GR(TreeNodeMatcher('binop_ord'), LExprBinOpMatcher({'<=', '>=', '<', '>', 'in'}, op_token='ORD_OP')),
    GR(TreeNodeMatcher('binop_add'), LExprBinOpMatcher({'+', '-'}, op_token='ADD_OP')),
    GR(TreeNodeMatcher('binop_mul'), LExprBinOpMatcher({'*', '/', '%'}, op_token='MUL_OP')),
    GR(TreeNodeMatcher('binop_exp'), LExprTagMatcher('^', min_arity=2, max_arity=2)),
    GR(ScalarTreeNodeMatcher('unary_neg'), LExprTagScalarMatcher('-')),
    GR(ScalarTreeNodeMatcher('unary_not'), LExprTagScalarMatcher('!')),
    GR(ScalarTreeNodeMatcher('bool'), LExprTypeMatcher(bool), lambda t: t == 'true', JsonToken('BOOL_LITERAL')),
    GR(ScalarTreeNodeMatcher('num'), LExprTypeMatcher(int, float),
       lambda t: ast.literal_eval(str(t)), JsonToken('SIGNED_NUMBER')),
    GR(ScalarTreeNodeMatcher('str'), LExprTypeMatcher(str),
       lambda t: ast.literal_eval(str(t)), _STR_LIT),
    GR(UnitTreeNodeMatcher('null', value=None), LExprTypeMatcher(type(None))),
    GR(ScalarTreeNodeMatcher('literal_expr'),
       LExprTagScalarMatcher('literal', guard=lambda lit: isinstance(lit, (list, dict))), None, _JSON_RAW_LIT),
    GR(ScalarTreeNodeMatcher('var'), LExprTagScalarMatcher('var'), _parse_var_ref, _dump_var_ref),
    GR(CaseConditionalsTreeMatcher(), LExprTagMatcher('case', min_arity=2)),
    GR(TreeNodeMatcher('let'), LExprTagMatcher('let'), _parse_let, _dump_let),
    GR(TreeNodeMatcher('call_kwargs'), LExprMultiTagMatcher(KWARG_FUNCTIONS), _parse_call, _dump_call_kwargs),
    GR(TreeNodeMatcher('call'), LExprTypeMatcher(list), _parse_call, _dump_call),
]


def compile_lookup_table(rules: ty.Sequence[_T],
                         key_set_getter: ty.Callable[[_T], ty.Optional[ty.Iterable[_K]]]
                         ) -> tuple[dict[_K, list[_T]], list[_T]]:
    lookup = {}
    wildcard_rules = []
    for rule in rules:
        key_set = key_set_getter(rule)
        if not key_set:
            wildcard_rules.append(rule)
            continue
        for key_value in key_set:
            lookup.setdefault(key_value, []).append(rule)
    return lookup, wildcard_rules


class LExprTransformer(metaclass=ABCMeta):
    def transform(self, expr):
        return self._transform(expr, [])

    @abstractmethod
    def _dispatch(self, tag, expr, path):
        return expr

    @staticmethod
    def _pass_through_indices(expr_tag, expr):
        """None means full passthrough"""
        if expr_tag == 'literal' and len(expr) == 2 and isinstance(expr[1], (list, dict)):
            return None
        elif expr_tag == 'match':
            return set(range(2, len(expr) - 1, 2))
        return set()

    def _transform(self, expr, path):
        if not isinstance(expr, list) or not expr:
            expr_tag = None
            result = expr
        else:
            expr_tag = expr[0]
            pass_through_indices = self._pass_through_indices(expr_tag, expr)
            if pass_through_indices is None:
                result = expr
            else:
                result = [expr_tag]
                path.append(None)
                for i in range(1, len(expr)):
                    if i in pass_through_indices:
                        result.append(expr[i])
                    else:
                        path[-1] = i
                        result.append(self._transform(expr[i], path))
                path.pop()

        return self._dispatch(expr_tag, result, path)
