Building VTK
============
One command builds a VTK wheel from source:

.. code-block:: bash

    pyvista-build vtk

It works on Linux, macOS, and Windows and follows the official `Building
Python wheels
<https://docs.vtk.org/en/latest/advanced/build_python_wheels.html>`_
instructions, with the options PyVista's own CI uses. A first build takes
from minutes to over an hour and needs several GB of disk.

- The wheel is built for, and installed into, the active virtual
  environment, else ``.venv`` in the current directory, else the Python
  running the command. ``--python PATH`` picks another interpreter.
- It says where the build goes and asks once before starting, then builds
  with those defaults straight through. Anything missing that it would
  install is listed before that question, which covers it too. ``--yes``
  answers it in advance.
- Every command is printed as it runs. Its output shows as one line that
  updates as it runs, with the time elapsed. ``--verbose`` (``-v``) prints
  all of the output and the environment variables each command sets.

``--interactive`` walks through the build one step at a time:

- Each step shows its settings, says what it is about to do and where, and
  waits for a yes.
- Enter accepts the default, ``n`` goes through the settings one by one, and
  the same flags the command line takes change one in place.

.. code-block:: bash

    pyvista-build vtk --interactive

``pyvista-build --help`` lists every flag. The result is a wheel, so once
installed (manually or with ``--install``) PyVista picks it up like the
stock one.

The Steps
~~~~~~~~~
Every build runs the same eight steps, in this order. Each one prints what it
is about to do, and ``--interactive`` waits for a yes before it runs.

1. Tools
^^^^^^^^
Ensure the tools the build needs are available.

- Checks ``git``, ``cmake``, ``ninja``, a C++ compiler, and the wheel repair
  tool before anything is downloaded. See `Tooling`_ for what each one does.
- Lists everything the build would install, each item with where it goes:
  ``cmake``, ``ninja``, and the repair tool when missing or too old,
  ``setuptools`` and ``wheel``, and the finished wheel with ``--install``.
- Starting the build covers that whole list. ``--interactive`` asks again at
  this step, and ``--yes`` answers in advance. Without a terminal and without
  ``--yes`` the command stops instead of installing.
- A missing compiler stops with instructions for your operating system. On
  Windows, Visual Studio's build environment is imported automatically.
- ``--compiler-cache auto`` adds a compiler cache (``ccache`` or ``sccache``)
  when one is on ``PATH``.
- When the cloned source asks for other ``cmake`` or ``ninja`` versions than
  the ones checked, as on a first ``cvista`` build, those are checked again
  after step 2.

2. Source
^^^^^^^^^
Get the VTK source to build.

- Clones VTK into ``./vtk-build/src`` at the release tag PyVista supports.
- ``--ref`` picks another tag, branch, or commit. ``--build-dir`` puts
  everything somewhere else. ``--source DIR`` builds a checkout you already
  have.
- An existing checkout is reused as is, local edits included.
- With ``--interactive`` the clone prompt also takes a fork's git URL or the
  path of another checkout, and an existing checkout is confirmed before it is
  reused. Answering with a git URL there deletes it, after one more
  confirmation, and clones the fork in its place.
- A build tree configured from one checkout cannot build another, so switching
  checkouts asks before deleting the build tree. ``--clean`` or another
  ``--build-dir`` avoids the question.

3. Build options
^^^^^^^^^^^^^^^^
Choose which modules and options to build.

On top of the modules every build has, the modules to build are organized
into named groups. The default set matches the stock wheel plus what
PyVista's CI enables:

- ``rendering``: OpenGL rendering, widgets, charts, and text
- ``io``: extra readers and writers (scene import, Exodus, Xdmf2)
- ``web``: web export modules used by trame and the Jupyter backends
- ``matplotlib``: Matplotlib-rendered math text and labels
- ``parallel``: DIY2-based parallel filters
- ``serialization``: object serialization and ``.pyi`` stub files
- ``headless`` (Linux, off by default): no X, rendering through EGL or
  OSMesa, see `Off-Screen Plotting GPU Support`_

Options:

- ``--with`` and ``--without`` add or drop groups, ``--minimal`` keeps only
  the required ones.
- ``--opt smp=VALUE`` picks the threading backend for SMP-enabled filters:
  ``Sequential`` (the default, as in the PyPI wheels), ``STDThread``,
  ``OpenMP``, or ``TBB``, which needs TBB installed.
- At the prompt, ``n`` asks about each group in turn, and the command-line
  flags work there as well.

.. code-block:: bash

    pyvista-build vtk --without web,matplotlib
    pyvista-build vtk --minimal --with rendering
    pyvista-build vtk --opt smp=STDThread

