"""Grid points for a map scan."""

import math


def point_in_polygon(lat, lon, polygon_coords):
    """Ray-cast test. polygon_coords is a list of [lat, lon] pairs."""
    if not polygon_coords or len(polygon_coords) < 3:
        return False

    inside = False
    j = len(polygon_coords) - 1
    for i in range(len(polygon_coords)):
        xi, yi = polygon_coords[i]
        xj, yj = polygon_coords[j]
        if ((yi > lon) != (yj > lon)) and (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def calculate_grid(bbox, spacing_km, polygon_coords=None):
    """
    Points inside the bounding box, optionally clipped to a polygon.
    Returns at most 100 points. spacing_km is the gap between points.
    """
    lat_center = (bbox['north'] + bbox['south']) / 2
    lat_deg_per_km = 1 / 110.574
    cos_lat = math.cos(math.radians(lat_center))
    if abs(cos_lat) < 1e-6:
        cos_lat = 1e-6
    lon_deg_per_km = 1 / (111.32 * abs(cos_lat))

    spacing_deg_lat = spacing_km * lat_deg_per_km
    spacing_deg_lon = spacing_km * lon_deg_per_km

    points = []
    lat = bbox['south']
    while lat <= bbox['north']:
        lon = bbox['west']
        while lon <= bbox['east']:
            if polygon_coords:
                if point_in_polygon(lat, lon, polygon_coords):
                    points.append((lat, lon))
            else:
                points.append((lat, lon))
            lon += spacing_deg_lon
        lat += spacing_deg_lat

    if len(points) > 100:
        step = len(points) / 100
        points = [points[int(i * step)] for i in range(100)]
    return points
