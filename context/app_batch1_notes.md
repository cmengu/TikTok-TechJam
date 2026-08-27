# app-batch-1 — running notes

Scratch notes for the `app-batch-1` branch. Findings that should survive until
PR time live here so they don't have to be re-derived.

## PR description drafts

### 1. `python -m app.server` was documented but broken

`context/Handoff.md:45` lists `python -m app.server` as the watch command for
the app. Before this branch that command did nothing useful — `app/server.py`
defined the FastAPI `app` object but had no uvicorn entrypoint, so running it as
a module imported the routes and exited without serving. This branch adds a
single `serve()` in `app/server.py`, called from both `app/__main__.py` and the
`__name__` guard in `server.py`, so the documented command now matches reality.

Do **not** edit `context/Handoff.md` — it is the teammate's phase doc. Mention
the fix in the PR description instead.

### 2. `node --test <directory>` does not scan the directory

Both spellings fail:

```
$ node --test app/static/
Error: Cannot find module '/Users/looyanting/TikTok-TechJam/app/static'
$ node --test app/static
Error: Cannot find module '/Users/looyanting/TikTok-TechJam/app/static'
```

Node treats a directory argument as an entry *file* to load rather than a tree
to scan for test files. Reproduced on Node 22.23 and 24.x, and on `main` before
this branch — so it is not a regression introduced here.

The correct spelling is the quoted glob:

```
node --test "app/static/*.test.js"
```

The quotes matter: they hand the glob to Node rather than letting the shell
expand it.

### 3. No `package.json` — module type is sniffed, not declared

The repo has no `package.json`, so Node classifies `.js` files as CommonJS. The
ESM `import` statements in `app/static` only work because Node >= 22.12 detects
ESM syntax and re-parses the file as a module. That is a fallback, not a
contract.

**PROPOSAL ONLY — not implemented in this branch.** A three-line `package.json`
would make the module type explicit and give the glob a name:

```json
{ "type": "module", "private": true,
  "scripts": { "test": "node --test \"app/static/*.test.js\"" } }
```

Then `npm test` replaces the glob everyone has to remember, and `.js` in this
repo is ESM by declaration instead of by syntax detection. Deferred so this
branch stays scoped to the Python entrypoints.

### 4. What `app/__init__.py` actually buys (premise correction)

The stated reason for adding `app/__init__.py` was that without it `python -m
app` only works from the repo root by cwd luck. That is **not** what happens in
this venv. Measured from `/tmp`, with and without the file:

```
### WITH app/__init__.py ###
app.__file__ = None
app.__main__ spec = True
### WITHOUT app/__init__.py (namespace pkg) ###
app.__file__ = None
app.__path__ = ['/Users/looyanting/TikTok-TechJam/app',
                '__editable__.beating_nise-0.0.0.finder.__path_hook__']
app.__main__ spec = True
```

`app.__main__` resolves from any cwd either way: the existing editable install
already mapped `app`, as a *namespace* package, via its finder's path hook.

The real payoff is at build time. `[tool.setuptools.packages.find]` uses
`find_packages`, not `find_namespace_packages`, and that only walks directories
containing an `__init__.py`:

```
### setuptools packages.find WITH __init__.py ###
['app', 'data', 'harness', 'harness.agents', 'harness.candidate', 'harness.tasks']
### WITHOUT __init__.py ###
['data', 'harness', 'harness.agents', 'harness.candidate', 'harness.tasks']
```

So `include = ["app*"]` in `pyproject.toml` was declaring a package that
discovery never returned. A built wheel or any non-editable install would have
shipped without `app` entirely; only the editable install's namespace path hook
was papering over it. The `__init__.py` makes the declaration true.

Note the venv's editable finder still pins `app` in its `NAMESPACES` dict — it
was generated before the `__init__.py` existed, which is why `app.__file__` is
still `None` above. A `pip install -e .` regenerates it as a regular package.
Not done on this branch; harmless either way for the editable install.
