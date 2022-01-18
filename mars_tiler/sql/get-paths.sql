SELECT
  "path",
  coalesce(d.minzoom, m.minzoom) minzoom,
  coalesce(d.maxzoom, m.maxzoom) maxzoom,
  coalesce(d.rescale_range, m.rescale_range) rescale_range,
  d.mosaic
FROM imagery.dataset d
JOIN imagery.mosaic m
  ON d.mosaic = m.name
WHERE ST_Intersects(
    footprint,
    ST_Translate(
      ST_TileEnvelope(
        %(z)s, %(x)s, %(y)s,
        (SELECT bounds FROM imagery.tms WHERE name = 'mars_mercator')
      ),
      949900
    )
  )
  AND mosaic = ANY(%(mosaics)s)
ORDER BY maxzoom DESC