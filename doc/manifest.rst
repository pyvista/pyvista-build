Manifest Reference
==================
A backend describes its build in a ``pyvista-build.toml`` manifest at the
root of its source tree. The file is the interface between a backend and
``pyvista-build``: it names the groups and options the command offers,
the tools it checks for, the CMake cache entries it passes, and the extra
commands it runs. This page lists every table and key the command reads.

A manifest for stock VTK ships with the package, and `cvista
<https://github.com/pyvista/cvista/blob/main/pyvista-build.toml>`_ keeps a
full one in its tree. Both are good starting points.

Where the Manifest Comes From
-----------------------------
- The checkout's own ``pyvista-build.toml`` is read when the tree has one.
- Otherwise the manifest shipped with the package is used, for backends
  that ship one (``vtk``).
- A backend with neither stops the build. ``pyvista-build vtk --url
  <fork>`` therefore builds a fork of VTK with the shipped manifest until the
  fork carries its own, and ``pyvista-build <name> --url <git url>`` or
  ``--source <checkout>`` builds any other backend whose tree carries one.

Unknown keys are errors rather than ignored, so a typo in a manifest stops
the build with a message naming the table and the keys it accepts.

Minimal Example
---------------
A fork of VTK that adds one module group and one switch:

.. code-block:: toml

    manifest_version = 1

    [backend]
    name = "vtk"
    default_ref = "my-branch"
    url = "https://github.com/me/vtk.git"

    [tools]
    cmake = ">=3.22"
    ninja = ">=1.11"

    [cmake]
    common = ["VTK_WHEEL_BUILD=ON", "VTK_WRAP_PYTHON=ON", "VTK_BUILD_TESTING=OFF"]

    [groups.rendering]
    help = "OpenGL rendering"
    default = true
    cmake = ["VTK_GROUP_ENABLE_Rendering=WANT"]
    cmake_off = ["VTK_GROUP_ENABLE_Rendering=NO"]

    [options.lto]
    help = "Link-time optimisation"
    default = false
    cmake = "CMAKE_INTERPROCEDURAL_OPTIMIZATION={value}"

The command adds the build type, the Python interpreter, the compiler
launcher and the version suffix itself. Everything else a wheel build
needs, ``VTK_WHEEL_BUILD`` and ``VTK_WRAP_PYTHON`` above all, comes from the
manifest or its init cache.

``manifest_version``
--------------------
Required integer, currently ``1``. A manifest written for another version
is refused, so a backend that needs a newer format fails on an older
``pyvista-build`` with a clear message instead of building something else.

``[backend]``
-------------
``name``
    Required. The backend's name, as given on the command line.

``import_name``
    Module the installed wheel is imported as, to check the install. Defaults
    to ``name``. Dotted names are accepted.

``default_ref``
    Required. Git ref cloned when ``--ref`` is not given: a tag for a
    release, a branch for a development backend.

``url``
    Git URL to clone from. Optional for a manifest that is only ever built
    from an existing checkout.

``version_command``
    Command run inside the source tree, in place of ``git describe``, to
    print the wheel's version suffix. Its output becomes
    ``VTK_VERSION_SUFFIX``, and empty output means a release. The command
    takes the placeholders listed under `Hooks`_. Without it, a checkout
    on a tag builds a release and any other commit gets ``dev0+g<sha>``.

``[tools]``
-----------
Version specifiers for the two tools the command installs when they are
missing or too old, as ``pip`` writes them:

.. code-block:: toml

    [tools]
    cmake = ">=3.22,<4.2"
    ninja = ">=1.11"

Both keys are optional. Any other tool the build needs is detected but not
installed, and the command prints how to get it.

``[cmake]``
-----------
``common``
    Cache entries passed on every operating system, written as
    ``KEY=VALUE`` or ``KEY:TYPE=VALUE`` without the ``-D`` prefix.

``linux``, ``macos``, ``windows``
    Cache entries for one operating system only, in the same form.

``init_cache``
    Table mapping an operating system to a CMake script passed with ``-C``,
    as a path relative to the source tree. An init cache runs before the
    cache entries, so entries from the manifest and the command line override
    it.

.. code-block:: toml

    [cmake]
    common = ["VTK_WHEEL_BUILD=ON", "VTK_WRAP_PYTHON=ON"]
    macos = ["CMAKE_OSX_DEPLOYMENT_TARGET=11.0"]
    init_cache = { linux = "ci/cmake/linux.cmake", macos = "ci/cmake/macos.cmake" }

A ``CMAKE_OSX_DEPLOYMENT_TARGET`` in ``common`` or ``macos`` is also the
platform tag the macOS wheel is built for. Without one the command
uses its own default.

``[groups.<name>]``
--------------------
A group is a set of cache entries switched on or off together. Groups
appear in the build options table, and ``--with``, ``--without`` and
``--minimal`` select them.

``help``
    Required. One line shown next to the group.

``default``
    Whether the group is on unless ``--without`` or ``--minimal`` says
    otherwise. Defaults to ``false``.

``cmake``
    Required. Cache entries added when the group is on.

``cmake_off``
    Cache entries added when the group is off. Without it, the keys from
    ``cmake`` are unset (``-U``) instead, unless another enabled entry
    sets them, so a module left over from an earlier configure does not
    stay on.

``os``
    Operating systems the group exists on, a list of ``"linux"``,
    ``"macos"`` and ``"windows"``. Defaults to all three. A group left out
    of the current platform is not shown and cannot be selected.

``conflicts``
    Groups that cannot be on at the same time. The relation is declared on
    both sides, and enabling both stops the build with a message naming
    them.

