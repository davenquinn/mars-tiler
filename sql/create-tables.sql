CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS imagery;

INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text)
VALUES (
  949900,
  'IAU',
  949900,
  'GEOGCS["GCS_Mars_2000_Sphere",DATUM["Mars_2000_(Sphere)",SPHEROID["Mars_2000_Sphere_IAU_IAG",3396190,0],AUTHORITY["ESRI","106971"]],PRIMEM["Reference_Meridian",0],UNIT["Degree",0.0174532925199433],AXIS["Longitude",EAST],AXIS["Latitude",NORTH]]")',
  '+proj=longlat +R=3396190 +no_defs'
) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS imagery.mosaic (
  name text PRIMARY KEY,
  minzoom integer,
  maxzoom integer
);

CREATE TABLE IF NOT EXISTS imagery.dataset (
  id serial PRIMARY KEY,
  name text UNIQUE,
  path text UNIQUE,
  mosaic text REFERENCES imagery.mosaic(name),
  minzoom integer,
  maxzoom integer,
  dtype text,
  footprint geometry(Polygon, 949900)
);

CREATE INDEX imagery_dataset_footprint_idx
 ON imagery.dataset USING GIST (footprint);