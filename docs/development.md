# Development

## Setup

```console
uv sync                 # creates .venv with pytest (dev group)
uv run pytest           # all tests
uv run pytest -k graph  # a subset
```

`uv.lock` is gitignored on purpose: the package has no runtime dependencies and pytest is the only
dev dependency.

CI (`.github/workflows/test.yml`) runs `uv run pytest -q` on ubuntu / windows / macos × Python 3.8 / 3.13.

## README examples

After changing output, run `uv run python scripts/demo.py` and paste both blocks into `README.md`.
The output is deterministic; if it changes without an output change, something is off.

## Tests

`tests/conftest.py` provides a `Repo` helper that creates throwaway repositories with an isolated git
config (`GIT_CONFIG_GLOBAL` / `GIT_CONFIG_SYSTEM` set to the null device) and fixed author identity.
Use it for every test that needs history; do not depend on the developer's git config.

## Gotchas

- **Every test commit needs a unique message.** Two branches committing from the same parent in the
  same second with the same message produce byte-identical commits, which silently merges the branches
  and makes counts flaky. `Repo.commit()` numbers messages for this reason; keep it.
- **`git()` strips stdout by default**, which eats the leading space of ` M file` in porcelain output.
  `status.read()` passes `strip=False`. Do the same for any whitespace-significant output.
- **`git status` is the slow part** on large repositories (a few hundred ms), hence `--no-status`.
- **Windows console:** the legacy console needs `os.system("")` to enable ANSI. When stdout is not a
  TTY it is reconfigured to UTF-8. On a TTY, Python writes through the console API, so `↑↓○│├╯`
  render regardless of code page.
- **`NO_COLOR` may be set in agent sandboxes.** Use `--color always` to see escapes.
- **Old git:** `%(ahead-behind:...)` needs git 2.41. Test the fallback with `refs.rank(n, native=False)`.
