# 0010 — Python package named `constellate`, not `kp`

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

The scaffold inherited `src/kp/` ("knowledge plane") from the prep sketch
without an explicit decision — flagged in review after phase 01 landed. The
package name is the import path in every file, the name on PyPI if the
project publishes (an explicit goal: open source, content, productization),
and part of how code reads to a stranger. Renaming later means touching every
import, doc, and published artifact; the cost only grows.

## Options considered

### Option A — keep `kp`
- Pros: two-character imports.
- Cons: opaque acronym — `import kp` tells a reader nothing; brand mismatch
  (Lyra/Orion/Hydra got named with care, the code lives in a mumble); `kp`
  is already taken on PyPI; same disease ADR 0009 cured for platforms.

### Option B — `knowledge_plane`
- Cons: long *and* underscored; names the concept, not the product — keeps
  the brand mismatch.

### Option C — `constellate`
- Pros: brand = import name (the Django/Flask convention);
  `from constellate.core import pipeline` reads as product code; PyPI-viable;
  consistent with the naming system.
- Cons: eleven characters — irrelevant with autocomplete.

## Decision

**We will name the package `constellate`, because the import name is product
surface and should carry the brand, not an acronym.** Scope: the Python
package; the domain term "knowledge plane" stays in prose and epithets.

## Consequences

- Easier: publishing, reading, teaching; one naming system everywhere.
- Harder: nothing — renamed while one PR was open and zero consumers existed.
- **Revisit trigger:** none; package renames after publication are
  effectively breaking — this is final.

## Related

- ADRs: [0009](0009-platform-codenames-constellations.md)
- PRs: #2
