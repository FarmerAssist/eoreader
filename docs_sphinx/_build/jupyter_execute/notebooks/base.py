#!/usr/bin/env python
# coding: utf-8

# # Basic example
# Let's use EOReader for the first time !
#
# <div class="alert alert-warning">
#
# <strong>Warning:</strong> To complete this tutorial you will need <strong>matplotlib</strong>
#
# </div>

# In[1]:


import os

# First of all, we need some satellite data.
# Let's open a lightweight a Landsat-5 MSS collection 2 tile.
path = os.path.abspath("../../CI/DATA/LM05_L1TP_200029_19841014_20200902_02_T2.tar")


# In[2]:


from eoreader.reader import Reader

# Create the reader
eoreader = Reader()

# This reader is a singleton can be called once and then open all your data.
# Use it like a logging.getLogger() instance


# In[3]:


from eoreader.bands.alias import *

# Open your product
prod = eoreader.open(path)  # No need to unzip here
print(prod)


# In[4]:


# Here you have opened your product and you have its object in hands
# You can play a little with it to see what it got inside
print(f"Landsat tile: {prod.tile_name}")
print(f"Acquisition datetime: {prod.datetime}")


# In[5]:


# Open here some more interesting geographical data: extent
extent = prod.extent()
extent.geometry.iat[0]


# In[6]:


# Open here some more interesting geographical data: footprint
footprint = prod.footprint()
footprint.geometry.iat[0]


# See the difference between footprint and extent hereunder:
#
# |Without nodata | With nodata|
# |--- | ---|
# | ![without_nodata](https://zupimages.net/up/21/14/69i6.gif) | ![with_nodata](https://zupimages.net/up/21/14/vg6w.gif) |

# In[7]:


from eoreader.env_vars import DEM_PATH

# Select the bands you want to load
bands = [GREEN, NDVI, TIR_1, SHADOWS]

# Compute DEM band only if you have set a DEM in your environment path
if DEM_PATH in os.environ:
    bands.append(HILLSHADE)

# Be sure they exist for Landsat-5 MSS sensor:
ok_bands = [band for band in bands if prod.has_band(band)]
print(to_str(ok_bands))  # Landsat-5 MSS doesn't provide TIR and SHADOWS bands


# In[8]:


# Load those bands as a dict of xarray.DataArray
band_dict = prod.load(ok_bands)
band_dict[GREEN]


# In[9]:


# The nan corresponds to the nodata you see on the footprint
get_ipython().run_line_magic("matplotlib", "inline")

# Plot a subsampled version
band_dict[GREEN][:, ::10, ::10].plot()


# In[10]:


# Plot a subsampled version
band_dict[NDVI][:, ::10, ::10].plot()


# In[11]:


# Plot a subsampled version
if HILLSHADE in band_dict:
    band_dict[HILLSHADE][:, ::10, ::10].plot()


# In[12]:


# You can also stack those bands
stack = prod.stack(ok_bands)


# In[13]:


stack


# In[14]:


# Error in plotting with a list
if "long_name" in stack.attrs:
    stack.attrs.pop("long_name")

# Plot a subsampled version
stack[:, ::10, ::10].plot(x="x", y="y", col="z")
