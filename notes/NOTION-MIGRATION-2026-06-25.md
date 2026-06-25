# Notion → erebos migration log (2026-06-25)

Migrated the Dom1 / Erebos content out of Notion (Cognate Quarters → **Coding** DB
+ one loose page) by Vector. Creative/Dom2 content (Writing DB) explicitly NOT in
scope. Source pages left intact in Notion.

## Architecture docs → `research/`
- Erebos: Multi-Nodule Use Cases → `erebos-multi-nodule-use-cases.md`
- Erebos: Pipeline-Parallel Composite Nodule (loose page) → `erebos-pipeline-parallel-composite-nodule.md`

## Working notes → `notes/`
- Device and Network Naming Scheme (Greek-underworld homelab map) → `device-and-network-naming-scheme.md`
- Erebos Code Sync Notes (May 1) → `erebos-code-sync-notes-2026-05-01.md`
- G700 Setup: Network-Local Testing Client → `erebos-g700-network-local-testing-client.md`

## Trackable items → Dom1 active-blocks (lean index + block file)
- Bug: Nodule Schema Inconsistency → `domain1-erebos-nodule-schema-inconsistency` (P3, planned)
- Erebos CLI Quick Fixes → `domain1-erebos-cli-quick-fixes` (P3, planned)
- Erebos Network Testing Checklist → `domain1-erebos-network-testing-checklist` (P3, active)

## Drift check — already-migrated docs (NO content drift; left as-is)
- Provider Abstraction Architecture — identical to `research/erebos-provider-abstraction-architecture.md`
- Nodule Protocol — identical to `research/erebos-llm-nodule-protocol.md`
- Orchestration Architecture — identical to `research/erebos-orchestration-architecture.md`

  Note: the recent Notion "Updated" timestamps on Orchestration (06-24) and Nodule
  Protocol (06-14) are **comment threads**, not content edits. Those discussions were
  NOT migrated — pull via notion get-comments if the notes matter.

## Notion cleanup (operator's call)
Source pages can be archived/deleted in Notion now that content is local. The Erebos
docs in the Notion recents are fully accounted for here.
