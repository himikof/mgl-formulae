from importlib import resources

import lark


_GLOBAL_FORMULAE_PARSER = None


def load_formulae_lark():
    global _GLOBAL_FORMULAE_PARSER
    if _GLOBAL_FORMULAE_PARSER is not None:
        return _GLOBAL_FORMULAE_PARSER
    with (resources.open_text(__package__, 'formulae.lark')) as grammar_f:
        _GLOBAL_FORMULAE_PARSER = lark.Lark(grammar_f, start='expr', maybe_placeholders=False, debug=False)
    return _GLOBAL_FORMULAE_PARSER
