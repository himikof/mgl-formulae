from __future__ import annotations

import dataclasses
import functools
import itertools
from typing import Optional, Dict, Callable

import lark
from lark import Lark
from lark.grammar import Terminal, Symbol
from lark.reconstruct import Reconstructor

from .grammar import load_formulae_lark
from .rules import LExprTransformer, compile_lookup_table, LExprTypeMatcher, KWARG_FUNCTIONS, NOTHING, TRANSFORM_RULES


class LExprToTree(LExprTransformer):
    def __init__(self, transform_rules):
        self._lookup, wildcards = compile_lookup_table(transform_rules, lambda r: r.expr_first_set())
        self._type_lookup, self._wildcards = compile_lookup_table(
            wildcards, lambda r: r.expr_matcher.types if isinstance(r.expr_matcher, LExprTypeMatcher) else None)

    def _pass_through_indices(self, expr_tag, expr):
        if expr_tag == 'var':
            return None
        elif expr_tag == 'let':
            return set(range(1, len(expr) - 2, 2))
        return super()._pass_through_indices(expr_tag, expr)

    def _dispatch(self, tag, expr, path):
        if tag in KWARG_FUNCTIONS:
            # We need to manually recurse into kwarg values before dispatching to the rule table
            expr = expr.copy()
            for idx, arg in enumerate(expr):
                if idx > 0 and isinstance(arg, dict):
                    expr[idx] = {
                        k: self._transform(v, path + [idx, k])
                        for k, v in arg.items()
                    }

        for rule in itertools.chain(self._lookup.get(tag, ()), self._type_lookup.get(type(expr), ()), self._wildcards):
            result = rule.match_expr(expr)
            if result is not NOTHING:
                return result
        return expr


# This class exists only to work around https://github.com/lark-parser/lark/issues/927
class CustomReconstructor(Reconstructor):
    def __init__(self, parser: Lark, term_subs: Optional[Dict[str, Callable[[Symbol], str]]] = None) -> None:
        full_term_subs = {
            **(term_subs or {}),
            '&&': lambda _: '&&',
            '||': lambda _: '||',
            '??': lambda _: '??',
        }
        super().__init__(parser, full_term_subs)

    def match_tree(self, tree, rule_name):
        if len(tree.children) >= 2:
            if rule_name == 'all':
                return self._manually_expand_variadic_binop(rule_name, '&&', tree)
            elif rule_name == 'any':
                return self._manually_expand_variadic_binop(rule_name, '||', tree)
            elif rule_name == 'coalesce':
                return self._manually_expand_variadic_binop(rule_name, '??', tree)
            elif rule_name == 'concat':
                return self._manually_expand_variadic_binop(rule_name, 'AMPERSAND', tree)
        # print(f"match_tree: {rule_name=}")
        return super().match_tree(tree, rule_name)

    def _match_with_single_child(self, rule_name, child):
        return super().match_tree(lark.ParseTree(rule_name, [child]), rule_name)

    def _manually_expand_variadic_binop(self, rule_name, op_term, tree):
        new_children = []
        manual_expansion = []
        for child in tree.children:
            child_tree = self._match_with_single_child(rule_name, child)
            new_children.extend(child_tree.children)
            manual_expansion.extend(child_tree.meta.orig_expansion)
            manual_expansion.append(Terminal(op_term, filter_out=True))
        manual_expansion.pop()
        result = lark.ParseTree(rule_name, new_children)
        result.meta.orig_expansion = manual_expansion
        result.meta.match_tree = True
        return result


@dataclasses.dataclass()
class FormulaFormatter:
    _BIN_OPS = {'ADD_OP', 'MUL_OP', 'EQ_OP', 'ORD_OP',
                '?', '&&', '||', '??', '&', '^'}
    _SPACE_BEFORE = {*_BIN_OPS, '=', 'else'}
    _SPACE_AFTER = {*_BIN_OPS, ',', ':', '=', 'if', 'else', 'let', ';'}

    def need_spaces(self, item) -> tuple[bool, bool]:
        key = item.type if isinstance(item, lark.Token) else item
        space_before = key in self._SPACE_BEFORE
        space_after = key in self._SPACE_AFTER
        return space_before, space_after


@dataclasses.dataclass()
class FormulaDecompiler:
    parser: lark.Lark
    to_tree_transformer: LExprToTree
    reconstructor: CustomReconstructor

    @staticmethod
    def _post_proc_format(tokens, dump_tokens_to=None):
        if dump_tokens_to is not None:
            dump_tokens_to[:] = tokens = list(tokens)
        formatter = FormulaFormatter()
        has_space_from_prev = False
        for idx, item in enumerate(tokens):
            space_before, space_after = formatter.need_spaces(item)
            if space_before and not has_space_from_prev:
                yield ' '
            yield item
            has_space_from_prev = False
            if space_after:
                yield ' '
                has_space_from_prev = True

    def to_parse_tree(self, expr) -> lark.ParseTree:
        return self.to_tree_transformer.transform(expr)

    def reconstruct(self, tree, dump_tokens_to=None) -> str:
        return self.reconstructor.reconstruct(tree, postproc=functools.partial(
            self._post_proc_format, dump_tokens_to=dump_tokens_to))

    def decompile(self, expr) -> str:
        """
        Return a formula string equivalent to the expression (in the Mapbox style expression language).

        Applies consistent but arbitrary formatting to the resulting formula.
        """
        return self.reconstruct(self.to_parse_tree(expr))

    @classmethod
    def create(cls, compiler=None):
        parser = compiler.parser if compiler is not None else load_formulae_lark()

        return cls(parser=parser, to_tree_transformer=LExprToTree(TRANSFORM_RULES),
                   reconstructor=CustomReconstructor(parser))
