pyvista-build
=============

Build a VTK backend wheel for `PyVista <https://github.com/pyvista/pyvista>`_
from source, guided step by step.

Kitware provides Python wheels for VTK at `PyPI VTK
<https://pypi.org/project/vtk/>`_, but there are situations where you may need
to build VTK from source: a new release of Python, a build without X, modules
the stock wheel leaves out, a VTK branch with a fix you need, or a backend
such as `cvista <https://github.com/pyvista/cvista>`_. ``pyvista-build`` does
this for you on Linux, macOS, and Windows:

.. code-block:: bash

   pip install pyvista-build
   pyvista-build vtk

The package depends on neither ``vtk`` nor ``pyvista``, so it runs in an
environment that has no VTK yet.

.. toctree::
   :maxdepth: 2

   building
