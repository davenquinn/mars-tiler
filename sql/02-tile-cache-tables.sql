CREATE SCHEMA tile_cache;

CREATE TABLE IF NOT EXISTS tile_cache.profile (
  name text NOT NULL PRIMARY KEY,
  format text NOT NULL,
  content_type text NOT NULL,
  minzoom integer,
  maxzoom integer
);

/* We need to add a TMS column to support non-mercator tiles */
CREATE TABLE IF NOT EXISTS tile_cache.tile (
  x integer NOT NULL,
  y integer NOT NULL,
  z integer NOT NULL,
  layers text[] NOT NULL,
  profile text NOT NULL REFERENCES tile_cache.profile(name),
  tile bytea NOT NULL,
  created timestamp without time zone NOT NULL DEFAULT now(),
  last_used timestamp without time zone NOT NULL DEFAULT now(),
  has_children boolean,
  PRIMARY KEY (x, y, z, layers)
);


/* Functions to find cached tiles
 This one finds parents and can perhaps be used for upscaling in the future.
*/
/*
CREATE OR REPLACE FUNCTION
  tile_cache.find_parent_tile(_x integer, _y integer, _z integer, _layers text)
RETURNS tile_cache.tile AS $$
SELECT
	x,
	y,
	z,
	t.layers,
  -- If tile is null that means that the tile should not be cached.
	CASE WHEN _z <= t.maxzoom THEN
		tile
	ELSE
		null
	END AS tile,
	t.created,
  t.last_used,
	t.maxzoom,
	t.sources
FROM tile_cache.tile t
JOIN tile_cache.profile p
  ON t.profile= p.name
WHERE layers = _layers
  AND _z-t.z >= 0
  -- Ensure we are within zoom of the layer
  AND coalesce(p.minzoom, 0) <= z
  AND z <= coalesce(p.maxzoom, 24)
  AND _x >= t.x*power(2, _z-t.z)
  AND _x < (t.x+1)*power(2, _z-t.z)
  AND _y >= t.y*power(2,_z-t.z)
  AND _y < (t.y+1)*power(2,_z-t.z)
  AND _x >= 0
  AND _x < power(2,_z)
  AND _y >= 0
  AND _y < power(2,_z)
ORDER BY z DESC
LIMIT 1;
$$ LANGUAGE SQL IMMUTABLE;
*/

INSERT INTO tile_cache.profile (name, format, content_type, minzoom, maxzoom)
SELECT 'mars_imagery', 'png', 'image/png', 0, 18
ON CONFLICT DO NOTHING;


