from mgl_formulae import FormulaCompiler, FormulaDecompiler

import pytest


@pytest.fixture()
def compiler():
    return FormulaCompiler.create()


@pytest.fixture()
def decompiler():
    return FormulaDecompiler.create()

# Many test cases are adapted from https://github.com/mapbox/expression-jamsession (under BSD-2-Clause license)


_LITERAL_CASES = [
    pytest.param(7, '7'),
    pytest.param(-3, '-3'),
    pytest.param(77.323, '77.323'),
    pytest.param('sing', '"sing"'),
    pytest.param('国立競技場', '"国立競技場"', id="unicode literal"),
    pytest.param(True, 'true'),
    pytest.param(False, 'false'),
    pytest.param(None, 'null'),
]

_ROUNDTRIP_CASES = [
    *_LITERAL_CASES,
    pytest.param(['+', 3, 4],
                 '3 + 4'),
    pytest.param(['-', ['+', 3, 4]],
                 '-(3 + 4)'),
    pytest.param(['/', ['+', 3, 4], 7],
                 '(3 + 4) / 7'),
    pytest.param(['/', ['*', ['+', 3, 4], 2], 7],
                 '(3 + 4) * 2 / 7'),
    pytest.param(['sing'],
                 'sing()'),
    pytest.param(['log2', 3],
                 'log2(3)'),
    pytest.param(['log2', ['/', ['+', 3, 4], 7]],
                 'log2((3 + 4) / 7)'),
    pytest.param(['min', 2, 4, 6],
                 'min(2, 4, 6)'),
    pytest.param(['max', 2, 4, 6],
                 'max(2, 4, 6)'),
    pytest.param(['max', 2, 4, ['/', ['+', 3, 4], 7]],
                 'max(2, 4, (3 + 4) / 7)'),
    pytest.param(['max', 3, ['log2', 6]],
                 'max(3, log2(6))'),
    pytest.param(
        [
            'concat', 'there are ', ['get', 'population'], ' people ',
            ['upcase', ['concat', 'here ', 'not there']]
        ],
        '"there are " & get("population") & " people " & upcase("here " & "not there")',
        id="concat text"),
    pytest.param(['%', 3, 2],
                 '3 % 2'),
    pytest.param(['%', ['+', 3, 2], 2],
                 '(3 + 2) % 2'),
    pytest.param(['^', 3, 2],
                 '3 ^ 2'),
    pytest.param(['^', 3, ['^', 1, 2]],
                 '3 ^ 1 ^ 2'),
    pytest.param(['+', ['^', 3, 2], 1],
                 '3 ^ 2 + 1'),
    pytest.param(['^', 3, ['+', 2, 1]],
                 '3 ^ (2 + 1)'),
    pytest.param(['coalesce', ['get', 'foo'], ['==', -1, 1]],
                 'get("foo") ?? -1 == 1'),
    pytest.param(['concat', ['to-number', ['get', 'miles']], ' miles'],
                 'to_number(get("miles")) & " miles"',
                 id='to_number(get("miles")) & " miles"'),
    pytest.param(['*', 3, ['length', ['get', 'len']]],
                 '3 * length(get("len"))'),
    pytest.param(['literal', [1, 2]],
                 '[1, 2]'),
    pytest.param(['literal', [1, [2, 3]]],
                 '[1, [2, 3]]'),
    pytest.param(['literal', ['foo', 'bar']],
                 '["foo", "bar"]'),
    pytest.param(['coalesce', ['literal', ['foo', ['bar', 'baz']]]],
                 'coalesce(["foo", ["bar", "baz"]])'),
    pytest.param(['literal', {"foo": 1, "bar": 2}],
                 '{"foo": 1, "bar": 2}'),
    pytest.param(['literal', {"boolean": True, "string": 'false'}],
                 '{"boolean": true, "string": "false"}'),
    pytest.param(['literal', {"nested": {'also-nested': 'bees'}}],
                 '{"nested": {"also-nested": "bees"}}'),
    pytest.param(['literal', {',quoted:,separators': ':,}{'}],
                 '{",quoted:,separators": ":,}{"}'),
    pytest.param(['concat', ['literal', 'hsl('], ['literal', '235'], ['literal', ',75%,50%)']],
                 'literal("hsl(") & literal("235") & literal(",75%,50%)")'),
    pytest.param(["literal", "国立競技場"],
                 'literal("国立競技場")',
                 id="explicit unicode literal"),
    pytest.param(['!=', 3, 4],
                 '3 != 4'),
    pytest.param(
        [
            '!=',
            ['+', ['*', 3, 4], 1],
            ['-', 4, ['/', 3, 2]]
        ],
        '3 * 4 + 1 != 4 - 3 / 2'),
    pytest.param(['==', ['!=', 3, 4], True],
                 '(3 != 4) == true'),
    pytest.param(['!', ['get', 'x']],
                 '!get("x")'),
    pytest.param(['let', 'foo', 42, ['+', 1, ['var', 'foo']]],
                 'let $foo = 42; 1 + $foo'),
    pytest.param(
        ['case', ['has', 'foo'], ['get', 'foo'], 0],
        'has("foo") ? get("foo") : 0'),
    pytest.param(
        ['case', 0],
        'case(0)',
        id="empty case"),
    pytest.param(
        [
            'case',
            ['<=', ['get', 'foo'], 4],
            6,
            ['==', 2, 2],
            3,
            1
        ],
        'if (get("foo") <= 4) { 6 } else if (2 == 2) { 3 } else { 1 }',
        id="complex case/if-else-chain"),
    pytest.param(
        ['match', None],
        'match(null)',
        id="empty match 1"),
    pytest.param(
        ['match', 'input', None],
        'match("input", null)',
        id="empty match 2"),
    pytest.param(
        [
            'match',
            ['get', 'scalerank'],
            [1, 2],
            13,
            [3, 4],
            11,
            9
        ],
        'match(get("scalerank"), [1, 2], 13, [3, 4], 11, 9)',
        id="complex match"),
    pytest.param(
        [
            'number-format',
            1.005,
            {
                'max-fraction-digits': 2,
                'min-fraction-digits': 2
            }
        ],
        'number_format(1.005, {"max-fraction-digits": 2, "min-fraction-digits": 2})',
        id="number-format with kwargs"),
]

_COMPILE_CASES = [
    *_ROUNDTRIP_CASES,
    pytest.param(
        [
            'case',
            ['<=', ['get', 'foo'], 4],
            6,
            ['==', 2, 2],
            3,
            1
        ],
        'case(get("foo") <= 4, 6, 2 == 2, 3, 1)',
        id="explicit case"),
    pytest.param(
        [
            'concat', 'there are ', ['get', 'population'], ' people ',
            ['upcase', ['concat', 'here ', 'not there']]
        ],
        'concat("there are ", get("population"), " people ", upcase(concat("here ", "not there")))',
        id="explicit concat text"),
]

_DECOMPILE_CASES = [*_ROUNDTRIP_CASES]


@pytest.mark.parametrize(('expr', 'formula'), _COMPILE_CASES, ids=lambda v: repr(v))
def test_compile(compiler, formula, expr):
    result_expr = compiler.compile(formula)
    assert result_expr == expr


@pytest.mark.parametrize(('expr', 'formula'), _DECOMPILE_CASES, ids=lambda v: repr(v))
def test_decompile(decompiler, expr, formula):
    result_formula = decompiler.decompile(expr)
    assert result_formula == formula
