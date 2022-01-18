INSERT INTO tile_cache.tile (z, x, y, layer_id, tile, sources)
VALUES (
  %(z)s,
  %(x)s,
  %(y)s,
  (SELECT name FROM tile_cache.layer WHERE mosaic = %(mosaic)s),
  %(tile)s,
  %(sources)s
);