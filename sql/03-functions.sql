CREATE OR REPLACE FUNCTION
  imagery.get_datasets(
    _x integer,
    _y integer,
    _z integer,
    _mosaics text[],
    _tms text = 'mars_mercator'
  )
RETURNS TABLE (
  path text,
  mosaic text,
  minzoom integer,
  maxzoom integer,
  rescale_range numeric[],
  overscaled boolean
) AS $$
  SELECT
    "path",
    d.mosaic,
    coalesce(d.minzoom, m.minzoom) minzoom,
    coalesce(d.maxzoom, m.maxzoom) maxzoom,
    coalesce(d.rescale_range, m.rescale_range) rescale_range,
    _z > coalesce(d.maxzoom, m.maxzoom) overscaled
  FROM imagery.dataset d
  JOIN imagery.mosaic m
    ON d.mosaic = m.name
  WHERE ST_Intersects(
      footprint,
      ST_Transform(
        ST_TileEnvelope(
          _z, _x, _y,
          (SELECT bounds FROM imagery.tms WHERE name = _tms)
        ),
        949900
      )
    )
    AND mosaic = ANY(_mosaics)
    AND _z >= coalesce(d.minzoom, m.minzoom)-3
  ORDER BY maxzoom DESC;
$$ LANGUAGE SQL STABLE;

-- This currently only works for square tiles.
CREATE OR REPLACE FUNCTION imagery.tile_index(coord numeric, z integer, _tms text = 'mars_mercator') RETURNS integer AS $$
DECLARE
  _tms_bounds geometry;
  _geom_bbox box2d;
  _tms_size numeric;
  _tile_size numeric;
BEGIN
  _tms_bounds := ST_Transform((SELECT bounds FROM imagery.tms WHERE name = _tms), 949900);
  _tms_size := ST_XMax(_tms_bounds) - ST_XMin(_tms_bounds);
  _tile_size := _tms_size/(2^z);

  RETURN floor((coord-ST_XMin(_tms_bounds))/_tile_size)::integer;
END;
$$ LANGUAGE PLPGSQL STABLE;


/* We only want to generate tiles if there are some assets that are not overscaled */
CREATE OR REPLACE FUNCTION
  imagery.should_generate_tile(_x integer, _y integer, _z integer, layers text[])
RETURNS boolean AS $$
  WITH a AS (
    SELECT (imagery.get_datasets(_x, _y, _z, layers)).*
  )
  SELECT count(a) > 0
  FROM a
  WHERE NOT overscaled;
$$ LANGUAGE sql STABLE;


CREATE OR REPLACE FUNCTION imagery.containing_tiles(_geom geometry, _tms text = 'mars_mercator')
RETURNS TABLE (
  x integer,
  y integer,
  z integer
) AS $$
DECLARE
  _tms_bounds geometry;
  _geom_bbox box2d;
BEGIN
  _tms_bounds := ST_Transform((SELECT bounds FROM imagery.tms WHERE name = _tms), 949900);

  IF ST_Within(_geom, _tms_bounds) THEN
    _geom_bbox := ST_Transform(_geom, ST_SRID(_tms_bounds))::box2d;
  ELSE
    RETURN;
  END IF;

  RETURN QUERY
  WITH tile_sizes AS (
    SELECT
      a.zoom
    FROM generate_series(0, 24) AS a(zoom)
  ), tilebounds AS (
    SELECT t.zoom,
      imagery.tile_index(ST_XMin(_geom_bbox)::numeric, t.zoom) xmin,
      imagery.tile_index(ST_YMin(_geom_bbox)::numeric, t.zoom) ymin,
      imagery.tile_index(ST_XMax(_geom_bbox)::numeric, t.zoom) xmax,
      imagery.tile_index(ST_YMax(_geom_bbox)::numeric, t.zoom) ymax
    FROM tile_sizes t
  )
  SELECT
    t.xmin::integer x,
    t.ymin::integer y,
    t.zoom::integer z
  FROM tilebounds t
  WHERE t.xmin = t.xmax
    AND t.ymin = t.ymax
  ORDER BY z DESC;
END;  
$$ LANGUAGE plpgsql STABLE;
