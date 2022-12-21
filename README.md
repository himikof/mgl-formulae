# Formula syntax for Mapbox GL expressions

A library for converting [Mapbox GL expressions](https://www.mapbox.com/mapbox-gl-js/style-spec/#expressions) to/from
a formula syntax more familiar to humans (extended JavaScript-like grammar).

## Syntax examples

```js
// Expression
["+", 3, 4]
// Formula
3 + 4
```

```js
// Expression
["==", ["coalesce", ["get", "foo"], -1], 1]
// Formula
(get("foo") ?? -1) == 1
```

```js
// Expression
["min", ["zoom"], ["log2", 3.14]]
// Formula
min(zoom(), log2(3.14))
```

```js
// Expression
[
    "!=",
    ["+", ["*", 3, 4], ["get", "foo"]],
    ["-", 4, ["/", 3, 2]]
]
// Formula
3 * 4 + get("foo") != 4 - 3 / 2
```

```js
// Expression
["concat", "id: ", ["number-format", ["get", "id"], {}]]
// Formula
"label: " & number_format(get("id"), {})
```

## Usage

```python
from mgl_formulae import FormulaCompiler, FormulaDecompiler
compiler = FormulaCompiler.create()
decompiler = FormulaDecompiler.create()

assert compiler.compile('3 + 4') == ['+', 3, 4]
assert decompiler.decompile(['+', 3, 4]) == '3 + 4'
```

## Features
* Transparent function calls: any unknown expression turns into a function call automatically, 
  simplifying forward compatibility when new language functions are added
* Automatic conversion between dash in expressions and underscore in function names:
  e.g. `number-format` and `number_format`
* Rich infix operator set for common operations with JavaScript precedence/associativity
* Automatic conversion between if/else chains, ternary conditionals and `case` expressions 
* Full support for all json literal values, including `literal` conversion for lists and objects
* Support for functions with keyword arguments (e.g. `format`)
* Syntactic sugar for `let`/`var`: `let $foo = 42; 1 + $foo`

## Non-trivial operator table

|   Operator   | Expression |
|:------------:|:----------:|
|      ??      |  coalesce  |
| &#124;&#124; |    any     |
|      &&      |    all     |
|      &       |   concat   |
|  a ? b : c   |   case/3   |

Other common operators are preserved as-is, while having the expected JavaScript-like semantics. 
