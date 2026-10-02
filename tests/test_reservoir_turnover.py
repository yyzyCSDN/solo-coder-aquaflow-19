import unittest

from aquaflow.reservoir.turnover import State, project_age, renewal_fraction
from aquaflow.workflow_rules import evaluate


class TurnoverTests(unittest.TestCase):
    def test_inflow_dominated(self):
        # Plenty of fresh inflow, little outflow: renewal must be driven by inflow.
        s = State(volume=100.0, inflow=100.0, outflow=4.0, age_hours=120.0)
        self.assertEqual(renewal_fraction(s, 1.0), 1.0)
        # Fully renewed volume: age is the midpoint age of the incoming water.
        self.assertEqual(project_age(s, 1.0), 0.5)

    def test_outflow_dominated(self):
        # Large outflow with negligible inflow must not look like renewal.
        s = State(volume=100.0, inflow=4.0, outflow=100.0, age_hours=120.0)
        self.assertAlmostEqual(renewal_fraction(s, 1.0), 0.04)
        self.assertAlmostEqual(project_age(s, 1.0), 116.18)

    def test_zero_volume(self):
        s = State(volume=0.0, inflow=10.0, outflow=0.0, age_hours=50.0)
        self.assertEqual(renewal_fraction(s, 5.0), 0.0)
        self.assertEqual(project_age(s, 5.0), 0)

    def test_negative_inputs_rejected(self):
        for kwargs in (
            dict(volume=-1.0, inflow=1.0, outflow=1.0, age_hours=1.0),
            dict(volume=1.0, inflow=-1.0, outflow=1.0, age_hours=1.0),
            dict(volume=1.0, inflow=1.0, outflow=-1.0, age_hours=1.0),
        ):
            with self.subTest(kwargs=kwargs):
                s = State(**kwargs)
                with self.assertRaises(ValueError):
                    project_age(s, 1.0)
                with self.assertRaises(ValueError):
                    renewal_fraction(s, 1.0)
        s = State(1.0, 1.0, 1.0, 1.0)
        with self.assertRaises(ValueError):
            project_age(s, -1.0)


class ReservoirAgeWorkflowTests(unittest.TestCase):
    def _payload(self, **state):
        base = dict(volume=100.0, inflow=0.0, outflow=0.0, age_hours=120.0)
        base.update(state)
        return {"state": base, "hours": 1.0, "max_age": 24.0}

    def test_inflow_dominated_decision(self):
        # Only the correct source (inflow) pulls projected age under the threshold.
        result = evaluate("reservoir_age", self._payload(inflow=100.0, outflow=4.0))
        self.assertEqual(result["decision"], "renew")
        self.assertAlmostEqual(result["value"], 0.5)
        self.assertEqual(result["evidence"]["renewal_fraction"], 1.0)

    def test_threshold_only_crossed_with_inflow(self):
        # Outflow-dominated case: the old outflow-based math would renew; the
        # correct inflow-based math must hold.
        outflow_dominated = evaluate("reservoir_age", self._payload(inflow=4.0, outflow=100.0))
        self.assertEqual(outflow_dominated["decision"], "hold")
        self.assertGreater(outflow_dominated["value"], 24.0)

        # Same state with the flows swapped: fresh inflow now crosses the threshold.
        inflow_dominated = evaluate("reservoir_age", self._payload(inflow=100.0, outflow=4.0))
        self.assertEqual(inflow_dominated["decision"], "renew")
        self.assertLessEqual(inflow_dominated["value"], 24.0)

    def test_outflow_dominated_decision(self):
        result = evaluate("reservoir_age", self._payload(inflow=4.0, outflow=100.0))
        self.assertEqual(result["decision"], "hold")
        self.assertAlmostEqual(result["evidence"]["renewal_fraction"], 0.04)

    def test_zero_volume_decision_and_evidence(self):
        result = evaluate("reservoir_age", self._payload(volume=0.0, age_hours=50.0))
        self.assertEqual(result["decision"], "renew")
        self.assertEqual(result["value"], 0)
        self.assertEqual(result["evidence"]["projected_age"], 0)
        self.assertEqual(result["evidence"]["renewal_fraction"], 0.0)

    def test_negative_inputs_rejected_end_to_end(self):
        with self.assertRaises(ValueError):
            evaluate("reservoir_age", self._payload(volume=-1.0))
        with self.assertRaises(ValueError):
            evaluate("reservoir_age", self._payload(inflow=-5.0))

    def test_prediction_present_in_audit_evidence(self):
        result = evaluate("reservoir_age", self._payload(inflow=100.0, outflow=4.0))
        evidence = result["evidence"]
        # The prediction must drive the decision and be recorded as audit evidence.
        self.assertEqual(evidence["projected_age"], result["value"])
        self.assertEqual(evidence["max_age"], 24.0)
        self.assertEqual(evidence["fresh_inflow"], 100.0)
        self.assertEqual(evidence["outflow"], 4.0)


if __name__ == "__main__":
    unittest.main()
