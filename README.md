# Mars tiler

Mars Tiler is a prototype web application that serves tiles from cloud-optimized
GeoTIFFs, with an emphasis on supporting planetary datasets. Many features are
hard-coded for Mars data and global projections, but the core of this work
should be applicable to other planetary projections (e.g., Mars polar data, the Moon, Ceres, etc.).

## Dynamic tiling

This applicaion is part of a new generation of "dynamic tilers", which generates and slices mosaics on the fly
from input datasets. All it needs to function are a collection of cloud-optimized GeoTIFFs, and 
a database of footprints to decide which datasets to include for each tile. The datasets do not need to be
stored on the same server as the tiler code, opening the door to new distributed and cloud-based workflows.

This software is based on emerging software stacks for Earth observation, especially [TiTiler](https://developmentseed.org/titiler/).
It can produce tiles compatible
with a wide range of web GIS software. It is designed to support the [**Mars Lab**](https://github.com/davenquinn/Mars-Lab)
effort towards a flexible software backbone for Mars science GIS.

## Software dependencies

This project is based heavily on TiTiler and its dependenies Rasterio and Rio-Tiler. It modifies TiTiler to use a PostGIS database
backend for metadata storage  rather than MosaicJSON. This allows a simpler API and compatibility with other parts
of a typical GIS software stack (e.g., ArcGIS, QGIS, etc.), at some expense of scalability and deployment on cloud
workers.