```{include} ../README.md
```

# Site content

```{eval-rst}
.. toctree::
   :maxdepth: 2
   :caption: For Users

   main_features
   optical
   sar
```

```{eval-rst}
.. toctree::
   :maxdepth: 2
   :caption: Examples

   notebooks/base
   notebooks/water_detection
```

```{eval-rst}
.. autosummary::
    :toctree: _autosummary
    :caption: API
    :template: custom-module-template.rst
    :recursive:

    eoreader
```