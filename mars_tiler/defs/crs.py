from pyproj import CRS

mars_radius = 3396190
MARS2000_SPHERE = CRS.from_dict({"proj": "longlat", "R": mars_radius, "no_defs": True})

MARS2000 = CRS.from_dict(
    {"proj": "longlat", "a": mars_radius, "b": 3376200, "no_defs": True}
)

MARS_MERCATOR = CRS.from_dict({"proj": "merc", "R": mars_radius, "no_defs": True})
MARS_MERCATOR.linear_units = "metre"
