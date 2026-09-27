# jsonpath-nv

JSONPath is a query language for selecting parts of a JSON document.
It was standardised in 2024 as
[RFC 9535](https://www.rfc-editor.org/rfc/rfc9535), which is the version
this package implements, rather than the 2007 article every earlier
library interprets slightly differently. A query is parsed into a typed
value, checked, and run against the standard library's JSON value.

```
$.store.book[?@.price < 10].title
```

## What it is

A **query** begins with `$`, the document's root, and is a sequence of
**segments**. A segment is a **child segment**, which looks at the
children of each node it is given, or a **descendant segment**, written
`..`, which looks at each node and everything below it.

Each segment holds one or more **selectors**, and RFC 9535 section 2.3
defines five.

| Selector | Written | What it selects |
| --- | --- | --- |
| Name | `.name`, `['name']` | One member of an object |
| Wildcard | `*` | Every member of an object, or every element of an array |
| Index | `[0]`, `[-1]` | One element of an array, counted from the end when negative |
| Slice | `[1:5:2]` | A range of elements, with Python's semantics and clamping |
| Filter | `[?<expr>]` | The children for which an expression is true |

A **nodelist** is what a query answers: each **node** is a value
together with its **normalized path**, RFC 9535 section 2.7's
unambiguous spelling of where the value was, such as
`$['store']['book'][0]['title']`.

A **filter expression** is built of `&&`, `||` and `!`, comparisons
with the six operators, a bare query as an existence test, and calls to
the five **function extensions** RFC 9535 defines.

| Function | Signature | What it answers |
| --- | --- | --- |
| `length()` | `ValueType -> ValueType` | Members of an object, characters of a string, elements of an array |
| `count()` | `NodesType -> ValueType` | How many nodes the argument selected |
| `match()` | `(ValueType, ValueType) -> LogicalType` | The whole string matches the pattern |
| `search()` | `(ValueType, ValueType) -> LogicalType` | Some substring matches the pattern |
| `value()` | `NodesType -> ValueType` | The value, when the argument selected exactly one node |

A query is **singular** when every segment names one child: only names
and indices, no wildcard, no slice and no filter. `@.a[0]` is singular
and `@.*` is not. Singularity decides where a query may appear.

The pattern language of `match()` and `search()` is **I-Regexp**,
[RFC 9485](https://www.rfc-editor.org/rfc/rfc9485): a subset chosen so
that a pattern matches the same strings in every implementation.

## Install

```
novo pkg add jsonpath-nv
```

## Example

```novo
use std.json
use jperror
use jpeval

fn main() [io]
    match json.parse("{\"users\":[{\"n\":\"ada\",\"age\":36},{\"n\":\"bob\",\"age\":24}]}")
        None      => println("not json")
        Some(doc) =>
            // Parse the query and run it in one call. Only the parse
            // can fail; running a query cannot.
            match jpeval.query(doc, "$.users[?@.age >= 30].n")
                Err(f)    => println(jperror.message(f))
                Ok(found) =>
                    for node in found
                        // The value, and the normalized path saying
                        // where in the document it was found.
                        println("${json.stringify(node.value)} at ${node.path}")
```

It prints `"ada" at $['users'][0]['n']`.

Build and test with `novo pkg build` and `novo test`.

## What the package contains

| Module | Contents |
| --- | --- |
| `jpquery` | The query as a typed value: the parse, the segments, the selectors, the filter grammar, the five functions and their type table. |
| `jpeval` | Running a query: the selection, the bounded selection, the normalized path in both directions, and comparison of two JSON values. |
| `jpregex` | I-Regexp: compiling a pattern, matching it, and naming the construct in a pattern that this language does not have. |
| `jperror` | Every reason a query does not parse, each with the byte range in the query text. |

## How to choose an entry point

**`jpeval.query` parses and runs in one call.** Use it for a query
written in the program, where a failure to parse is a programming
mistake.

**`jpquery.parse` then `jpeval.select` is the shape for a query from
outside.** Parse once, at the edge, and keep the `JpQuery`. From then
on the query cannot fail and running it costs only time.

**`jpeval.select_with` bounds the walk.** It takes a `JpLimits` and
answers what was found along with whether a bound stopped it. Use it
for a query a stranger supplied.

**`jpeval.select_values` and `select_paths` answer one half each**, and
`select_one` answers the first node or none.

**`jpeval.at_path` revisits a location.** It takes a normalized path
from an earlier result, so finding something once and coming back to it
later costs no second query.

## The rules a user needs

1. **Running a query cannot fail.** `jpeval.select` answers a list and
   not a result. RFC 9535 makes every disagreement at run time produce
   false or an empty nodelist: comparing a string with a number is
   false, section 2.3.5.2.2; a `match()` whose pattern is not I-Regexp
   is false, section 2.4.6; a name nothing has selects nothing.
2. **Everything that can be wrong is wrong in the query.**
   `jpquery.parse` is where it is caught, and every fault carries the
   byte offset and one past the end of the construct, so a message can
   underline it.
3. **Well-typedness is checked when a query is parsed.** RFC 9535
   section 2.4.3 is the part implementations skip.

   | Query | Here |
   | --- | --- |
   | `$[?length(@.a) > 1]` | parses |
   | `$[?length(@.*) > 1]` | `JpWrongArgumentType`: `length` takes a value and `@.*` is a nodelist |
   | `$[?count(@.*) > 1]` | parses: `count` takes a nodelist |
   | `$[?match(@.a, 'x')]` | parses: a logical result is a test |
   | `$[?match(@.a, 'x') == true]` | `JpWrongArgumentType`: a logical is not a value |
   | `$[?length(@.a)]` | `JpWrongArgumentType`: a value is not a test |
   | `$[?@.* == 1]` | `JpNotSingular`: a comparison operand is one value |

   `jpquery.parameter_types` and `jpquery.result_type` are section
   2.4.2's table as data, so the rule can be read as well as enforced.
4. **A comparison operand must be a singular query.** A lenient
   implementation picks the first node instead, and answers differently
   on the day a document has two matching members.
   `jpquery.is_singular` says whether a query is one.
5. **Every node carries its normalized path.** It is always quoted and
   never the shorthand, so two paths to one location are the same
   string. `jpeval.path_steps` turns a path back into steps and
   `jpeval.at_path` walks it.
6. **Order is the specification's.** Document order within a selector,
   selector order within a segment. `$[2,0]` answers the third element
   before the first.
7. **A slice's defaults depend on the sign of its step.** An absent
   start is absent and not zero, so `[::-1]` starts at the end. A step
   of zero parses and selects nothing (RFC 9535 section 2.3.4.2.2).
8. **An array index is bounded at 2^53 - 1.** RFC 9535 section 2.1 sets
   that range, because a JSON number is a double. Outside it the parse
   answers `JpBadIndex`.
9. **A bounded walk truncates rather than fails.** `JpLimits` carries
   the deepest descent, the most nodes selected and the most nodes
   visited. When one is reached, `JpSelection.truncated` is true and
   the nodes already found are real. The defaults are 256 deep, 100 000
   selected and 1 000 000 visited.
10. **`match()` and `search()` take an I-Regexp pattern, not a
    general regular expression.** I-Regexp has no anchors, so `^` and
    `$` are ordinary characters, and no backreferences, lookaround,
    lazy quantifiers, named groups or capture semantics. A pattern
    outside the language is `JpBadRegex` from `jpregex.compile`, and
    `jpregex.unsupported_construct` names what it used, such as
    `"inline flag"` or `"lookahead"`.
11. **A pattern using `\p{...}` needs a lookup the caller supplies.**
    The Unicode general categories are a quarter of a megabyte of
    table, which a caller selecting `$.store.book[0].title` should not
    carry. `jpregex.compile` refuses such a pattern with
    `JpNoCategoryLookup`; `jpregex.compile_with` takes a
    `fn(Int) -> Str` that answers a code point's category, and
    `jpeval.select_categorised` carries it through the evaluator.
    Under `jpeval.select` such a pattern does not compile, and its
    `match()` or `search()` is false.
12. **Comparison is structural.** RFC 9535 section 2.3.5.2.2 compares
    arrays and objects by their contents, treats `1` and `1.0` as
    equal, and ignores member order. `jpeval.value_equals`, which is
    `std.json.equals`, and `value_order` are that rule.
13. **An object's members are visited in the order of the document's
    text.** RFC 9535 leaves that order to the implementation, and
    `std.json` keeps it, so `$.*` over `{"b":1,"a":2}` answers `1`
    before `2`.
14. **`jperror.kind_name` is stable across releases.** The spellings
    are lower case with hyphens, such as `not-singular`, because
    programs quote them in their own messages and tests.

## What is not included

- **A JSON value type of this package's own.** Queries run over
  `std.json`'s value, because a second JSON type in one program would
  mean converting every document before it could be queried.
- **A microcontroller build, and a browser build.** `std.json` is
  refused on the embedded tier and has no wasm runtime, so neither is
  claimed here even though this package's own arithmetic would run.
- **A general regular expression engine.** See rule 10. Accepting a
  `std.regex` pattern would make a query that works here answer
  differently against a conforming implementation on the other side of
  a wire.
- **The Unicode general category table.** See rule 11.
- **Writing to a document.** A node's normalized path is what a caller
  uses to find the location again; changing the value is the caller's.
- **Pipes, stages and output formatting.** A JSONPath query is one
  selection. A program that wants a pipeline of transformations wants
  a jq-shaped tool.

## Related packages

- `std.json` in the standard library parses and renders JSON and is the
  value this package selects over. `std.regex` is a different pattern
  language, PCRE-shaped, and is deliberately not used here.
- [unicode-nv](https://novo-lang.org/packages/unicode-nv) carries the
  general categories `\p{...}` needs. A caller that has it passes
  `uclass.category_abbrev(uclass.category(data, ch))` to
  `jpregex.compile_with`; a caller that does not gets a named refusal
  rather than a guess.
- [schema-nv](https://novo-lang.org/packages/schema-nv) validates a
  JSON document against JSON Schema and reports where it failed. It
  answers whether a document is right; this package answers which parts
  of it you asked for. Both select over `std.json`'s value.
- `orbit/nq` in the monorepo is the jq-style filter this package's
  evaluator is cut to serve. It keeps its pipes, its command line and
  jq's own rules where they differ from JSONPath's; a JSONPath query is
  the path inside one of its stages.

## Tests

```bash
novo test tests/jpquery_tests.nv    # the grammar and the type rules
novo test tests/jpeval_tests.nv     # the walk, the bounds, the paths and the functions
novo test tests/jpregex_tests.nv    # I-Regexp's grammar and the automaton
novo test tests/jprender_tests.nv   # render, and check_types on a query built in code
novo test tests/jperror_tests.nv    # the fault kinds and the message
novo test tests/cts_tests.nv        # the JSONPath Compliance Test Suite
bash tests/coverage.sh              # line coverage over src/
```

RFC 9535 is the specification, and `tests/jpeval_tests.nv` quotes the
bookstore document and table from its section 1.5. The oracle is the
JSONPath Compliance Test Suite, which lists queries with the documents
and the exact nodelists they must produce, and queries that must be
refused. `tests/cts_tests.nv` holds 702 of its 706 cases, written by
`tools/cts.py`. The tool lists the four left out: two whose query holds
U+0000, which a `Str` cannot, and two that read `^` and `$` in a
`match()` pattern as anchors, which RFC 9485's grammar makes ordinary
characters.

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
