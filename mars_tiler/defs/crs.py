from pyproj import CRS
import rasterio

mars_radius = 3396190
MARS2000_SPHERE = CRS.from_dict({"proj": "longlat", "R": mars_radius, "no_defs": True})
MARS2000_SPHERE = CRS.from_wkt(
    """GEOGCRS["unknown",
    DATUM["Mars_2000_(Sphere)",
        ELLIPSOID["Mars_2000_Sphere_IAU_IAG",3396190,0,
            LENGTHUNIT["metre",1,
                ID["EPSG",9001]]]],
    PRIMEM["Reference meridian",0,
        ANGLEUNIT["degree",0.0174532925199433,
            ID["EPSG",9122]]],
    CS[ellipsoidal,2],
        AXIS["longitude",east,
            ORDER[1],
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]],
        AXIS["latitude",north,
            ORDER[2],
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]]]"""
)


MARS2000 = CRS.from_dict(
    {"proj": "longlat", "a": mars_radius, "b": 3376200, "no_defs": True}
)

MARS_MERCATOR = CRS.from_dict({"proj": "merc", "R": mars_radius, "no_defs": True})
MARS_MERCATOR.linear_units = "metre"

mars_mercator_wkt = """PROJCRS["Mars 2000 / Pseudo-Mercator",
    BASEGEOGCRS["GCS_Mars_2000_Sphere",
        DATUM["Mars_2000_(Sphere)",
            ELLIPSOID["Mars_2000_Sphere_IAU_IAG",3396190,0,
                LENGTHUNIT["metre",1]]],
        PRIMEM["Reference_Meridian",0,
            ANGLEUNIT["Degree",0.0174532925199433]]],
    CONVERSION["unnamed",
        METHOD["Mercator (variant A)",
            ID["EPSG",9804]],
        PARAMETER["Latitude of natural origin",0,
            ANGLEUNIT["degree",0.0174532925199433],
            ID["EPSG",8801]],
        PARAMETER["Longitude of natural origin",0,
            ANGLEUNIT["Degree",0.0174532925199433],
            ID["EPSG",8802]],
        PARAMETER["Scale factor at natural origin",1,
            SCALEUNIT["unity",1],
            ID["EPSG",8805]],
        PARAMETER["False easting",0,
            LENGTHUNIT["metre",1],
            ID["EPSG",8806]],
        PARAMETER["False northing",0,
            LENGTHUNIT["metre",1],
            ID["EPSG",8807]]],
    CS[Cartesian,2],
        AXIS["x",east,
            ORDER[1],
            LENGTHUNIT["metre",1]],
        AXIS["y",north,
            ORDER[2],
            LENGTHUNIT["metre",1]]
    ]"""

MARS_MERCATOR = CRS.from_wkt(mars_mercator_wkt)

MARS_EQC = CRS.from_dict(
    dict(
        proj="eqc",
        lat_ts=0,
        lat_0=0,
        lon_0=180,
        x_0=0,
        y_0=0,
        R=mars_radius,
        units="m",
        no_defs=True,
    )
)
