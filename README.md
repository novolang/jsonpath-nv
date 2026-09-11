# jsonpath-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`.  Installing this package works;
calling it panics with `not implemented`.

## What this is

JSONPath, as RFC 9535 standardised it in 2024 — not the 2007 blog post
every library implements slightly differently.  A query is parsed into a
typed value, checked, and run against the standard library's JSON value;
every node that comes back knows where it was.

```
$.store.book[?@.price < 10].title
```

Four modules.

| surface | module | reach for it when |
| --- | --- | --- |
| the **query** | `jpquery` | you are parsing, checking or rendering a query |
| the **evaluator** | `jpeval` | you are running one against a document |
| the **patterns** | `jpregex` | you are using `match()` or `search()` |
| the **faults** | `jperror` | you are telling somebody their query is wrong |

## Adding it, and checking it

```bash
novo pkg add jsonpath-nv       # into your novo.toml
novo pkg build                 # type- and effect-check the package
novo test --isolate tests/jpquery_tests.nv
```

`novo test` is red today and that is the point of the release: every
assertion fails with `not implemented: jsonpath-nv.<module>.<fn>`.  They
turn green one at a time as bodies land.

## The one example that will work

```novo
use std.json
use jpeval

fn main() [io]
    match json.parse("{\"users\":[{\"n\":\"ada\",\"age\":36},{\"n\":\"bob\",\"age\":24}]}")
        None      =>
            println("not json")
        Some(doc) =>
            match jpeval.query(doc, "$.users[?@.age >= 30].n")
                Err(f)    => println("bad query at ${f.at}")
                Ok(found) =>
                    for node in found
                        println("${json.stringify(node.value)} at ${node.path}")
            // "ada" at $['users'][0]['n']
```

## The load-bearing interface

Two facts, and everything else follows from them.

**The first: evaluation cannot fail.**  `jpeval.select` answers a list,
not a `Result`.  RFC 9535 makes every runtime disagreement produce false
or an empty nodelist rather than an error — § 2.3.5.2.2 says comparing a
string with a number is false, § 2.4.6 says `match()` with a pattern
that is not I-Regexp is false, and a selector that names a member
nothing has selects nothing.  Everything that *can* be wrong is wrong in
the **query**, and `jpquery.parse` is where it is caught.

```novo norun:pseudo
pub fn parse(query: Str)     -> Result<JpQuery, jperror.JpFault> []
pub fn select(q: JpQuery, root: JsonValueH) -> [JpNode]          []
```

That split is the API.  A service that accepts queries from outside
parses once, at the edge, and from then on can only be slow — which is
what `jpeval.select_with` and `JpLimits` are for, and even those
*truncate* rather than raise, because a walk that ran out of budget
produced real nodes and throwing them away would answer less than is
known.

**The second: every node carries its normalized path.**  § 2.7's, quoted
throughout: `$['store']['book'][0]['title']`.  It is the half of
JSONPath that makes a result usable rather than merely visible — a
program that selects `$..price` and then wants to *write* those
locations has to know where each one was, and a bare list of values
cannot say.  `jpeval.path_steps` and `jpeval.at_path` turn a stored path
back into a walk, so finding something once and revisiting it later
costs no second query.

## Well-typedness is checked when you parse, not when you run

RFC 9535 § 2.4.3 is the part implementations skip, and it is what makes
one JSONPath engine's answers another's.

`length(@.*)` is not a query that answers nothing.  It is **not a
query**.  `@.*` is a `NodesType`, `length` takes a `ValueType`, and the
only nodes-to-value conversion the specification allows is a *singular*
query used directly.  So:

| query | here |
| --- | --- |
| `$[?length(@.a) > 1]` | parses |
| `$[?length(@.*) > 1]` | `JpWrongArgumentType` |
| `$[?count(@.*) > 1]` | parses — `count` takes a `NodesType` |
| `$[?match(@.a, 'x')]` | parses — a `LogicalType` result is the test |
| `$[?match(@.a, 'x') == true]` | `JpWrongArgumentType` — a logical is not a value |
| `$[?length(@.a)]` | `JpWrongArgumentType` — a value is not a test |
| `$[?@.* == 1]` | `JpNotSingular` — a comparison operand is one value |