4. Configure
^^^^^^^^^^^^
Generate the build tree with CMake.

- Shows the build type, compiler cache, version suffix, and extra CMake cache
  entries, then runs ``cmake``.
- ``--build-type``, ``--compiler-cache``, ``--version-suffix``, and ``-D``
  change one directly. At the prompt, ``n`` asks about each in turn.
- Every command is printed in full before it runs.

5. Build
^^^^^^^^
Compile VTK.

- Runs ``cmake --build`` with Ninja and logs the full output to
  ``vtk-build/build.log``.
- Uses one compile job per CPU core, at most one per 2 GB of memory, since
  each job can take that much. ``--jobs`` sets the number instead.
- When a command fails, its last lines of output are printed and the build
  stops. The log has the complete compiler output.

6. Wheel
^^^^^^^^
Package the build as a wheel.

- Runs ``setup.py bdist_wheel`` in the build tree.

7. Repair
^^^^^^^^^
Make the wheel installable outside the build tree.

- Bundles the libraries the wheel links against and sets its platform tag, so
  it installs outside the build tree and on other machines.
- A rerun reuses the repaired wheel when the built wheel's contents have not
  changed.
- ``--no-repair`` skips the step.

8. Install
^^^^^^^^^^
Install the wheel into the target environment.

- ``--install`` installs the wheel into the target environment, which
  starting the build covers. Without it, ``--interactive`` offers to, and
  otherwise the wheel's path and the ``pip`` command are printed.
- The wheel replaces the installed ``vtk``. ``pip install --force-reinstall
  vtk`` goes back to the stock one.

Scripted Use
~~~~~~~~~~~~
Without ``--interactive`` the command asks once before it starts, and
that answer covers installing anything that is missing. Without a
terminal it stops at that question, so pass ``--yes`` in CI and scripts,
and ``--verbose`` so the job log shows every command in full and every
line of output. ``--dry-run``
prints the commands, and the install list, without running anything.
For a backend whose manifest lives only in
its source tree, such as ``cvista``, ``--dry-run`` needs an existing
checkout and stops without one. Optional steps keep their own switches, so
``--no-repair`` skips the repair step and ``--install`` installs the
wheel at the end.

.. code-block:: bash

    pyvista-build vtk --ref master --build-type RelWithDebInfo --jobs 8 --yes
    pyvista-build vtk --dry-run

Developer Loop
~~~~~~~~~~~~~~
The build tree is kept between runs. Edit files under ``vtk-build/src``
and run ``pyvista-build vtk`` again: configure is skipped unless the
options changed, ``ninja`` rebuilds what the edit touched and a new
wheel is written. ``--reconfigure`` forces ``cmake`` to run again,
``--clean`` deletes the build tree first, and ``-D KEY=VALUE`` passes
any CMake cache entry straight through:

.. code-block:: bash

    pyvista-build vtk --build-type Debug -D VTK_ENABLE_LOGGING=OFF

``--ref`` leaves a checkout
that is already at that commit as it is, edits included, and otherwise
checks the commit out, which needs a checkout without local edits.
``--update`` fetches first, then checks out ``--ref``, or the release
tag when ``--ref`` is not given, and always needs a checkout without
local edits:

.. code-block:: bash

    pyvista-build vtk --update --ref master

CI Workflows
~~~~~~~~~~~~
A CI job builds from scratch every time, so a compiler cache is what keeps
it short: a warm cache turns a build of hours into minutes.

- Pass ``--yes`` and ``--verbose``, as in `Scripted Use`_.
- ``--compiler-cache auto`` uses ``ccache`` or ``sccache``, whichever is on
  ``PATH``. Install ``ccache`` on Linux and macOS (``apt-get install ccache``,
  ``brew install ccache``) and set up ``sccache`` on Windows, where MSVC
  needs it (`mozilla-actions/sccache-action
  <https://github.com/mozilla-actions/sccache-action>`_).
- ``--cache-dir`` puts the cache in a directory the job can save and restore
  between runs. Save it at the end of the job and restore it at the start,
  one cache per operating system: object files from one do not help another.
- The cache tools read their own environment variables, and the command
  passes every ``CCACHE_*`` and ``SCCACHE_*`` setting through to the build
  and into the manylinux container. ``CCACHE_MAXSIZE=1G`` or
  ``SCCACHE_CACHE_SIZE=1G`` is the one worth setting in a job: the defaults
  are 5 GB and 10 GB, a full VTK build fits in 1 GB, and the cache is
  uploaded and downloaded on every run. A developer machine needs no cap.
