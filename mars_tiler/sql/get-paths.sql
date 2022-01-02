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
    ST_SetSRID(ST_MakeEnvelope(:x1,:y1,:x2,:y2), 949900)
  )
  AND mosaic = ANY(:mosaics)
ORDER BY maxzoom DESC