A lenient implementation would answer nothing for the refused rows, and
a caller would find out on the Tuesday a document happened to have two
matching members.  `jpquery.parameter_types` and `jpquery.result_type`
are § 2.4.2's table as data, so the rule is readable rather than only
enforced.

## The pattern language is I-Regexp, and it is not a small PCRE

`match()` and `search()` take an **I-Regexp** (RFC 9485) pattern, and
`jpregex` is that language and only that language.

It has no anchors — `^` and `$` are ordinary characters — no
backreferences, no lookaround, no lazy quantifiers, no named groups and
no capture semantics at all.  Every one of those is either
unimplementable in a finite automaton or specified differently by every
engine that has it, and what is left matches the same strings
everywhere.  That is the *point* of RFC 9485: it is what makes a
JSONPath query portable.

So accepting a `std.regex` pattern here would be worse than refusing
one.  A query with `(?i)` in it would work against this implementation
and answer different nodes against a conforming one on the other side of
a wire.  `jpregex.unsupported_construct` names what a pattern used —
`"inline flag"`, `"backreference"`, `"lookahead"`, `"lazy quantifier"` —
so a tool can tell a person *why* the pattern that works everywhere else
does not work here.

**`\p{...}` is in the language and the table is not.**  RFC 9485's
grammar includes the Unicode category escapes, which need a quarter of a
megabyte of table that a caller selecting `$.store.book[0].title` should
not carry.  So `jpregex.compile` refuses a pattern that uses one, by
name, and `jpregex.compile_with` takes the lookup as a `fn(Int) -> Str`
the caller supplies — unicode-nv's
`uclass.category_abbrev(uclass.category(data, ch))`, or two lines for a
caller that only cares about ASCII.  `jpeval.select_categorised` carries
it through the evaluator.  That is `docs/publishing.md` § *How a `core`
package takes a stream from its host*, applied to a table instead of to
a stream.

## What the standard library's JSON value cannot carry

This package selects over `std.json`'s value — `JsonValueH` — on
purpose: a second JSON value type in the assembly would mean every
caller converting a document before it could query it, and the documents
are already there, from `json.parse`, from an HTTP body, from `nq`.

What that costs, exactly, because the brief for this package was to say
so rather than to work around it:

**`{}` and `null` are the same value to every accessor.**  Both answer
zero keys and `None` from `to_str`, `to_int`, `to_float`, `to_bool` and
`to_list`.  Only `json.stringify` separates them, and that answers a
rendered document.  RFC 9535 § 2.4.4 makes `length()` the member count
for an object and **Nothing** for a non-container, so `length(@) == 0`
must be *true* for `{}` and *false* for `null` — and that is the one
place a correct evaluator cannot be written over this surface without
rendering every node it reaches.  `orbit/nq` already hit this: its
`eval.kind` assembles the six types from the typed accessors and falls
back to the rendering for exactly this pair, with a regression test
called `test_empty_object_is_not_null`.

**There is no deep equality.**  § 2.3.5.2.2 defines `==` structurally
over arrays and objects, with `1` and `1.0` equal and member order
irrelevant.  `stringify`-and-compare is wrong on both counts.  So
`jpeval.value_equals` and `jpeval.value_order` are public here — they
are the piece a caller is most likely to want on its own, and there is
no `json.equals` to defer to.

**Reaching one element of an array materialises all of it.**
`json.to_list` is the only way in, so element 5 of a 100,000-element
array costs the whole list, and a descendant walk pays that once per
array it visits.

**`std.json` is refused on the embedded tier and has no wasm runtime.**
So this package makes no device claim and does not run in a browser,
even though its own arithmetic would.

All four are filed against the toolchain as
`std-json-cannot-tell-an-empty-object-from-null-and-has-no-deep-equality`,
with `json.is_null`, `json.type_of` and `json.equals` as the smallest
things that would close them.  When they land, `jpeval.value_equals`
becomes a wrapper and `length()` becomes correct.

