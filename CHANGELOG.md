# Changelog

Every published version, newest first. This file is on the publish
allow-list, so it travels with the package: it is the only thing a
consumer deciding whether to upgrade can read.

## 0.0.1 — 2026-09-11

The **interface**, before anyone implements it.  Every signature, every
type and every effect row is published; every body is `todo()`, and the
release is stamped `NOT IMPLEMENTED — interface only`.  Adding this
package works and calling it panics.

- Four modules.  `jpquery` is the whole grammar as a typed value —
  filter expressions included, because RFC 9535's grammar is mutually
  recursive and a filter selector holds an expression that holds a
  query — `jpeval` runs one, `jpregex` is the pattern language the two
  function extensions use, and `jperror` is the one fault type.
- **Evaluation cannot fail, and nothing in `jpeval` answers a
  `Result`.**  RFC 9535 makes every runtime disagreement produce false
  or an empty nodelist: a string compared with a number is false, a
  pattern that is not I-Regexp is false, a selector that names nothing
  selects nothing.  Everything that can be wrong is wrong in the query,
  and the parse is where it is caught.  A resource bound truncates —
  `JpSelection.truncated` — rather than raising, because a walk that ran
  out of budget produced real nodes.
- **Every node carries its normalized path**, § 2.7's, quoted
  throughout.  `path_steps` and `at_path` turn a stored path back into a
  walk, so finding a location once and revisiting it later costs no
  second query; `select_values` and `select_paths` are there for a
  caller that wants only one half.
- **Well-typedness is checked at parse time** — § 2.4.3, the part
  implementations skip.  `length(@.*)` is not a query that answers
  nothing; it is not a query, because `@.*` is a `NodesType` and
  `length` takes a `ValueType`.  Seven rows of the README's table say
  which way each case goes, and `parameter_types` / `result_type` are
  § 2.4.2's table as data rather than as prose.
- **The pattern language is I-Regexp (RFC 9485) and only that**: no
  anchors, no backreferences, no lookaround, no lazy quantifiers, no
  captures.  Accepting a PCRE pattern would make a query work here and
  select different nodes on a conforming implementation across a wire.
  `unsupported_construct` names what a pattern used, so a tool can say
  why the pattern that works everywhere else does not work here.
- **`\p{...}` is in the language and the table is not.**  The Unicode
  general categories arrive as a `fn(Int) -> Str` the caller supplies —
  `compile_with`, and `select_categorised` to carry it through the
  evaluator — so a caller selecting `$.store.book[0].title` does not
  carry a quarter of a megabyte of table, and one that needs the escape
  and did not supply the lookup gets a named refusal.
- **The value is the standard library's**, and four things it cannot
  carry are written down rather than worked around: `{}` and `null` are
  the same value to every accessor, which is where § 2.4.4's `length()`
  cannot be answered; there is no deep equality, which is why
  `value_equals` and `value_order` are public here; reaching one array
  element materialises the whole array; and `std.json` is refused on the
  embedded tier and has no wasm runtime, so this package makes no device
  claim.  All four are filed against the toolchain.
- **No dependencies.**  Not a JSON package, because a second JSON value
  type would mean converting every document before querying it.  Not
  unicode-nv and not `std.regex`, for the two reasons above.

The oracle is the JSONPath Compliance Test Suite;
`tests/jpeval_tests.nv` quotes RFC 9535 § 1.5's own bookstore table so a
reviewer can check the port against the specification rather than
against this package.
