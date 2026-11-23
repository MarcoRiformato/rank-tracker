import math
import unittest

from rank_tracker.grid import calculate_grid, point_in_polygon


class GridTests(unittest.TestCase):
    def test_point_in_square(self):
        square = [[0, 0], [0, 1], [1, 1], [1, 0]]
        self.assertTrue(point_in_polygon(0.5, 0.5, square))
        self.assertFalse(point_in_polygon(2, 2, square))
        self.assertFalse(point_in_polygon(0.5, 0.5, [[0, 0], [1, 1]]))

    def test_longitude_step_uses_cosine(self):
        bbox = {"north": 45.02, "south": 45.0, "east": 9.05, "west": 9.0}
        points = calculate_grid(bbox, 1)
        first_lat = points[0][0]
        lons = sorted({round(lon, 5) for lat, lon in points if abs(lat - first_lat) < 1e-9})
        self.assertGreaterEqual(len(lons), 2)
        step = lons[1] - lons[0]
        expected = 1 / (111.32 * math.cos(math.radians(45)))
        self.assertAlmostEqual(step, expected, places=4)

    def test_polygon_filter(self):
        bbox = {"north": 1, "south": 0, "east": 1, "west": 0}
        covering = [[0, 0], [0, 2], [2, 2], [2, 0]]
        points = calculate_grid(bbox, 50, covering)
        self.assertTrue(points)
        elsewhere = [[10, 10], [10, 11], [11, 11], [11, 10]]
        self.assertEqual(calculate_grid(bbox, 50, elsewhere), [])


if __name__ == "__main__":
    unittest.main()
