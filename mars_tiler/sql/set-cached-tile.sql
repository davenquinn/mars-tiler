INSERT INTO tile_cache.tile (x, y, z, layer_id, tile, sources, maxzoom)
VALUES (
  %(x)s,
  %(y)s,
  %(z)s,
  (SELECT name FROM tile_cache.layer WHERE mosaic = %(mosaic)s),
  %(tile)s,
  %(sources)s,
  %(maxzoom)s
)
ON CONFLICT (x,y,z,layer_id)
DO UPDATE
SET 
  tile = EXCLUDED.tile,
  sources = EXCLUDED.sources,
  maxzoom = EXCLUDED.maxzoom,
  created = now();