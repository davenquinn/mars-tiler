CREATE OR REPLACE FUNCTION
  imagery.tile_envelope(
    _x integer,
    _y integer,
    _z integer,
    _tms text = 'mars_mercator'
  ) RETURNS geometry(Polygon, 949900)
AS $$
  SELECT ST_Transform(
    ST_TileEnvelope(
      _z, _x, _y,
      (SELECT bounds FROM imagery.tms WHERE name = _tms)
    ),
    949900
  );
$$ LANGUAGE SQL;


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
      imagery.tile_envelope(_x, _y, _z, _tms)
    )
    AND mosaic = ANY(_mosaics)
    AND _z >= coalesce(d.minzoom, m.minzoom)-3
  -- First order by mosaic, then by maxzoom within each mosaic.
  ORDER BY array_position(_mosaics, m.name), maxzoom DESC;
$$ LANGUAGE SQL STABLE;

-- This currently only works for square tiles.
CREATE OR REPLACE FUNCTION imagery.tile_index(coord numeric, z integer, _tms text = 'mars_mercator')
RETURNS integer AS $$
DECLARE
  _tms_bounds geometry;
  _geom_bbox box2d;
  _tms_size numeric;
  _tile_size numeric;
BEGIN
  SELECT bounds FROM imagery.tms WHERE name = _tms INTO _tms_bounds;
  _tms_size := ST_XMax(_tms_bounds) - ST_XMin(_tms_bounds);
  _tile_size := _tms_size/(2^z);

  RETURN floor(coord/_tile_size)::integer;
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
  SELECT bounds FROM imagery.tms WHERE name = _tms INTO _tms_bounds;

  IF ST_Within(_geom, ST_Transform(_tms_bounds, ST_SRID(_geom))) THEN
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
      imagery.tile_index((ST_XMin(_geom_bbox)-ST_XMin(_tms_bounds))::numeric, t.zoom) xmin,
      imagery.tile_index((ST_YMax(_tms_bounds)-ST_YMin(_geom_bbox))::numeric, t.zoom) ymin,
      imagery.tile_index((ST_XMax(_geom_bbox)-ST_XMin(_tms_bounds))::numeric, t.zoom) xmax,
      imagery.tile_index((ST_YMax(_tms_bounds)-ST_YMax(_geom_bbox))::numeric, t.zoom) ymax
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


CREATE OR REPLACE FUNCTION imagery.parent_tile(_geom geometry, _tms text = 'mars_mercator')
RETURNS TABLE (
  x integer,
  y integer,
  z integer
) AS $$
  SELECT x, y, z FROM imagery.containing_tiles(_geom, _tms) LIMIT 1;
$$ LANGUAGE sql STABLE;

/** This function returns tile information for use in the API, all at once */
CREATE OR REPLACE FUNCTION imagery.get_tile_info(_x integer, _y integer, _z integer, _layers text[])
RETURNS TABLE (
	datasets jsonb,
	should_generate boolean,
	cached_tile bytea,
	content_type text
) AS $$
BEGIN
  RETURN QUERY
  WITH ds AS (
    SELECT row_to_json(imagery.get_datasets(_x, _y, _z, _layers)) _data
  ),
  ds1 AS (
    SELECT json_agg(ds._data) datasets FROM ds
  ),
  cached AS (
    SELECT
      tile,
      p.content_type
    FROM tile_cache.tile t
    JOIN tile_cache.profile p ON t.profile = p.name
    WHERE t.layers = _layers
      AND t.x = _x
      AND t.y = _y
      AND t.z = _z
    LIMIT 1
  )
  -- ), update_cache AS (
  --   UPDATE tile_cache.tile
  --     SET last_used = now()
  --   WHERE x = _x
  --     AND y = _y
  --     AND z = _z
  --     AND layers = _layers
  -- )
  SELECT
    ds1.datasets::jsonb,
    imagery.should_generate_tile(_x, _y, _z, _layers),
    c.tile::bytea,
    c.content_type::text	
  FROM ds1
  LEFT JOIN cached c ON true;
END;
$$ LANGUAGE plpgsql VOLATILE;