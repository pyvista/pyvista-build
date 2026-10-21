# pyvista-build

Build a VTK backend wheel for [PyVista](https://github.com/pyvista/pyvista) from source,
guided step by step.

```bash
uv venv
uvx pyvista-build vtk --python .venv/bin/python --install
uv pip install --python .venv/bin/python pyvista
```

`pyvista-build BACKEND` clones the backend, checks the tools it needs and offers to
install the missing ones, configures it with CMake, compiles it, packages the wheel,
bundles the libraries it links against, and installs it into the interpreter given with
`--python`. It asks once before starting and prints every command as it runs.
`--interactive` asks before each step, `--dry-run` prints the commands and runs nothing,
and `--manylinux` runs the build inside a manylinux container for a portable Linux wheel.

Each backend describes its build in a `pyvista-build.toml` manifest at the root of its
source tree. A manifest for stock VTK is shipped here, and `pyvista-build cvista` reads
the one in the [cvista](https://github.com/pyvista/cvista) tree. Any other backend builds
with `--url <git url>` or `--source <checkout>` when its tree carries a manifest.

The package depends on neither `vtk` nor `pyvista`, so it runs in an environment that
has no VTK yet.

## Development

```bash
uv sync --group dev
uv run pytest
uv run mypy
uv run pre-commit run --all-files
uv run --group docs sphinx-build -W doc doc/_build/html
```
