""" Script testing EOReader satellites in a push routine """
import glob
import logging
import os
import tempfile
import platform
from tempenv import TemporaryEnvironment

import geopandas as gpd
import xarray as xr

from eoreader.bands.alias import *
from eoreader.env_vars import CI_EOREADER_BAND_FOLDER, DEM_PATH, S3_DEF_RES, SAR_DEF_RES
from eoreader.products.product import Product, SensorType
from eoreader.reader import CheckMethod, Platform
from eoreader.utils import EOREADER_NAME
from sertit import ci, files, logs

from .scripts_utils import (
    OPT_PATH,
    READER,
    SAR_PATH,
    assert_geom_almost_equal,
    get_ci_data_dir,
    get_db_dir,
)

LOGGER = logging.getLogger(EOREADER_NAME)

if os.environ.get("USE_UNISTRA_S3") not in ("Y", "YES", "TRUE", "T"):
    try:
        merit_dem = os.path.join(
            get_db_dir(),
            "GLOBAL",
            "MERIT_Hydrologically_Adjusted_Elevations",
            "MERIT_DEM.vrt",
        )
        # eudem_path = os.path.join(utils.get_db_dir(), 'GLOBAL', "EUDEM_v2", "eudem_wgs84.tif")
        os.environ[DEM_PATH] = merit_dem
    except NotADirectoryError as ex:
        LOGGER.debug("Non available default DEM: %s", ex)
        pass
else:
    os.environ[DEM_PATH] = "https://s3.unistra.fr/sertit-geodatastore/GLOBAL/MERIT_Hydrologically_Adjusted_Elevations/MERIT_DEM.vrt"
    LOGGER.info(f"Using DEM provided through Unistra S3 ({os.environ[DEM_PATH]})")


def remove_dem(prod):
    """Remove DEM from product output"""
    to_del = glob.glob(os.path.join(prod.output, f"{prod.condensed_name}_DEM.tif"))
    to_del += glob.glob(
        os.path.join(prod.output, f"{prod.condensed_name}_HILLSHADE.tif")
    )
    to_del += glob.glob(os.path.join(prod.output, f"{prod.condensed_name}_SLOPE.tif"))
    for to_d in to_del:
        files.remove(to_d)


def test_invalid():
    wrong_path = "dzfdzef"
    assert READER.open(wrong_path) is None
    assert not READER.valid_name(wrong_path, "S2")


def _test_core_optical(pattern: str, debug=False):
    """
    Core function testing optical data
    Args:
        pattern (str): Pattern of the satellite
        debug (bool): Debug option
    """
    possible_bands = [RED, SWIR_2, HILLSHADE, CLOUDS]
    _test_core(pattern, OPT_PATH, possible_bands, debug)


def _test_core_sar(pattern: str, debug=False):
    """
    Core function testing SAR data
    Args:
        pattern (str): Pattern of the satellite
        debug (bool): Debug option
    """
    possible_bands = [VV, VV_DSPK, HH, HH_DSPK, SLOPE, HILLSHADE]
    _test_core(pattern, SAR_PATH, possible_bands, debug)


