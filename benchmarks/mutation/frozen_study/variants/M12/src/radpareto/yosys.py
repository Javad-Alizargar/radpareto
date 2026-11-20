"""Strict importer for a small mapped-generic Yosys JSON subset.

The metrics are generic cell count and combinational logic levels, not silicon
area, time, power or fault coverage. MIT-licensed original RadPareto code.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

_GATES = {
    "$_BUF_": ("A",), "$_NOT_": ("A",),
    **{f"$_{g}_": ("A", "B") for g in ("AND", "NAND", "OR", "NOR", "XOR", "XNOR")},
    "$_MUX_": ("A", "B", "S"),
}
_FF = {"$_DFF_P_", "$_DFF_N_"}


def _summarize_yosys(data, top):
    """Return strict structural metrics; reject unsupported/ambiguous netlists."""
    if not isinstance(data, dict) or not isinstance(data.get("modules"), dict):
        raise ValueError("YOSYS_FORMAT: expected modules object")
    modules = data["modules"]
    if top not in modules:
        raise ValueError("YOSYS_TOP: top module is missing")
    sources, drivers, primitives = set(["0", "1"]), {}, []
    primary_sources = set(sources)
    aliases = {}
    hierarchy = Counter()

    def canonical(bit):
        while bit in aliases:
            bit = aliases[bit]
        return bit

    def alias(a, b):
        a, b = canonical(a), canonical(b)
        if a != b:
            root_sources = {canonical(bit) for bit in primary_sources}
            if a in root_sources and b in root_sources:
                raise ValueError("YOSYS_ALIAS: conflicting primary sources")
            if a in ("0", "1") and b in ("0", "1"):
                raise ValueError("YOSYS_ALIAS: conflicting constant aliases")
            if b in ("0", "1"):
                a, b = b, a
            aliases[b] = a

    def scalar_bit(bit, path, portmap):
        if isinstance(bit, bool) or not isinstance(bit, (int, str)):
            raise ValueError("YOSYS_BIT: invalid bit identifier")
        if isinstance(bit, str):
            if bit not in ("0", "1"):
                raise ValueError("YOSYS_UNKNOWN_BIT: x/z constants unsupported")
            return bit
        if bit < 0:
            raise ValueError("YOSYS_BIT: negative bit identifier")
        return portmap.get(bit, f"{path}:{bit}")

    def expand(name, path, portmap, ancestors):
        if name in ancestors:
            raise ValueError("YOSYS_RECURSION: recursive hierarchy")
        mod = modules[name]
        attrs = mod.get("attributes", {})
        if any(str(attrs.get(a, "0")).strip("0") for a in ("blackbox", "whitebox")):
            raise ValueError("YOSYS_BLACKBOX: cannot infer unknown implementation")
        if mod.get("memories") or mod.get("processes"):
            raise ValueError("YOSYS_UNMAPPED: memory/process unsupported")
        if not isinstance(mod.get("ports"), dict) or not isinstance(mod.get("cells"), dict):
            raise ValueError("YOSYS_FORMAT: missing ports/cells")
        for pname, port in mod["ports"].items():
            direction = port.get("direction")
            if direction not in ("input", "output"):
                raise ValueError("YOSYS_INOUT: inout/unknown direction unsupported")
            if not ancestors and direction == "input":
                sources.update(scalar_bit(b, path, portmap) for b in port["bits"])
                primary_sources.update(scalar_bit(b, path, portmap) for b in port["bits"])
        for cname, cell in mod["cells"].items():
            ctype = cell.get("type")
            connections = cell.get("connections", {})
            bits = {p: [scalar_bit(b, path, portmap) for b in bs] for p, bs in connections.items()}
            if ctype in modules:
                child = modules[ctype]
                if set(connections) != set(child.get("ports", {})):
                    raise ValueError("YOSYS_PORTS: hierarchy port mismatch")
                childmap = {}
                childdirections = {}
                for pname, port in child["ports"].items():
                    if len(port["bits"]) != len(bits[pname]):
                        raise ValueError("YOSYS_WIDTH: hierarchy width mismatch")
                    for childbit, parentbit in zip(port["bits"], bits[pname]):
                        if isinstance(childbit, str):
                            if childbit not in ("0", "1") or port["direction"] != "output":
                                raise ValueError("YOSYS_ALIAS: unsupported constant hierarchy port")
                            alias(childbit, parentbit)
                            continue
                        if isinstance(childbit, bool) or not isinstance(childbit, int) or childbit < 0:
                            raise ValueError("YOSYS_BIT: invalid child port identifier")
                        if childbit in childmap and childmap[childbit] != parentbit:
                            if port["direction"] == childdirections[childbit] == "input":
                                raise ValueError("YOSYS_ALIAS: shorted distinct hierarchy inputs")
                            alias(childmap[childbit], parentbit)
                        else:
                            childmap[childbit] = parentbit
                            childdirections[childbit] = port["direction"]
                hierarchy[ctype] += 1
                expand(ctype, f"{path}/{cname}", childmap, ancestors + (name,))
                continue
            ff = ctype in _FF
            if ctype not in _GATES and not ff:
                raise ValueError(f"YOSYS_CELL: unsupported cell {ctype}")
            output = "Q" if ff else "Y"
            inputs = ("C", "D") if ff else _GATES[ctype]
            expected = {**{p: "input" for p in inputs}, output: "output"}
            if cell.get("port_directions") != expected or set(bits) != set(expected):
                raise ValueError("YOSYS_DIRECTIONS: unexpected primitive ports")
            if any(len(bs) != 1 for bs in bits.values()):
                raise ValueError("YOSYS_WIDTH: generic primitives must be one bit")
            out = bits[output][0]
            if out in drivers or out in sources:
                raise ValueError("YOSYS_DRIVER: multiply driven signal")
            drivers[out] = f"{path}/{cname}"
            primitives.append((ctype, [bits[p][0] for p in inputs], out, ff))
            if ff:
                sources.add(out)

    expand(top, top, {}, ())
    primitives = [(t, [canonical(b) for b in inputs], canonical(out), ff) for t, inputs, out, ff in primitives]
    outputs = set(canonical(b) for b in primary_sources)
    for _, _, out, _ in primitives:
        if out in outputs:
            raise ValueError("YOSYS_DRIVER: aliased multiply driven signal")
        outputs.add(out)
    levels = {canonical(b): 0 for b in sources}
    pending = [p for p in primitives if not p[3]]
    while pending:
        progress, remaining = False, []
        for ctype, inputs, out, ff in pending:
            if all(b in levels for b in inputs):
                levels[out] = 1 + max(levels[b] for b in inputs)
                progress = True
            else:
                remaining.append((ctype, inputs, out, ff))
        if not progress:
            raise ValueError("YOSYS_GRAPH: combinational cycle or undriven signal")
        pending = remaining
    for _, inputs, _, _ in primitives:
        if any(b not in levels for b in inputs):
            raise ValueError("YOSYS_UNDRIVEN: input to primitive is undriven")
    for port in modules[top]["ports"].values():
        if port["direction"] == "output" and any(canonical(scalar_bit(b, top, {})) not in levels for b in port["bits"]):
            raise ValueError("YOSYS_UNDRIVEN: primary output is undriven")
    return {
        "cell_count": len(primitives),
        "logic_depth": max(levels.values(), default=0),
        "flip_flops": sum(p[3] for p in primitives),
        "cell_types": dict(sorted(Counter(p[0] for p in primitives).items())),
        "hierarchy_instances": dict(sorted(hierarchy.items())),
    }


def summarize_yosys(data, top):
    """Return metrics or a structured ValueError for unsupported JSON shapes."""
    try:
        return _summarize_yosys(data, top)
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError("YOSYS_FORMAT: malformed or excessively nested netlist") from exc


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("YOSYS_DUPLICATE_KEY: ambiguous JSON object")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("YOSYS_NONFINITE: nonfinite JSON number")


def import_yosys(path, *, top, record_id, design, method, context, source_uri=None):
    """Import already-synthesized JSON, retaining byte hash and caller context.

    Context truth is the caller's responsibility. Core evidence validation must
    still run before comparison. This adapter cannot infer physical conditions.
    """
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(10_000_001)
    if len(raw) > 10_000_000:
        raise ValueError("YOSYS_SIZE: report exceeds 10 MB")
    data = json.loads(raw, object_pairs_hook=_unique_keys, parse_constant=_invalid_constant)
    summary = summarize_yosys(data, top)
    if context.get("source_kind") != "synthesis":
        raise ValueError("YOSYS_SOURCE_KIND: require synthesis context")
    record = {
        "id": record_id, "design": design, "method": method,
        "context": dict(context),
        "metrics": {
            key: {"value": summary[key], "lower": summary[key], "upper": summary[key],
                  "unit": unit, "denominator": "absolute", "uncertainty_kind": "exact"}
            for key, unit in (("cell_count", "generic_cells"), ("logic_depth", "logic_levels"))
        },
        "provenance": {"source_uri": source_uri or path.as_posix(),
                       "source_sha256": hashlib.sha256(raw).hexdigest(),
                       "locator": f"modules.{top}; recursively expanded generic primitives",
                       "extraction": "radpareto.yosys strict generic importer v0.1"},
        "protection": {"status": "unverified", "fault_model": "not_tested",
                       "scope": "resource and logic-depth measurement only",
                       "evidence_uri": "not_available"},
    }
    return record, summary
