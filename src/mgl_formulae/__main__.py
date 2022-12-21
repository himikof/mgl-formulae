import argparse
import json

from mgl_formulae import load_formulae_lark
from mgl_formulae.compile import TreeToLExpr, FormulaCompiler
from mgl_formulae.rebuild import FormulaDecompiler
from mgl_formulae.rules import TRANSFORM_RULES


def cmd_expand(args):
    print(f"Expanding formula {args.formula!r}:")
    fp = load_formulae_lark()
    tree = fp.parse(args.formula)
    print(f"Parse tree:\n{tree.pretty()}")
    expander = TreeToLExpr(TRANSFORM_RULES)
    result = expander.transform(tree)
    print(f"Result:\n{json.dumps(result) if args.dump_json else repr(result)}")


def cmd_compact(args):
    compactor = FormulaDecompiler.create()
    if args.pre_expand:
        expander = FormulaCompiler.create()
        print(f"Pre-expanding formula {args.expr!r}")
        expr = expander.compile(args.expr)
    else:
        expr = json.loads(args.expr)
    print(f"Compacting l-expression {expr!r}:")
    tree = compactor.to_parse_tree(expr)
    print(f"Parse tree:\n{tree.pretty()}")
    # # print(self.reconstructor.match_tree(tree, tree.data).pretty())
    formula = compactor.reconstruct(tree)
    print(f"Result formula:\n{formula}")


def main():
    arg_parser = argparse.ArgumentParser()

    commands_parser = arg_parser.add_subparsers(required=True)

    sub_expand_parser = commands_parser.add_parser('expand')
    sub_expand_parser.add_argument('formula')
    sub_expand_parser.add_argument('--raw', action='store_false', dest='dump_json')
    sub_expand_parser.set_defaults(func=cmd_expand)

    sub_compact_parser = commands_parser.add_parser('compact')
    sub_compact_parser.add_argument('expr')
    sub_compact_parser.add_argument('--pre-expand', action='store_true')
    sub_compact_parser.set_defaults(func=cmd_compact)

    args = arg_parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
