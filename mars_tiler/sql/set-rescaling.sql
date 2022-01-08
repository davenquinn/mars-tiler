/**
A draft query to set per-dataset rescaling.
Requires the info column to contain `gdalinfo` output as JSON.
*/
WITH band_info AS (
	SELECT
		path,
		mosaic,
		info -> 'bands' -> 0 band,
		info
	FROM imagery.dataset
)
UPDATE imagery.dataset d
SET
  rescale_range = ARRAY[
    coalesce(
      :min,
      band ->> 'min',
      band -> 'metadata' -> '' ->> 'STATISTICS_MINIMUM'
    )::numeric,
    coalesce(
      :max,
      band ->> 'max',
      band -> 'metadata' -> '' ->> 'STATISTICS_MAXIMUM'
    )::numeric
  ]
FROM band_info b
WHERE b.mosaic = :mosaic
  AND d.name LIKE '%'||:name||'%'
  AND b.path = d.path