- The command already keys ``ccache`` entries on the compiler's version
  string rather than its binary's timestamp (``CCACHE_COMPILERCHECK``) and
  on paths relative to the build (``CCACHE_BASEDIR``), so a runner image
  update that ships the same compiler, or a job that checks out elsewhere,
  keeps the cache valid.
- On Linux add ``--manylinux`` for a wheel that installs on other
  machines; the container installs ``ccache`` itself and uses the same
  directory.
- The cache statistics are printed after the build and, on GitHub Actions,
  written to the job summary (``GITHUB_STEP_SUMMARY``), from inside the
  container as well.

.. code-block:: bash

    pyvista-build vtk --yes --verbose --compiler-cache auto --cache-dir compiler-cache

`This repository's own workflow
<https://github.com/pyvista/pyvista-build/blob/main/.github/workflows/build-vtk.yml>`_
does this on all three operating systems, keeping the cache as a workflow
artifact. A full
hit rate finishes in about 10 minutes on Linux, 25 on macOS, and 35 on
Windows.

Other Backends
~~~~~~~~~~~~~~
The same command builds any VTK backend whose source tree carries a
``pyvista-build.toml`` manifest. That file declares the groups and
options the backend offers, its tool requirements, per-platform CMake
init caches, and the extra commands it needs; stock VTK's manifest ships
with ``pyvista-build``. `cvista <https://github.com/pyvista/cvista>`_, the
community fork, is known by name. A fork of VTK is built as ``vtk`` from
its URL, using the manifest
in its tree when it has one and the shipped one otherwise. A ``--url`` the
existing checkout in the build directory was not cloned from stops the
build, so give a fork its own ``--build-dir``:

.. code-block:: bash

    pyvista-build cvista
    pyvista-build vtk --url https://github.com/me/vtk.git --ref my-branch --build-dir vtk-fork-build

A backend built this way is selected like any other installed one:
automatically for ``cvista``, or explicitly through
``PYVISTA_VTK_BACKEND``.

Off-Screen Plotting GPU Support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The stock Linux wheels already render off-screen without an X server:
VTK picks EGL for GPU rendering, or OSMesa for software rendering, at
run time. To build a wheel that does not link against X at all:

.. code-block:: bash

    pyvista-build vtk --with headless

Such a wheel cannot open on-screen windows, so use it only where you
save static images or stream the render window to another computer
with a display (for example, using
``pyvista.set_jupyter_backend('server')`` and JupyterLab).

Portable Linux Wheels
~~~~~~~~~~~~~~~~~~~~~
A wheel built on Linux is tagged for the ``glibc`` of the machine that
built it and may not install elsewhere. To share one, build it inside a
`manylinux <https://github.com/pypa/manylinux>`_ container, as PyVista's
own CI does.

- ``--manylinux`` builds a Linux wheel only. It runs the build in a
  container through `Docker <https://docs.docker.com/get-docker/>`_, so
  Docker is needed for this flag and for nothing else.
- Without ``--manylinux`` no Docker is involved on any operating system,
  and macOS and Windows wheels are always built that way.
- A macOS or Windows machine can still run ``--manylinux`` to produce a
  Linux wheel, which it then cannot install.

Docker must be installed and running first:

- Linux: install `Docker Engine <https://docs.docker.com/engine/install/>`_
  for your distribution, then add yourself to the ``docker`` group
  (``sudo usermod -aG docker $USER``) and log in again so no ``sudo`` is
  needed.
- macOS: install `Docker Desktop for Mac
  <https://docs.docker.com/desktop/setup/install/mac-install/>`_ (or
  ``brew install --cask docker``) and start it.
- Windows: install `Docker Desktop for Windows
  <https://docs.docker.com/desktop/setup/install/windows-install/>`_ with
  the WSL 2 backend and start it.

``docker run --rm hello-world`` confirms it works. Then:

.. code-block:: bash

    pyvista-build vtk --manylinux

What happens:

- The image matches your machine's architecture (``manylinux_2_28_x86_64``
  or ``manylinux_2_28_aarch64``) and carries the same Python version as the
  one running the command. ``--manylinux-image`` picks another image.
- The source is cloned or updated on your machine first.
- The container installs VTK's build dependencies and this package's
  requirements, mounts the ``pyvista-build`` you are running read-only, and
  runs the remaining steps with the source and ``./vtk-build`` mounted.
- The repair step runs ``auditwheel`` there, which gives the wheel its
  ``manylinux`` tag and puts it in ``vtk-build/wheelhouse``.
