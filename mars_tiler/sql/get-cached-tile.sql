SELECT
  tile,
  sources,
  l.content_type,
  l.mosaic
FROM tile_cache.tile t
JOIN tile_cache.layer l
  ON t.layer_id = l.name
WHERE mosaic = %(mosaic)s
  AND z = %(z)s
  AND x = %(x)s
  AND y = %(y)s
  AND NOT stale
  AND coalesce(l.minzoom, 0) <= z
  AND z <= coalesce(l.maxzoom, 24)