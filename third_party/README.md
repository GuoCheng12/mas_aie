# Third-Party Runtime Dependencies

This directory is reserved for local runtime dependencies that are not
version-controlled in this repository.

Expected Linux layout:

- `third_party/Amesp/`
- `third_party/PyAmesp/`

Guidelines:

- Keep the actual Amesp distribution and the PyAmesp source tree here on the
  target Linux machine.
- Do not commit these two directories into this repository.
- `git pull` is expected to update tracked project files while leaving the
  local `third_party/Amesp` and `third_party/PyAmesp` trees untouched.
- If `third_party/PyAmesp/` contains its own `.git/`, that is acceptable for
  local use because the entire directory is ignored by this repository.

Suggested Linux setup:

```bash
export PATH="$PWD/third_party/Amesp/Bin:$PATH"
python -m pip install -e "$PWD/third_party/PyAmesp"
```

Future runtime integration should treat these paths as configurable local
dependencies rather than tracked source files.
