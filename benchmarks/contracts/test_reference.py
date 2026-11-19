"""Hand-specified development controls, separate from the held-out evaluation."""
import copy
import hashlib
import unittest
from tabular_reference import compare_document, nominal_only_document


def fixture():
    context = dict(baseline_id="baseline-v1", device="generic-demonstration", toolchain="manual",
                   tool_version="1", implementation="hand-specified", constraints_id="scope-v1",
                   timing_corner="structural-surrogate", workload_id="all-inputs", source_kind="synthetic_example")
    records = []
    for name, x, y in (("A", 1, 3), ("B", 2, 2), ("C", 3, 4)):
        records.append(dict(id=name, design="control", method=name, context=copy.deepcopy(context),
            metrics={key:dict(value=value, lower=value, upper=value, unit="abstract_cost",
                             denominator="absolute", uncertainty_kind="exact") for key,value in (("x",x),("y",y))},
            provenance=dict(source_uri="urn:radpareto:reference:hand-controls",
                            source_sha256=hashlib.sha256(b"A=(1,3);B=(2,2);C=(3,4)").hexdigest(),
                            locator=name, extraction="original hand-specified development control"),
            protection=dict(status="unverified",fault_model="not_tested",scope="cost-only",evidence_uri="not_available")))
    return dict(schema_version="1.0", records=records)


class ReferenceTests(unittest.TestCase):
    def test_nominal_tradeoff_and_constrained_front(self):
        result = compare_document(fixture(), limits={"x":2,"y":3})
        self.assertEqual(result["nominal_front"], ["A","B"])
        self.assertEqual(result["not_certainly_dominated"], ["A","B"])
        self.assertEqual(result["definitely_feasible_nominal_front"], ["A","B"])
        self.assertEqual(result["feasibility"]["C"]["status"], "definitely_infeasible")

    def test_unconstrained_feasibility_is_vacuous(self):
        result = compare_document(fixture())
        self.assertTrue(all(v["status"]=="definitely_feasible" for v in result["feasibility"].values()))
        self.assertEqual(result["definitely_feasible_nominal_front"], result["nominal_front"])

    def test_interval_overlap_retains_all(self):
        data = fixture()
        for record in data["records"]:
            for metric in record["metrics"].values():
                metric.update(lower=metric["value"]-1,upper=metric["value"]+1,uncertainty_kind="bounded")
        result = compare_document(data,limits={"x":2,"y":3})
        self.assertEqual(result["not_certainly_dominated"],["A","B","C"])
        self.assertTrue(all(v["status"]=="uncertain" for v in result["feasibility"].values()))
        self.assertEqual(result["definitely_feasible_nominal_front"],[])

    def test_exact_ties_survive(self):
        data = fixture()
        data["records"][1]["metrics"] = copy.deepcopy(data["records"][0]["metrics"])
        result = compare_document(data)
        self.assertEqual(result["nominal_front"],["A","B"])
        self.assertEqual(result["not_certainly_dominated"],["A","B"])

    def test_large_integer_values_not_rounded_by_dataframe(self):
        data=fixture()
        data["records"]=data["records"][:2]
        for record,value in zip(data["records"],(9007199254740993,9007199254740992)):
            for metric in record["metrics"].values():
                metric.update(value=value,lower=value,upper=value)
        self.assertEqual(compare_document(data)["nominal_front"],["B"])

    def test_every_context_mismatch_refused(self):
        for key in fixture()["records"][0]["context"]:
            data=fixture()
            data["records"][1]["context"][key]="simulation" if key=="source_kind" else "other"
            self.assertEqual(compare_document(data)["status"],"refused",key)

    def test_mixed_integer_float_limits_preserve_large_integer_boundary(self):
        data=fixture(); data["records"]=data["records"][:1]
        data["records"][0]["metrics"]["x"].update(value=9007199254740993,lower=9007199254740993,upper=9007199254740993)
        limits={"x":9007199254740993,"y":3.0}
        self.assertEqual(compare_document(data,limits=limits)["feasibility"]["A"]["status"],"definitely_feasible")
        self.assertTrue(nominal_only_document(data,limits=limits)["nominal_limit_compliance"]["A"])

    def test_matching_missing_context_not_evidence(self):
        for token in ("unknown","NOT AVAILABLE","not/report-ed","N/A"):
            data=fixture()
            for record in data["records"]:
                record["context"]["device"]=token
            self.assertEqual(compare_document(data)["status"],"refused",token)

    def test_metric_semantics_refused(self):
        for key,value in (("unit","nanoseconds"),("denominator","different baseline"),("uncertainty_kind","bounded")):
            data=fixture()
            data["records"][1]["metrics"]["x"][key]=value
            self.assertEqual(compare_document(data)["status"],"refused",key)

    def test_bad_structure_refused(self):
        changes=[lambda d:d.update(extra=1), lambda d:d.update(records=[]),
                 lambda d:d["records"][1].update(id="A"),
                 lambda d:d["records"][0]["metrics"]["x"].update(value=True),
                 lambda d:d["records"][0]["metrics"]["x"].update(value=float("nan")),
                 lambda d:d["records"][0]["metrics"]["x"].update(lower=2),
                 lambda d:d["records"][0]["provenance"].update(source_sha256="A"*64)]
        for change in changes:
            data=fixture();change(data)
            self.assertEqual(compare_document(data)["status"],"refused")

    def test_bad_limits_refused(self):
        for limits in ({"absent":1},{"x":True},{"x":-1},{"x":float("inf")},[]):
            self.assertEqual(compare_document(fixture(),limits=limits)["status"],"refused")

    def test_protection_gate_and_matching_evidence(self):
        data=fixture()
        self.assertEqual(compare_document(data,require_verified_protection=True)["status"],"refused")
        for record in data["records"]:
            record["protection"].update(status="verified_within_model",fault_model="abstract single bit flip",
                                        scope="specified fault sites",evidence_uri="urn:campaign:hand-control")
        self.assertEqual(compare_document(data,require_verified_protection=True)["status"],"accepted")
        data["records"][0]["protection"]["evidence_uri"]="not_available"
        self.assertEqual(compare_document(data,require_verified_protection=True)["status"],"refused")

    def test_protection_scope_mismatch_refused(self):
        data=fixture()
        for record in data["records"]:
            record["protection"].update(status="verified_within_model",fault_model="f",scope="s",evidence_uri="urn:e")
        data["records"][1]["protection"]["scope"]="different sites"
        self.assertEqual(compare_document(data,require_verified_protection=True)["status"],"refused")

    def test_ablation_intentionally_ignores_units_and_protection(self):
        data=fixture();data["records"][1]["metrics"]["x"]["unit"]="different units"
        result=nominal_only_document(data,require_verified_protection=True)
        self.assertEqual(result["status"],"accepted")
        self.assertEqual(result["nominal_front"],["A","B"])
        self.assertIsNone(result["not_certainly_dominated"])
        self.assertIsNone(result["feasibility"])

    def test_input_unchanged(self):
        data=fixture(); original=copy.deepcopy(data)
        compare_document(data,limits={"x":2})
        self.assertEqual(data,original)


if __name__=="__main__":
    unittest.main()
