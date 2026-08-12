# Repository libraries

`libs/` contains every Rust library whose source is maintained as part of the
CodeDesk repository. This includes CodeDesk-owned crates such as `hbb_common`
and pinned source snapshots of libraries that were previously Cargo Git
dependencies.

The imported library revisions are recorded in `sources.json`. Each imported
directory also contains a `.codedesk-source.json` marker with its upstream URL
and commit. Cargo manifests use local `path` dependencies only, so normal
builds do not clone Git repositories.

To import missing libraries or refresh selected libraries after changing their
commit in `sources.json`, run:

```powershell
./scripts/sync_lib_sources.ps1
./scripts/sync_lib_sources.ps1 -Names hwcodec,cpal -Refresh
```

The sync script downloads immutable source archives, recursively imports active
submodules, materializes archive symlinks for cross-platform checkouts, and
applies the local Cargo path replacements declared in `sources.json`.

The `wezterm` entry is intentionally sparse: CodeDesk uses only its
`portable-pty` and `filedescriptor` crates, so unrelated terminal application
sources and assets are not copied into this repository.

After changing a source revision, regenerate the affected Cargo lockfiles and
run `make check-local-deps` to ensure no Cargo Git dependencies were
reintroduced.
