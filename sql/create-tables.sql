CREATE EXTENSION postgis;

CREATE OR REPLACE TABLE mosaic AS (
  name text,
  minzoom integer,
  maxzoom integer
);

CREATE OR REPLACE TABLE dataset AS (
  id serial PRIMARY KEY,
  name text UNIQUE,
  path text UNIQUE,
  mosaic text REFERENCES mosaic(name),
  dtype text,
  footprint geometry(Polygon)
);
