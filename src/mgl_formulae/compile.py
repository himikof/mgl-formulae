from __future__ import annotations

import ast
import dataclasses
import functools

import lark

from .grammar import load_formulae_lark
from .rules import Rule, compile_lookup_table, NOTHING, TRANSFORM_RULES


class TreeToLExpr(lark.Transformer):
    _lookup: dict[str, list[Rule]]
    _wildcards: list[Rule]

    def __init__(self, transform_rules):
        super().__init__(visit_tokens=False)
        self._lookup, self._wildcards = compile_lookup_table(transform_rules, lambda r: r.tree_first_set())
        for tag, tag_rules in self._lookup.items():
            bound_call = functools.partial(type(self)._on_lookup, self, tag_rules=tag_rules)
            bound_call.visit_wrapper = bound_call
            setattr(self, tag, bound_call)

    def _on_lookup(self, _, data, children, meta, *, tag_rules: list[Rule]):
        for rule in tag_rules:
            result = rule.match_tree(data, children, meta)
            if result is not NOTHING:
                return result
        return self.__default__(data, children, meta)

    def __default__(self, data, children, meta):
        for rule in self._wildcards:
            result = rule.match_tree(data, children, meta)
            if result is not NOTHING:
                return result
        return super().__default__(data, children, meta)

    @lark.visitors.v_args(inline=True)
    def literal_list(self, *items):
        return list(items)

    @lark.visitors.v_args(inline=True)
    def literal_dict(self, *kv_items):
        return {
            ast.literal_eval(item.children[0]): item.children[1]
            for item in kv_items
        }

    kwargs = literal_dict


@dataclasses.dataclass()
class FormulaCompiler:
    parser: lark.Lark
    expand_transformer: TreeToLExpr

    def compile(self, formula: str):
        """
        Return an expanded list-expression representation of the formula in the Mapbox style expression language.
        """
        tree = self.parser.parse(formula)
        return self.expand_transformer.transform(tree)

    @classmethod
    def create(cls):
        return cls(parser=load_formulae_lark(), expand_transformer=TreeToLExpr(TRANSFORM_RULES))
