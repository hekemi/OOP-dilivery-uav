import unittest

from simulation import Point, SimulationConfig, manhattan_distance, optimize_deliveries, run_simulation


class SimulationTests(unittest.TestCase):
    def test_manhattan_distance(self):
        self.assertEqual(manhattan_distance(Point(1, 2), Point(4, 6)), 7)

    def test_reproducibility(self):
        config = SimulationConfig(seed=7)
        first = run_simulation(config)
        second = run_simulation(config)
        self.assertEqual(first.generated_count, second.generated_count)
        self.assertEqual(first.delivered_count, second.delivered_count)
        self.assertEqual(first.total_distance_km, second.total_distance_km)

    def test_range_constraint_never_exceeds_limit(self):
        result = run_simulation(SimulationConfig(seed=4, max_range_km=10, charge_hours=1))
        self.assertTrue(all(item["distance_km"] <= 10 for item in result.timeline))

    def test_optimization_respects_limits(self):
        config, result = optimize_deliveries(SimulationConfig(seed=3), 2, 3, 2)
        self.assertLessEqual(config.drones, 2)
        self.assertLessEqual(config.speed_kmh, 3)
        self.assertLessEqual(config.capacity, 2)
        self.assertGreaterEqual(result.delivered_count, 0)


if __name__ == "__main__":
    unittest.main()
