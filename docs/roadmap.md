# Roadmap

Status as of the last doc update. Tick items when done; remove ticked items after the next release.

## Release 0.1.0

- [ ] Create the public GitHub repo and push: `gh repo create hwei/git-nearest --public --source . --push`.
  **Confirm with the user first.**
- [ ] First CI run. The workflow has never run. Likely trouble: Python 3.8 syntax, Windows
  path/encoding in tests, a runner git older than 2.41 (fallback should cover it).
- [ ] Replace the hand-written README examples with a real screenshot or asciinema recording of a
  throwaway repo.
- [ ] Add GitHub topics: `git`, `git-tools`, `cli`, `branch`.
- [ ] PyPI via Trusted Publishing: add a publish workflow triggered by a version tag; the user registers
  the publisher on pypi.org once (walk them through it). Verify with `uv build` and
  `uv publish --dry-run` (or `twine check`) first. **Confirm before the first upload.**

## Later

- [ ] Optional: answer the Stack Overflow question "How to find the nearest parent of a Git branch"
  with a link, once the package is public. **Confirm with the user first.**
