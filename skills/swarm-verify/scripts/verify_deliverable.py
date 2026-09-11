# -*- coding: utf-8 -*-
"""
verify_deliverable.py -- Mechanism 2: on-disk deliverable verification.

Completion is a property the COORDINATOR measures against the filesystem, not a
status a builder self-reports. A task is done only if its artifact survives an
escalating gate (pick the level that matches the task's stakes):

  exists -> non-empty(min-bytes) -> parses -> schema/required-fields
         -> provenance(anti-fabrication) -> sentinel(anti-truncation)
         -> content assertion(count matches the claim)

Existence/parse catch no-shows and truncation. They do NOT catch fabrication --
that needs provenance (the deliverable must embed the raw sources it claims to
have used) or an adversarial reader. Schema validates SHAPE, never truth.

Stdlib only (optional `jsonschema` used if importable -- never assumed, L004).
Windows-safe: `python`, ASCII output (L018).

Exit codes: 0 = PASS (all RUN checks passed), 1 = FAIL (>=1 required check failed).

Example:
  python verify_deliverable.py --file results/a.json \
      --min-bytes 20 --required-fields summary sources \
      --provenance-field sources --count-field sources --min-count 50
  python verify_deliverable.py --file report.md \
      --sentinel "<!-- END:7ab6978a -->" --expect-sections "## Findings" "## Sources"
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def detect_format(path, override):
    if override and override != "auto":
        return override
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return "json"
    if ext in (".md", ".markdown"):
        return "md"
    return "raw"


class Report(object):
    def __init__(self):
        self.checks = []
        self.failed = False

    def add(self, name, status, detail=""):
        self.checks.append({"check": name, "status": status, "detail": detail})
        if status == "fail":
            self.failed = True

    def render(self):
        tag = {"pass": "[PASS]", "fail": "[FAIL]", "skip": "[skip]"}
        lines = ["verdict: %s" % ("FAIL" if self.failed else "PASS")]
        for c in self.checks:
            line = "  %s %s" % (tag.get(c["status"], "[?]"), c["check"])
            if c["detail"]:
                line += " -- " + c["detail"]
            lines.append(line)
        return "\n".join(lines)


def verify(args):
    r = Report()
    path = args.file

    # 1. exists
    if not os.path.isfile(path):
        r.add("exists", "fail", "no file at %s" % path)
        return r  # cannot proceed
    r.add("exists", "pass", path)

    # 2. non-empty / min-bytes
    size = os.path.getsize(path)
    if size < args.min_bytes:
        r.add("min-bytes", "fail", "%d < %d bytes (truncated/empty?)" % (size, args.min_bytes))
    else:
        r.add("min-bytes", "pass", "%d bytes" % size)

    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except Exception as e:
        r.add("read", "fail", "unreadable: %s" % e)
        return r

    fmt = detect_format(path, args.format)
    obj = None

    # 3. parse
    if fmt == "json":
        try:
            obj = json.loads(text)
            r.add("parse-json", "pass")
        except Exception as e:
            r.add("parse-json", "fail", "invalid JSON: %s" % e)
            return r  # downstream JSON checks impossible
    else:
        r.add("parse-json", "skip", "format=%s" % fmt)

    # 4. required fields (JSON top-level, non-null)
    if args.required_fields:
        if isinstance(obj, dict):
            missing = [k for k in args.required_fields
                       if k not in obj or obj[k] is None]
            if missing:
                r.add("required-fields", "fail", "missing/null: %s" % missing)
            else:
                r.add("required-fields", "pass", str(args.required_fields))
        else:
            r.add("required-fields", "fail", "deliverable is not a JSON object")
    else:
        r.add("required-fields", "skip")

    # 4b. JSON Schema (optional lib; never assumed)
    if args.schema:
        try:
            with open(args.schema, "r", encoding="utf-8-sig") as fh:
                schema = json.load(fh)
            try:
                import jsonschema  # noqa
                jsonschema.validate(obj, schema)
                r.add("schema", "pass", os.path.basename(args.schema))
            except ImportError:
                # fallback: enforce schema's own "required" list only
                req = schema.get("required", []) if isinstance(schema, dict) else []
                miss = [k for k in req if not isinstance(obj, dict) or k not in obj]
                if miss:
                    r.add("schema", "fail", "required missing %s (jsonschema lib absent)" % miss)
                else:
                    r.add("schema", "pass", "required-only (jsonschema lib absent)")
            except Exception as e:
                r.add("schema", "fail", str(e))
        except Exception as e:
            r.add("schema", "fail", "cannot read schema: %s" % e)
    else:
        r.add("schema", "skip")

    # 5. provenance (anti-fabrication): the claimed-source field must be present
    # and non-empty -- you cannot have analyzed sources you did not record.
    if args.provenance_field:
        if isinstance(obj, dict) and obj.get(args.provenance_field):
            r.add("provenance", "pass", "%s present (n=%s)" % (
                args.provenance_field, _length(obj[args.provenance_field])))
        else:
            r.add("provenance", "fail",
                  "no/empty '%s' -- analysis claimed without recorded sources" % args.provenance_field)
    else:
        r.add("provenance", "skip")

    # 6. content assertion: count matches the claim ("analyzed N" -> N items)
    if args.count_field is not None and args.min_count is not None:
        n = _length(obj.get(args.count_field)) if isinstance(obj, dict) else None
        if n is None:
            r.add("count", "fail", "field '%s' absent/uncountable" % args.count_field)
        elif n < args.min_count:
            r.add("count", "fail", "%s has %d < required %d" % (args.count_field, n, args.min_count))
        else:
            r.add("count", "pass", "%s=%d >= %d" % (args.count_field, n, args.min_count))
    else:
        r.add("count", "skip")

    # 7. sentinel (anti-truncation): raw text must END with the completion marker
    if args.sentinel:
        if text.rstrip().endswith(args.sentinel.rstrip()):
            r.add("sentinel", "pass")
        else:
            r.add("sentinel", "fail", "missing end-sentinel -- file likely truncated mid-write")
    else:
        r.add("sentinel", "skip")

    # 7b. expected markdown sections present
    if args.expect_sections:
        miss = [s for s in args.expect_sections if s not in text]
        if miss:
            r.add("sections", "fail", "missing headings: %s" % miss)
        else:
            r.add("sections", "pass", str(args.expect_sections))
    else:
        r.add("sections", "skip")

    return r


def _length(v):
    try:
        return len(v)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Verify a deliverable on disk (mechanism 2).")
    ap.add_argument("--file", required=True, help="path to the deliverable")
    ap.add_argument("--format", default="auto", choices=["auto", "json", "md", "raw"])
    ap.add_argument("--min-bytes", type=int, default=1)
    ap.add_argument("--required-fields", nargs="*")
    ap.add_argument("--schema", help="path to a JSON Schema (uses jsonschema if installed)")
    ap.add_argument("--provenance-field", help="field that must hold the recorded sources")
    ap.add_argument("--count-field", help="field whose length must meet --min-count")
    ap.add_argument("--min-count", type=int)
    ap.add_argument("--sentinel", help="raw text must end with this completion marker")
    ap.add_argument("--expect-sections", nargs="*", help="substrings/headings that must be present")
    ap.add_argument("--json", action="store_true", help="emit machine JSON report")
    args = ap.parse_args()

    r = verify(args)
    if args.json:
        print(json.dumps({"file": args.file, "verdict": "FAIL" if r.failed else "PASS",
                          "checks": r.checks}, indent=2))
    else:
        print(r.render())
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
