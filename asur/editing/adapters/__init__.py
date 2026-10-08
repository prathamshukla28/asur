"""EDITING media adapters - behind asur[generation].

This is the only place in the EDITING layer that touches a third-party media
library. Every adapter is a declaration-only shell: the heavy dependency
(OpenTimelineIO) is imported lazily inside the call, never at module level, so
the stdlib control path in ``asur.editing`` can import nothing from here and the
boundary import-linter skips this directory (any path with ``adapters`` in it).
Adapters are never called in CI (no network, no GPU, never a real render).
"""
