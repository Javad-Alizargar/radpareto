import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from radpareto.yosys import summarize_yosys, import_yosys


def gate(kind, ins, out):
    inputs = {k: [v] for k, v in ins.items()}
    output = "Q" if kind.startswith("$_DFF") else "Y"
    return {"type": kind, "connections": dict(inputs, **{output: [out]}),
            "port_directions": dict.fromkeys(inputs, "input") | {output: "output"}}


def network():
    return {"modules": {"top": {"ports": {"a": {"direction":"input", "bits":[2]},
        "b": {"direction":"input", "bits":[3]}, "y": {"direction":"output", "bits":[5]}},
        "cells": {"and": gate("$_AND_", {"A":2,"B":3},4), "not":gate("$_NOT_",{"A":4},5)}}}}


class ImportTests(unittest.TestCase):
    def test_hand_counted_two_levels(self):
        s = summarize_yosys(network(), "top")
        self.assertEqual((s["cell_count"], s["logic_depth"], s["flip_flops"]), (2,2,0))

    def test_register_boundary_breaks_feedback(self):
        n=network(); m=n["modules"]["top"]
        m["cells"]={"not":gate("$_NOT_",{"A":5},4),"q":gate("$_DFF_P_",{"C":2,"D":4},5)}
        s=summarize_yosys(n,"top")
        self.assertEqual((s["cell_count"],s["logic_depth"],s["flip_flops"]),(2,1,1))

    def test_pure_combinational_cycle_rejected(self):
        n=network(); n["modules"]["top"]["cells"]["and"]["connections"]["A"]=[5]
        with self.assertRaisesRegex(ValueError,"YOSYS_GRAPH"):
            summarize_yosys(n,"top")

    def test_unknown_cell_rejected(self):
        n=network(); n["modules"]["top"]["cells"]["and"]["type"]="$mul"
        with self.assertRaisesRegex(ValueError,"YOSYS_CELL"):
            summarize_yosys(n,"top")

    def test_blackbox_rejected(self):
        n=network(); n["modules"]["top"]["attributes"]={"blackbox":"0001"}
        with self.assertRaisesRegex(ValueError,"YOSYS_BLACKBOX"):
            summarize_yosys(n,"top")

    def test_unknown_input_rejected(self):
        n=network(); n["modules"]["top"]["cells"]["and"]["connections"]["B"]=["x"]
        with self.assertRaisesRegex(ValueError,"YOSYS_UNKNOWN_BIT"):
            summarize_yosys(n,"top")

    def test_undriven_output_rejected(self):
        n=network(); n["modules"]["top"]["ports"]["y"]["bits"]=[42]
        with self.assertRaisesRegex(ValueError,"YOSYS_UNDRIVEN"):
            summarize_yosys(n,"top")

    def test_multiple_drivers_rejected(self):
        n=network(); n["modules"]["top"]["cells"]["not"]["connections"]["Y"]=[4]
        with self.assertRaisesRegex(ValueError,"YOSYS_DRIVER"):
            summarize_yosys(n,"top")

    def test_hierarchy_counts_instances(self):
        n=network(); n["modules"]["leaf"]=n["modules"].pop("top")
        n["modules"]["top"]={"ports":{"a":{"direction":"input","bits":[2]},"b":{"direction":"input","bits":[3]},"y":{"direction":"output","bits":[4,5]}},
            "cells":{str(i):{"type":"leaf","connections":{"a":[2],"b":[3],"y":[i]}} for i in (4,5)}}
        s=summarize_yosys(n,"top")
        self.assertEqual(s["hierarchy_instances"],{"leaf":2})
        self.assertEqual(s["cell_count"],4)
        self.assertEqual(s["logic_depth"],2)

    def test_import_preserves_hash_and_surrogate_units(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"n.json"; p.write_text(json.dumps(network()))
            r,s=import_yosys(p,top="top",record_id="x",design="x",method="base",context={"source_kind":"synthesis"},source_uri="example/n.json")
            self.assertEqual(len(r["provenance"]["source_sha256"]),64)
            self.assertEqual(r["metrics"]["logic_depth"]["unit"],"logic_levels")
            self.assertEqual(r["protection"]["status"],"unverified")

    def test_hierarchy_repeated_output_alias(self):
        n=network(); leaf=n["modules"].pop("top")
        leaf["ports"]["y"]["bits"]=[5,5]
        n["modules"]["leaf"]=leaf
        n["modules"]["top"]={"ports":{"a":{"direction":"input","bits":[2]},"b":{"direction":"input","bits":[3]},"y":{"direction":"output","bits":[4,5]}},
            "cells":{"child":{"type":"leaf","connections":{"a":[2],"b":[3],"y":[4,5]}}}}
        self.assertEqual(summarize_yosys(n,"top")["logic_depth"],2)

    def test_malformed_shapes_become_valueerror(self):
        for n in ([], {"modules":{"top":[]}}, {"modules":{"top":{"ports":{},"cells":[]}}}):
            with self.subTest(n=n), self.assertRaises(ValueError):
                summarize_yosys(n,"top")

    def test_hierarchy_constant_output(self):
        n={"modules":{"top":{"ports":{"y":{"direction":"output","bits":[2]}},"cells":{"child":{"type":"zero","connections":{"y":[2]}}}},
            "zero":{"ports":{"y":{"direction":"output","bits":["0"]}},"cells":{}}}}
        s=summarize_yosys(n,"top")
        self.assertEqual((s["cell_count"],s["logic_depth"]),(0,0))

    def test_constant_hierarchy_output_cannot_drive_input(self):
        n={"modules":{"top":{"ports":{"a":{"direction":"input","bits":[2]}},"cells":{"child":{"type":"zero","connections":{"y":[2]}}}},
            "zero":{"ports":{"y":{"direction":"output","bits":["0"]}},"cells":{}}}}
        with self.assertRaisesRegex(ValueError,"YOSYS_ALIAS"):
            summarize_yosys(n,"top")

    def test_nonfinite_and_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"n.json"
            for text, code in (("{\"modules\":{},\"modules\":{}}","YOSYS_DUPLICATE_KEY"),("{\"x\":NaN}","YOSYS_NONFINITE")):
                p.write_text(text)
                with self.subTest(code=code), self.assertRaisesRegex(ValueError,code):
                    import_yosys(p,top="top",record_id="x",design="x",method="x",context={"source_kind":"synthesis"})


if __name__ == "__main__":
    unittest.main()
