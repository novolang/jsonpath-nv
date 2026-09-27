#!/usr/bin/env python3
"""Write tests/cts_tests.nv from the JSONPath Compliance Test Suite.

The suite is https://github.com/jsonpath-standard/jsonpath-compliance-test-suite,
BSD-2-Clause, at commit 9d1a415.  Its `cts.json` holds, for each case,
a query and either the fact that it is invalid, or a document with the
nodelist the query selects from it: the values and the normalized
paths, in order.  Where RFC 9535 leaves the order open, as it does for
an object's members, a case lists every order it accepts.

Each invalid query must be refused by `jpquery.parse`.  Each valid one
is run with `jpeval.select_categorised`, and the paths and the values
must be one of the accepted answers.  The category lookup is a table,
written by this tool with Python's `unicodedata`, of the code points
the category cases use.

Usage:
    python3 tools/cts.py <checkout> > tests/cts_tests.nv
    novo fmt tests/cts_tests.nv

With a second argument `report`, each case prints its name when it
fails instead of asserting, so a change can be reviewed against the
whole suite at once.
"""
import json
import os
import re
import sys
import unicodedata

# Cases left out, each with its reason.
LEFT_OUT = {
    # A novo-lang `Str` ends at a zero byte, so a query holding U+0000
    # cannot be written as one.
    "name selector, double quotes, embedded U+0000":
        "a Str cannot hold U+0000",
    "name selector, single quotes, embedded U+0000":
        "a Str cannot hold U+0000",
    # RFC 9485's grammar makes `^` and `$` ordinary characters
    # (`NormalChar` includes %x24 and %x5E), and the suite reads them as
    # anchors.
    "functions, match, explicit caret":
        "RFC 9485 makes ^ an ordinary character",
    "functions, match, explicit dollar":
        "RFC 9485 makes $ an ordinary character",
}

REPORT = len(sys.argv) > 2 and sys.argv[2] == "report"
GROUP = 40


def nv(s):
    """A novo-lang string literal."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '$':
            out.append('\\$')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif o < 0x20 or o == 0x7F:
            out.append('\\x%02x' % o)
        elif 0xD800 <= o <= 0xDFFF:
            out.append('\\u{%x}' % o)
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def doc_text(v):
    """A document as JSON text: every non-ASCII character as itself, and
    every control character as a `\\u` escape."""
    text = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    codes = {"\\\\": "\\\\", "\\b": "\\u0008", "\\f": "\\u000c"}
    return re.sub(r"\\\\|\\b|\\f", lambda m: codes[m.group(0)], text)


def main():
    root = sys.argv[1]
    tests = json.load(open(os.path.join(root, "cts.json")))["tests"]
    kept = [t for t in tests if t["name"] not in LEFT_OUT]
    cats = {}
    for t in kept:
        if "\\p" in t["selector"] or "\\P" in t["selector"]:
            for ch in json.dumps(t.get("document", ""), ensure_ascii=False):
                cats[ord(ch)] = unicodedata.category(ch)
    w = sys.stdout.write
    w("// cts_tests.nv — the JSONPath Compliance Test Suite.\n//\n")
    w("// Written by tools/cts.py from\n")
    w("// https://github.com/jsonpath-standard/jsonpath-compliance-test-suite at\n")
    w("// commit 9d1a415, BSD-2-Clause.  %d of its %d cases; the tool lists the\n" % (len(kept), len(tests)))
    w("// others with their reasons.\n\n")
    w("use std.test\nuse std.json\nuse std.list\nuse std.str\nuse jpquery\nuse jpeval\n\n")
    w("// The general categories of the code points the category cases use,\n")
    w("// from Python's unicodedata.\n")
    w("fn category(cp: Int) -> Str\n")
    for cp in sorted(cats):
        w("    if cp == %d\n        return %s\n" % (cp, nv(cats[cp])))
    w("    \"Cn\"\n\n")
    w("// Whether a query is refused.\n")
    w("fn refused(query: Str) -> Bool\n")
    w("    match jpquery.parse(query)\n")
    w("        Ok(_)  => false\n")
    w("        Err(_) => true\n\n")
    w("// Whether a query selects, from a document, one of the accepted\n")
    w("// nodelists: `values` a JSON array of the values, and `paths` the\n")
    w("// normalized paths joined with a line feed.\n")
    w("fn selects(query: Str, doc: Str, values: [Str], paths: [Str]) -> Bool\n")
    w("    let q = match jpquery.parse(query)\n")
    w("        Ok(x)  => x\n")
    w("        Err(_) => return false\n")
    w("    let d = json.parse(doc) ?? json.parse(\"null\")!\n")
    w("    let sel = jpeval.select_categorised(q, d, jpeval.default_limits(), category)\n")
    w("    var got: [Str] = []\n")
    w("    for n in sel.nodes\n")
    w("        list.push(got, n.path)\n")
    w("    let text = str.join(got, \"\\n\")\n")
    w("    var i = 0\n")
    w("    for want in paths\n")
    w("        if want == text and same_values(sel.nodes, values[i])\n")
    w("            return true\n")
    w("        i = i + 1\n")
    w("    false\n\n")
    w("// Whether the nodes' values are the elements of a JSON array.\n")
    w("fn same_values(nodes: [jpeval.JpNode], values: Str) -> Bool\n")
    w("    let want = json.parse(values) ?? json.parse(\"[]\")!\n")
    w("    if (json.len(want) ?? 0) != list.len(nodes)\n")
    w("        return false\n")
    w("    var i = 0\n")
    w("    for n in nodes\n")
    w("        let v = json.index(want, i) ?? json.parse(\"null\")!\n")
    w("        if not json.equals(n.value, v)\n")
    w("            return false\n")
    w("        i = i + 1\n")
    w("    true\n\n")
    if REPORT:
        w("fn check(name: Str, ok: Bool) [io]\n")
        w("    if not ok\n")
        w("        println(\"FAIL ${name}\")\n\n")
    for g in range(0, len(kept), GROUP):
        w("@test\nfn test_cts_%03d() [io]\n" % (g // GROUP))
        for t in kept[g:g + GROUP]:
            if t.get("invalid_selector"):
                expr = "refused(%s)" % nv(t["selector"])
            else:
                if "results" in t:
                    vals, paths = t["results"], t["results_paths"]
                else:
                    vals, paths = [t["result"]], [t["result_paths"]]
                vlist = "[" + ", ".join(nv(doc_text(v)) for v in vals) + "]"
                plist = "[" + ", ".join(nv("\n".join(p)) for p in paths) + "]"
                expr = "selects(%s, %s, %s, %s)" % (nv(t["selector"]), nv(doc_text(t["document"])), vlist, plist)
            if REPORT:
                w("    check(%s, %s)\n" % (nv(t["name"]), expr))
            else:
                w("    test.case(%s)\n" % nv(t["name"]))
                w("    test.assert(%s)\n" % expr)
        w("\n")


main()
