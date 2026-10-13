# GitHub Distribution Plan

This runbook documents the GitHub-only distribution flow for `lab-registry-server`.
Colleagues install directly from the repository:

```bash
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp"
```

Pin a release tag when reproducibility matters:

```bash
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp@v0.3.0"
```

---

## 0) Distribution model

- Downloaded repository contents: MCP server only
- Source of truth: GitHub repository `Palo-IT-GitHub-Demos/lab-registry-mcp`
- Marketplace source: separate `GLOBAL-PALO-IT/gen-e2-marketplace` repository, fetched remotely by default
- Installation path: `pip install git+https://...`
- Optional release artifact: Git tag + GitHub Release with built wheel/sdist attached
- No PyPI or TestPyPI publication

---

## 1) Pre-release checklist

- [ ] `version` bumped in `pyproject.toml` if needed
- [ ] `README.md`, `TESTING.md`, and `TODO.md` are up to date
- [ ] `pytest tests/ -q` passes locally
- [ ] `python -m build` succeeds
- [ ] `python -m twine check dist/*` succeeds
- [ ] Remote GitHub repo exists and teammates have access

---

## 2) Local validation commands

```bash
cd lab-registry-mcp
source .venv/bin/activate

rm -rf dist build ./*.egg-info(N)
python -m pip install --upgrade pip
pip install -e ".[dev]" build twine
pytest tests/ -q
python -m build
python -m twine check dist/*
```

If you cloned under another folder name, adapt the `cd` command accordingly.

---

## 3) Push updates to GitHub

```bash
git push origin main
```

Repository already published: `https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp`

---

## 4) Tagged release

The current package version is `0.3.0` in `pyproject.toml`, with matching tag
`v0.3.0`. For future releases, bump the package version and push a tag using
the matching `vX.Y.Z` format; `release.yml` runs tests before building or
publishing.

```bash
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp@v0.3.0"
```

The GitHub Actions workflow runs `pytest tests/ -q`, builds the sdist and wheel,
runs `twine check`, then creates the GitHub Release and attaches `dist/*`.

Teammates can also install from `main`:

```bash
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp@main"
```

---

## 5) Teammate smoke test

```bash
python -m venv /tmp/lab-registry-git
source /tmp/lab-registry-git/bin/activate
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp"
lab-registry --help
```

Expected result: GitHub install succeeds without cloning manually, and `lab-registry --help` exits successfully.

---

## 6) Suggested usage policy

- Use `@main` for fast internal adoption.
- Use `@vX.Y.Z` for reproducible team setups.
- Bump patch version for docs/fixes, minor for new tools, major for breaking contract changes.