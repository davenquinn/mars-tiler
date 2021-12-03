SELECT
  "path",
  mosaic,
  minzoom,
  maxzoom
FROM imagery.dataset
WHERE ST_Intersects(
    footprint,
    ST_SetSRID(ST_MakeEnvelope(:x1,:y1,:x2,:y2), 949900)
  )
ORDER BY maxzoom DESC