## What nq keeps, and what it would take from here

`orbit/nq` is the jq-style filter this package's evaluator is cut for.
The row on the grid says jsonquery-nv builds its evaluator on this; nq
is what jsonquery-nv comes out of, so it is worth being precise about
which half is which.

**nq keeps**, and none of it is JSONPath's business:

- the **CLI** — argv, `-r`, `-c`, `--tab`, several files or stdin, and
  an exit code that answers "did that match anything?" so a shell script
  can branch on it;
- the **pipes** — `.a | .b | select(...) | map(...)`, which is a jq
  program shape and not a path;
- the **renderers** — `src/table.nv`'s columns, the CSV in and out, the
  pretty printer;
- **jq's own rules where they differ from JSONPath's**: a missing field
  is `null` rather than nothing, indexing a non-container is an error,
  and `keys` answers an object's names sorted.  A user who knows jq must
  not have to relearn those, and its README says so.

**nq would take**, replacing code it has today:

- `jpquery.parse` and the typed query, in place of `src/query.nv`'s
  810-line hand-written parser — and would gain filters, slices,
  descendant segments and the function extensions, none of which it has;
- `jpeval.select` in place of the walk half of `src/eval.nv`;
- `jpeval.value_equals` and `jpeval.value_order` in place of its own
  `cmp_arr` / `cmp_obj` / `cmp_float` — which are already the same
  arithmetic;
- `jpeval.kind`-shaped type discovery — nq's `eval.kind` and this
  package's needs are the same six-way question over `std.json`, and
  the filing above is what closes it for both;
- `jpregex` in place of `std.regex` behind `~=` — which would be a
  **narrowing**, and a decision nq's owner has to make rather than a
  free upgrade: `~=` accepts PCRE today and I-Regexp has no `(?i)`.

What nq would *not* take is the pipe. A jq program is a sequence of
stages that transform a stream; a JSONPath query is one selection.  The
right shape is nq keeping its stage list and using a JSONPath query as
the path inside each stage — so `select(.users[?@.age > 30])` becomes
expressible, and `map`, `keys` and `length` stay nq's.

## The layer, and why

`core`.  A parse of a string the caller typed, and a walk over a value
the caller already holds.  No function declares an effect.  The
Unicode table `\p{...}` would need arrives as an argument rather than as
a dependency, for the same reason: a `core` package takes what it needs
from its host instead of reaching for it.

## The reference implementation

RFC 9535 itself, and `serde_json_path` (Rust, MIT) / `jsonpath-ng`
(Python, Apache-2.0) as the implementations to check against.  The
oracle is the **JSONPath Compliance Test Suite** — the community suite
the RFC's authors maintain, a list of queries and documents with the
exact node list each must produce.  `tests/jpeval_tests.nv` quotes
§ 1.5's own bookstore table so a reviewer can check the port against the
specification rather than against this package, and the whole suite
becomes a generated run when the bodies land.

## Status

| function | implemented |
| --- | --- |
| `jperror.fault`, `.kind_name`, `.message` | no |
| `jpquery.parse`, `.parse_singular`, `.is_singular`, `.render` | no |
| `jpquery.function_name`, `.function_named` | no |
| `jpquery.parameter_types`, `.result_type`, `.check_types` | no |
| `jpquery.depth`, `.has_descendant` | no |
| `jpeval.default_limits`, `.select`, `.select_with` | no |
| `jpeval.select_values`, `.select_paths`, `.select_one`, `.query` | no |
| `jpeval.select_categorised` | no |
| `jpeval.normalized_path`, `.name_step`, `.index_step` | no |
| `jpeval.path_steps`, `.at_path` | no |
| `jpeval.value_equals`, `.value_order`, `.value_comparable` | no |
| `jpregex.compile`, `.compile_with`, `.is_match`, `.search` | no |
| `jpregex.is_iregexp`, `.needs_categories`, `.unsupported_construct` | no |
