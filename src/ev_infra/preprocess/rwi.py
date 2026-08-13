"""Process Relative Wealth Index (RWI) point data for West Bengal: convert raw points
to a geodataframe, grid them to match RWI's native ~2.4km resolution, and average RWI
per administrative block."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box

from ev_infra.config import DATA_PROCESSED, RAW_RWI_CSV
from ev_infra.preprocess.boundaries import WEST_BENGAL_GEOJSON, WB_BLOCKS_DISTRICTS_GEOJSON

# Define the directory to write out the processsed data
WB_RWI_GEOJSON = DATA_PROCESSED / "west-bengal-RWI.geojson"
WB_BLOCKS_RWI_GEOJSON = DATA_PROCESSED / "west-bengal-blocks-rwi.geojson"


def process_rwi_points(
    west_bengal_boundary_path=WEST_BENGAL_GEOJSON,
    raw_rwi_csv=RAW_RWI_CSV):
    """Convert the raw India/Pakistan RWI CSV to point geometry and clip to West Bengal."""
    # Read in the files
    west_bengal = gpd.read_file(west_bengal_boundary_path)
    ind_pak_rwi = pd.read_csv(raw_rwi_csv)

    # Convert latitude and longitude (X and Y) data to Point data to be used to create a geodataframe.
    rwi_points = ind_pak_rwi.apply(lambda row: Point(row.longitude, row.latitude), axis=1)

    # Create a new geodataframe using converted geometry points
    rwi = gpd.GeoDataFrame(ind_pak_rwi, geometry=rwi_points)
    rwi.crs = "epsg:4326"

    # Extract the points for West Bengal and save to output file
    wb_rwi = gpd.clip(rwi, mask=west_bengal).reset_index(drop=True)

    # Write out the extracted RWI points to a geojson file
    wb_rwi.to_file(WB_RWI_GEOJSON, driver="GeoJSON")

    return wb_rwi


def points_to_grid(df):
    """Convert RWI point geometry to 2.4km x 2.4km square polygons matching its native resolution."""
    # Obtain the CRS of the dataframe
    crs = df.crs
    # Conver to a projected CRS (e.g., UTM) for accurate distance calculations.
    df = df.to_crs(epsg=32645)  # UTM zone 45N

    # Define the distance in meters (2.4 km)
    distance = 2400 / 2  # 1200 m from center to each edge of the square

    # Create square polygons around each point
    def create_square_polygon(point, distance):
        x, y = point.x, point.y
        return box(x - distance, y - distance, x + distance, y + distance)

    df["geometry"] = df["geometry"].apply(lambda point: create_square_polygon(point, distance))

    # Convert back to geographic CRS if needed
    df = df.to_crs(crs)
    
    return df


def average_rwi_by_block(wb_rwi_grid, wb_blocks_districts):
    """Spatially join gridded RWI points to blocks and compute average RWI per block."""

    # Create a spatial join of the RWI grid data with the West Bengal block boundaries
    wb_blocks_rwi = gpd.sjoin(wb_rwi_grid, wb_blocks_districts, how="inner", predicate="intersects").reset_index(drop=True)

    # Calculate the average RWI in each block
    avg_rwi_per_block = wb_blocks_rwi.groupby("block")["rwi"].mean().reset_index()
    avg_rwi_per_block = avg_rwi_per_block.rename(columns={"rwi": "avg_rwi"})

    # Merge the average RWI values with the block boundaries geodataframe
    wb_blocks_avg_rwi = wb_blocks_districts.merge(avg_rwi_per_block, on='block')

    return wb_blocks_avg_rwi

def process_block_rwi(
    rwi_path=WB_RWI_GEOJSON,
    wb_blocks_districts_path=WB_BLOCKS_DISTRICTS_GEOJSON):
    """Grid RWI points, join to blocks, average per block, and write the result out."""
    # Read in the relevant files
    rwi = gpd.read_file(rwi_path)
    wb_blocks_districts = gpd.read_file(wb_blocks_districts_path)

    wb_rwi_grid = points_to_grid(rwi)
    wb_blocks_avg_rwi = average_rwi_by_block(wb_rwi_grid, wb_blocks_districts)

    wb_blocks_avg_rwi.to_file(WB_BLOCKS_RWI_GEOJSON, driver="GeoJSON")

    return wb_blocks_avg_rwi