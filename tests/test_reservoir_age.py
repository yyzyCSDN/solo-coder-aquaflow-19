"""Reservoir water-age projection must be driven by fresh inflow, end to end.

The renewal fraction comes from fresh inflow only; outflow merely changes the
operating background.  These tests exercise the cross-module path
(workflow_models -> workflow_rules -> reservoir.turnover -> workflow_service)
and the domain guards directly.
"""
import unittest

from aquaflow.api import AquaFlowService
from aquaflow.reservoir.turnover import State, project_age


def run(state, hours, max_age=24):
    payload = {"state": state, "hours": hours, "max_age": max_age}
    return AquaFlowService().run_workflow("reservoir_age", payload)


class ReservoirAgeWorkflowTest(unittest.TestCase):
    def test_inflow_dominated_renews(self):
        # Fresh inflow replaces the full volume, so the projected age drops.
        result = run({"volume": 100, "inflow": 60, "outflow": 10, "age_hours": 30}, 10)
        self.assertEqual(result["decision"], "renew")
        self.assertAlmostEqual(result["value"], 5.0)

    def test_outflow_dominated_holds(self):
        # Heavy outflow with little inflow must not refresh the tank:
        # the water keeps aging and the tank cannot continue operating.
        result = run({"volume": 100, "inflow": 2, "outflow": 60, "age_hours": 30}, 10)
        self.assertEqual(result["decision"], "hold")
        self.assertAlmostEqual(result["value"], 33.0)

    def test_zero_volume(self):
        result = run({"volume": 0, "inflow": 10, "outflow": 5, "age_hours": 12}, 3)
        self.assertEqual(result["decision"], "renew")
        self.assertEqual(result["value"], 0)

    def test_threshold_crossed_only_with_inflow_source(self):
        # Inflow-driven renewal (0.2) projects age 25 > max_age 24 -> hold.
        # The legacy outflow-driven renewal (1.0) would project 5 -> renew,
        # so only the correct renewal source crosses the threshold.
        state = {"volume": 100, "inflow": 2, "outflow": 40, "age_hours": 20}
        result = run(state, 10, max_age=24)
        self.assertEqual(result["decision"], "hold")
        self.assertAlmostEqual(result["value"], 25.0)

    def test_threshold_crossed_only_with_inflow_source_renew_side(self):
        # Mirror case: inflow-driven renewal (1.0) projects 5 <= 24 -> renew,
        # while outflow-driven renewal (0.2) would project 25 -> hold.
        state = {"volume": 100, "inflow": 40, "outflow": 2, "age_hours": 20}
        result = run(state, 10, max_age=24)
        self.assertEqual(result["decision"], "renew")
        self.assertAlmostEqual(result["value"], 5.0)

    def test_prediction_enters_decision_and_evidence(self):
        result = run({"volume": 100, "inflow": 2, "outflow": 40, "age_hours": 20}, 10, max_age=24)
        self.assertEqual(result["evidence"]["projected_age"], result["value"])
        self.assertEqual(result["evidence"]["max_age"], 24.0)
        self.assertEqual(result["evidence"]["fresh_inflow"], 2.0)
        self.assertEqual(result["evidence"]["renewal_source"], "inflow")
        self.assertEqual(result["audit"]["contract"], "v1")


class ProjectAgeGuardsTest(unittest.TestCase):
    def test_negative_volume_rejected(self):
        with self.assertRaises(ValueError):
            project_age(State(-1, 10, 5, 12), 3)

    def test_negative_inflow_rejected(self):
        with self.assertRaises(ValueError):
            project_age(State(100, -1, 5, 12), 3)

    def test_negative_outflow_rejected(self):
        with self.assertRaises(ValueError):
            project_age(State(100, 10, -5, 12), 3)

    def test_negative_hours_rejected(self):
        with self.assertRaises(ValueError):
            project_age(State(100, 10, 5, 12), -3)

    def test_zero_volume_returns_zero(self):
        self.assertEqual(project_age(State(0, 10, 5, 12), 3), 0)


if __name__ == "__main__":
    unittest.main()