``required``
    A group that is always on and that ``--without`` refuses to disable.
    Defaults to ``false``.

``[options.<name>]``
---------------------
An option is a scalar knob, set with ``--opt NAME=VALUE``. Its type follows
its default: a boolean accepts ``1``, ``0``, ``true``, ``false``, ``on``,
``off``, ``yes`` and ``no``; an integer accepts digits; a string accepts
anything, or one of its ``choices``.

``help``
    Required. One line shown next to the option.

``default``
    Required. A boolean, an integer or a string.

``cmake``
    Cache entry template containing ``{value}``, for example
    ``"VTK_SMP_IMPLEMENTATION_TYPE={value}"``. A boolean renders as ``ON``
    or ``OFF``.

``env``
    Environment variable set to the value while ``cmake`` and the hooks
    run, for an init cache or a hook that reads its settings from the
    environment. A boolean renders as ``1`` or ``0``.

``choices``
    Allowed values for a string option. The default has to be one of
    them.

Exactly one of ``cmake`` and ``env`` is set.

.. code-block:: toml

    [options.smp]
    help = "Threading backend for SMP-enabled filters"
    default = "Sequential"
    choices = ["OpenMP", "STDThread", "Sequential", "TBB"]
    cmake = "VTK_SMP_IMPLEMENTATION_TYPE={value}"

    [options.lto]
    help = "Link-time optimisation as in the release wheels"
    default = true
    env = "CVISTA_LTO"

``[manylinux]``
---------------
``packages``
    System packages ``--manylinux`` installs in the container with ``dnf``
    before configuring, such as the X11 and GL development headers VTK's
    rendering modules need. The manylinux images are AlmaLinux based, so
    the names are the RPM ones.
``env``
    Environment variables ``--manylinux`` passes from the host into the
    container, by name or ``fnmatch`` pattern. The ``CCACHE_*`` and
    ``SCCACHE_*`` settings and the terminal color variables go in without
    being listed, and the cache's host paths (``CCACHE_DIR`` and the others
    named in :doc:`building`) stay on the host even when a pattern matches
    them. ``--env`` adds names for one build.

.. code-block:: toml

    [manylinux]
    packages = ["libX11-devel", "libXcursor-devel", "mesa-libGL-devel"]
    env = ["CVISTA_*"]

``[repair]``
------------
``strip``
    Strip the local symbols from every library in the repaired wheel, the
    extension modules included. Defaults to ``false``. On Linux
    ``auditwheel repair`` runs with ``--strip``. On macOS every Mach-O
    library is stripped with ``strip -x``, signed again ad-hoc with ``codesign``, and
    the wheel's ``RECORD`` is recomputed. On Windows nothing is stripped:
    ``delvewheel`` has no symbol strip.

``linux``, ``macos``, ``windows``
    Extra arguments for that operating system's repair tool
    (``auditwheel``, ``delocate-wheel`` or ``delvewheel``), inserted
    before the wheel path. Each defaults to an empty list. Inside a
    manylinux container a ``--plat`` in ``linux`` replaces the one the
    build passes for the image.

.. code-block:: toml

    [repair]
    strip = true
    windows = ["--no-mangle-all"]

.. _hooks:

``[hooks]``
-----------
Commands the build runs at fixed points, each a list of command lines.
They run inside the source tree, with the ``env`` options exported, and a
failing command stops the build.

``post_configure``
    After ``cmake`` configures. A place to check that the build tree
    matches what the backend can build here.

``post_build``
    After the compile, before the wheel is packaged. ``cvista`` prunes dead
    subpackages from ``setup.py`` here.

``post_wheel``
    After ``bdist_wheel`` writes the wheel, before the repair step. A place
    to retag the wheel.

Each command line is split like a shell would, and these placeholders are
substituted in every part:

``{python}``
    The interpreter the wheel is built for.

``{src_dir}``
    The source checkout.

``{build_dir}``
    The CMake build tree.

``{dist_dir}``
    Where ``bdist_wheel`` writes the wheel.

``{wheelhouse}``
    Where the repaired wheel goes.

A literal brace is written as ``{{`` or ``}}``.

.. code-block:: toml

    [hooks]
    post_configure = ["{python} ci/pyvista_build_hooks.py check {build_dir}"]
    post_build = ["{python} ci/prune_setup_py.py {build_dir}"]
    post_wheel = ["{python} ci/pyvista_build_hooks.py retag {build_dir}"]

``[defaults.<name>]``
---------------------
A named set of values for the command's own options, applied with
``pyvista-build <backend> --defaults <name>``. Nothing is read without the
flag. Keys are the option names without the leading dashes, values follow
the option's type, and a repeatable option such as ``opt`` takes a list.
``backend`` and ``defaults`` are not accepted as keys. Paths are relative to
the manifest's directory.

.. code-block:: toml

    [defaults.ci]
    yes = true
    source = "."
    opt = ["lto=0", "gate_o2=1"]

    [defaults.fast]
    source = "."
    opt = ["lto=0", "abi3=0"]

One set applies per run, and anything given on the command line wins over
it (``--opt`` and ``-D`` values from the set stay, with the command line's
own applied last). The set is read from the ``--source`` checkout's manifest,
else from a ``pyvista-build.toml`` in the current directory, else from the
manifest shipped for the backend. The build prints one line naming the file
and the values it applied, and an unknown set or key, or a value of the wrong
type, stops the command with the file's name.

Checking a Manifest
-------------------
A dry run loads the manifest and prints every command the build would run,
so it is the quickest check that a new manifest is accepted and does what
was meant:

.. code-block:: bash

    pyvista-build <name> --source . --dry-run
