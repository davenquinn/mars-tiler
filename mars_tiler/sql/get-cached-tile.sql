WITH tile AS (
  SELECT (tile_cache.find_tile(%(x)s, %(y)s, %(z)s, %(mosaic)s)).*
)
SELECT
  CASE WHEN t.x = %(x)s AND t.y = %(y)s AND t.z = %(z)s THEN
    t.tile
  ELSE
    NULL
  END AS tile,
  t.tile IS NULL OR %(z)s > t.maxzoom AS should_return_null,
  t.sources,
  l.content_type,
  l.mosaic,
  t.maxzoom
FROM tile t
JOIN tile_cache.layer l
  ON t.layer_id = l.name;