def _test_core(pattern: str, prod_dir: str, possible_bands: list, debug=False):
    """
    Core function testing all data
    Args:
        pattern (str): Pattern of the satellite
        prod_dir (str): Product directory
        possible_bands(list): Possible bands
        debug (bool): Debug option
    """
    with xr.set_options(warn_for_unclosed_files=debug):

        # Init logger
        logs.init_logger(LOGGER)

        # DATA paths
        pattern_paths = files.get_file_in_dir(
            prod_dir, pattern, exact_name=True, get_list=True
        )

        for path in pattern_paths:
            LOGGER.info(os.path.basename(path))

            # Open product and set output
            prod: Product = READER.open(path, method=CheckMethod.MTD)
            prod_name = READER.open(path, method=CheckMethod.NAME)
            prod_both = READER.open(path, method=CheckMethod.BOTH)
            assert prod is not None
            assert prod == prod_name
            assert prod == prod_both

            # Discard the case where an invalid file/directory is in the CI folder
            if prod is not None:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    # tmp_dir = os.path.join(get_ci_data_dir(), "OUTPUT")
                    prod.output = tmp_dir
                    if (
                        prod.platform == Platform.S3
                        or prod.sensor_type == SensorType.SAR
                    ):
                        os.environ[CI_EOREADER_BAND_FOLDER] = os.path.join(
                            get_ci_data_dir(), prod.condensed_name
                        )
                    else:
                        if CI_EOREADER_BAND_FOLDER in os.environ:
                            os.environ.pop(CI_EOREADER_BAND_FOLDER)

                    # Extent
                    LOGGER.info("Checking extent")
                    extent = prod.extent()
                    extent_path = os.path.join(
                        get_ci_data_dir(), prod.condensed_name, "extent.geojson"
                    )
                    if not os.path.isfile(extent_path):
                        extent.to_file(extent_path, driver="GeoJSON")

                    try:
                        ci.assert_geom_equal(extent, gpd.read_file(extent_path))
                    except AssertionError:
                        assert_geom_almost_equal(
                            extent, gpd.read_file(extent_path)
                        )  # TODO: WHY ???

                    # Footprint
                    LOGGER.info("Checking footprint")
                    footprint = prod.footprint()
                    footprint_path = os.path.join(
                        get_ci_data_dir(), prod.condensed_name, "footprint.geojson"
                    )
                    if not os.path.isfile(footprint_path):
                        footprint.to_file(footprint_path, driver="GeoJSON")

                    try:
                        ci.assert_geom_equal(footprint, gpd.read_file(footprint_path))
                    except AssertionError:
                        assert_geom_almost_equal(
                            footprint, gpd.read_file(footprint_path)
                        )  # Has not happen for now

                    # Remove DEM tifs if existing
                    remove_dem(prod)

                    # Get stack bands
                    LOGGER.info("Checking load and stack")
                    # DO NOT RECOMPUTE BANDS WITH SNAP --> WAY TOO SLOW
                    stack_bands = [
                        band for band in possible_bands if prod.has_band(band)
                    ]

                    # Manage S3 resolution to speed up processes
                    if prod.sensor_type == SensorType.SAR:
                        res = 1000.0
                        os.environ[SAR_DEF_RES] = str(res)
                    else:
                        res = prod.resolution * 50
                        os.environ[S3_DEF_RES] = str(res)

                    # Stack data
                    ci_data = os.path.join(
                        get_ci_data_dir(), prod.condensed_name, "stack.tif"
                    )
                    if debug:
                        curr_path = os.path.join(
                            get_ci_data_dir(), prod.condensed_name, "stack.tif"
                        )
                    else:
                        curr_path = os.path.join(
                            tmp_dir, f"{prod.condensed_name}_stack.tif"
                        )
                    prod.stack(stack_bands, resolution=res, stack_path=curr_path)

                    # Test
                    ci.assert_raster_almost_equal(curr_path, ci_data, decimal=4)

                # CRS
                LOGGER.info("Checking CRS")
                assert prod.crs().is_projected


def test_s2():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("S2*_MSI*")


def test_s2_theia():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("SENTINEL2*")


def test_s3_olci():
    """Function testing the correct functioning of the optical satellites"""
    # Init logger
    _test_core_optical("S3*_OL_1_*")


def test_s3_slstr():
    """Function testing the correct functioning of the optical satellites"""
    # Init logger
    _test_core_optical("S3*_SL_1_*")


def test_l8():
    """Function testing the correct functioning of the optical satellites"""
    # Init logger
    _test_core_optical("LC08*")


def test_l7():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LE07*")


def test_l5_tm():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LT05*")


def test_l4_tm():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LT04*")


def test_l5_mss():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LM05*")


def test_l4_mss():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LM04*")


def test_l3_mss():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LM03*")


def test_l2_mss():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LM02*")


def test_l1_mss():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_optical("LM01*")


def test_s1():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_sar("S1*_IW*")


def test_csk():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_sar("csk_*")


def test_tsx():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_sar("TSX*")


def test_rs2():
    """Function testing the correct functioning of the optical satellites"""
    _test_core_sar("RS2_*")


# TODO:
# check non existing bands
# check cloud results
