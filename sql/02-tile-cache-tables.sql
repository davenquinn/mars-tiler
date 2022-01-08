CREATE SCHEMA tile_cache;

CREATE TABLE IF NOT EXISTS tile_cache.layer (
  name text PRIMARY KEY,
  format text NOT NULL,
  content_type text NOT NULL,
  minzoom number,
  maxzoom number,
);

CREATE TABLE IF NOT EXISTS tile_cache.tile (
  z integer NOT NULL,
  x integer NOT NULL,
  y integer NOT NULL,
  layer_id integer NOT NULL REFERENCES tile_cache.layer(id),
  tile bytea,
  created timestamp without time zone DEFAULT now(),
  stale boolean,
  sources text[],
  PRIMARY KEY (z, x, y, layer_id),
);

-- Link our tile cache to the tiler
ALTER TABLE tile_cache.layer
ADD COLUMN mosaic text REFERENCES imagery.mosaic(name);

INSERT INTO tile_cache.layer (name, format, content_type, mosaic)
SELECT name, 'png', 'image/png', name
ON CONFLICT DO NOTHING;


