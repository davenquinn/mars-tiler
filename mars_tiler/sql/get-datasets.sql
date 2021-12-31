SELECT 
 id,
 name,
 path,
 mosaic,
 dtype,
 'Feature' "type",
 ST_AsGeoJSON(ST_SetSRID(footprint, 0))::json geometry
FROM imagery.dataset
WHERE mosaic = any(:mosaic::text[])