- Files written by the container are handed back to your user, even when
  the build fails.
- On a Linux host the install step runs afterwards. On macOS and Windows the
  wheel is only written, since it is for Linux.

Caches and limits:

- With ``--compiler-cache auto`` or ``ccache`` the container installs
  ``ccache`` and keeps its cache between runs in ``vtk-build/compiler-cache``,
  or in ``--cache-dir`` or ``$CCACHE_DIR`` when set. ``sccache`` is not
  available there.
- ``pip`` keeps its cache in ``vtk-build/pip-cache``.
- A build tree configured inside the container cannot be continued outside
  it.

Tooling
~~~~~~~
What the command looks for and offers to install:

- `git <https://git-scm.com/>`_ clones the source and checks out the
  requested tag, branch, or commit. Never installed by the command.
- `CMake <https://cmake.org/>`_ configures the build: it reads VTK's
  ``CMakeLists.txt`` and the options chosen, finds the compiler and
  Python, and writes the build files. Installed with ``pip`` when
  missing.
- `Ninja <https://ninja-build.org/>`_ is the build tool that CMake
  generates files for; it runs the compiler across all cores and only
  rebuilds what changed. Installed with ``pip`` when missing.
- **A C++ compiler**: `GCC <https://gcc.gnu.org/install/>`_ or
  `Clang <https://clang.llvm.org/get_started.html>`_ on Linux, `Xcode's
  command-line tools
  <https://developer.apple.com/documentation/xcode/installing-the-command-line-tools>`_
  on macOS (``xcode-select --install``), `Visual Studio
  <https://visualstudio.microsoft.com/downloads/>`_ with the
  `Desktop development with C++ workload
  <https://learn.microsoft.com/en-us/cpp/build/vscpp-step-0-installation>`_
  on Windows. Never installed by the command. A missing one stops with the
  instructions for your operating system.
- **Development headers on Linux** for Python, OpenGL, and X11:
  ``sudo apt install python3-dev libgl1-mesa-dev libx11-dev libxcursor-dev``
  on Debian and Ubuntu, or ``sudo dnf install python3-devel
  mesa-libGL-devel libX11-devel libXcursor-devel`` on Fedora. The tool
  check cannot see them, so a missing one stops ``cmake`` instead.
- `ccache <https://ccache.dev/>`_ and `sccache
  <https://github.com/mozilla/sccache>`_ are compiler caches: they store
  each object file keyed by its inputs, so rebuilding after an edit or a
  reconfigure compiles again only what changed. ``ccache`` is the usual
  choice on Linux and macOS; ``sccache`` is the one that supports MSVC
  on Windows. ``--compiler-cache auto`` uses whichever is on ``PATH``.
  Off by default: within one build tree Ninja already rebuilds only what
  changed, so a cache pays off when the tree is built from scratch, as in
  CI.
- **Wheel repair tools** copy the shared libraries a wheel depends on
  into the wheel itself and set the platform tag, so it installs on
  other machines: `auditwheel
  <https://github.com/pypa/auditwheel>`_ on Linux, `delocate
  <https://github.com/matthew-brett/delocate>`_ on macOS, and `delvewheel
  <https://github.com/adang1345/delvewheel>`_ on Windows. Installed with
  ``pip`` when missing.
- `setuptools <https://setuptools.pypa.io/>`_ and `wheel
  <https://wheel.readthedocs.io/>`_ are the Python packages that
  ``setup.py bdist_wheel`` needs to package the build tree. Installed
  with ``pip`` when missing.
- `Docker <https://docs.docker.com/get-docker/>`_ runs the manylinux
  container for ``--manylinux``. Never installed by the command.

Building by Hand
~~~~~~~~~~~~~~~~
``pyvista-build vtk --dry-run`` prints the exact ``cmake`` and
``setup.py`` commands, which is the quickest way to get a starting point
for a manual build. The essential configuration is:

.. code-block:: bash

    git clone https://gitlab.kitware.com/vtk/vtk.git
    cmake -S vtk -B vtk/build -GNinja \
          -DCMAKE_BUILD_TYPE=Release \
          -DVTK_WHEEL_BUILD=ON \
          -DVTK_WRAP_PYTHON=ON \
          -DVTK_BUILD_TESTING=OFF \
          -DVTK_BUILD_DOCUMENTATION=OFF \
          -DVTK_BUILD_EXAMPLES=OFF \
          -DPython3_EXECUTABLE=$(which python)
    cmake --build vtk/build --parallel
    cd vtk/build && python setup.py bdist_wheel

The wheel is written to ``vtk/build/dist``.
