"""Extract and process WorldPop population raster data for West Bengal:
clip the national raster to the state boundary, then compute zonal population
sums and density for each district and block boundary."""

import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterstats import zonal_stats
from rasterio.warp import calculate_default_transform, reproject, Resampling

from ev_infra.config import DATA_PROCESSED, RAW_POPULATION_TIF
from ev_infra.preprocess.boundaries import (
    WEST_BENGAL_GEOJSON, WB_BLOCKS_DISTRICTS_GEOJSON, WB_DISTRICTS_GEOJSON,
)

# Define the directories for the storing the processed data
WB_POPULATION_TIF = DATA_PROCESSED / "west_bengal_pop.tif"
WB_BLOCKS_POP_GEOJSON = DATA_PROCESSED / "west-bengal-blocks-pop.geojson"
WB_DISTRICTS_POP_GEOJSON = DATA_PROCESSED / "west-bengal-districts-pop.geojson"


def extract_west_bengal_population_raster(
    west_bengal_boundary_path=WEST_BENGAL_GEOJSON,
    raw_population_tif=RAW_POPULATION_TIF,
    output_path=WB_POPULATION_TIF,
):
    """Clip the national WorldPop population raster to the West Bengal boundary and write it out."""
    west_bengal = gpd.read_file(west_bengal_boundary_path)

    with rasterio.open(raw_population_tif) as raster:
        # Define the transform and new dimensions for reprojecting
        transform, width, height = calculate_default_transform(
            raster.crs, 'EPSG:4326', raster.width, raster.height, *raster.bounds)

        # Create an array to hold the reprojected data
        reprojected_data = np.empty((height, width), dtype=np.float32)

        # Reproject the raster to EPSG:4326
        reproject(
            source=raster.read(1),
            destination=reprojected_data,
            src_transform=raster.transform,
            src_crs=raster.crs,
            dst_transform=transform,
            dst_crs='EPSG:4326',
            resampling=Resampling.nearest)

        # Create a clip of only population data for West Bengal using a mask
        west_bengal_pop, west_bengal_transform = mask(raster, west_bengal.geometry, crop=True)

    # Write out extracted West Bengal population data as new tiff file
    with rasterio.open(
        output_path, 
        "w", 
        driver="GTiff",
        height=west_bengal_pop.shape[1], 
        width=west_bengal_pop.shape[2],
        count=1, 
        dtype=west_bengal_pop.dtype,
        crs="EPSG:4326", 
        transform=west_bengal_transform,
    ) as dst:
        dst.write(west_bengal_pop[0], 1)

    return output_path

# Compute West Bengal population statistics
def population_raster_process(imagefile, bndy_shp):
    """Compute total population and population density for each polygon in bndy_shp
    from a population raster, via zonal statistics."""

    # Open the raster file
    with rasterio.open(imagefile, mode="r") as raster:
        pop, pop_transform = mask(raster, bndy_shp.geometry, nodata=-99999, crop=True)

    # Ensure data is a 2D array; change to 2D array for zonal stats processing
    pop_array = pop[0] if pop.ndim > 2 else pop

    # Check to see if there is no valid raster day for the boundary shape file
    if pop_array is None or pop_array.size == 0:
        print("Warning: No valid raster data for the polygon.")

    # Calculate the total population within each boundary
    total_pop = zonal_stats(bndy_shp, pop_array, affine=pop_transform,
                             stats="sum", geojson_out=True, nodata=-99999)

    # Create a geodataframe for the total population for each village
    df_pop_process = gpd.GeoDataFrame.from_features(total_pop)
    df_pop_process = df_pop_process.rename(columns={"sum": "total_pop"})
    df_pop_process = df_pop_process.drop(
        columns=["shapeType_left", "shapeType_right"], errors="ignore"
    )

     # Set CRS of GeoDataframe to EPSG:4326
    df_pop_process = df_pop_process.set_crs(epsg=4326, inplace=True)

    # Population density requires a projected (metric) CRS for area calculation.
    df_pop_process = df_pop_process.to_crs(epsg=3857)
    df_pop_process["pop_den"] = df_pop_process["total_pop"] / (df_pop_process["geometry"].area / 10**6)
    # Re-project back to EPSG:4326
    df_pop_process = df_pop_process.to_crs(epsg=4326)

    return df_pop_process


def process_block_district_population(
    population_tif,
    wb_blocks_districts_path=WB_BLOCKS_DISTRICTS_GEOJSON,
    wb_districts_path=WB_DISTRICTS_GEOJSON,
) -> dict:
    """Compute block- and district-level population from the clipped population raster
    and write both out as GeoJSON."""

    # Read in block and district geojson files
    wb_blocks_districts = gpd.read_file(wb_blocks_districts_path)
    wb_districts = gpd.read_file(wb_districts_path)

    # Calculate the total population per block
    wb_blocks_pop = population_raster_process(population_tif, wb_blocks_districts)
    wb_blocks_pop = wb_blocks_pop.dropna(axis=0).reset_index(drop=True)

    # Calcualte the total population per district
    wb_districts_pop = population_raster_process(population_tif, wb_districts)

    # Write out the population to GeoJSON files
    wb_blocks_pop.to_file(WB_BLOCKS_POP_GEOJSON, driver="GeoJSON")
    wb_districts_pop.to_file(WB_DISTRICTS_POP_GEOJSON, driver="GeoJSON")

    return {"blocks": wb_blocks_pop, "districts": wb_districts_pop}
