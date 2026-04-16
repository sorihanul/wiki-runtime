# GitHub Publishing

This document defines how a local working repository is turned into this public repository.

The public package is a filtered derivative.
It is meant to show a reusable wiki-runtime structure, not to claim that every local environment is bundled here.

## Source Rule

- working source of truth: a separate local working repository
- public derivative: this repository
- research draft: any private or draft workspace that is not meant for publication

Do not publish from the draft workspace.

## What Should Stay Public

- entry documents such as `README.md`, `START_HERE.md`, `MAP.md`
- policy documents
- runtime scripts under `scripts/`
- templates under `templates/`
- minimal safe sample surfaces
- folder structure for `wiki`, `wiki_lite`, `retrieval`, `reports`, and `validation`

## What Should Stay Out

- absolute local paths inside notes or templates
- live private source material under `wiki_lite/RAW`
- live operating notes that expose private knowledge
- generated databases and transient retrieval build artifacts
- runtime-only state files that are not useful as public source

## Pre-Publish Check

1. `python "./scripts/wiki_runtime.py" status`
2. `powershell -ExecutionPolicy Bypass -File "./scripts/validate.ps1"`
3. confirm retrieval wiring does not depend on a private absolute path
4. confirm `.gitignore` excludes generated databases and build artifacts
5. confirm sample notes and templates do not contain personal or machine-specific paths
6. review `./PUBLIC_RELEASE_CHECKLIST.md`

## Retrieval Wiring

Use one of these:

- environment variable `WIKI_RETRIEVAL_SCRIPT`
- `./vendor/ivk2_improved.py`

The legacy alias `WIKI_IVK2_SCRIPT` is still accepted.

## Publishing Rule

- keep the public package centered on `wiki quality`, not internal experimentation
- prefer structure, scripts, templates, and clear entry docs over live operating residue
- if public-facing explanation needs to be simpler than the working runtime, simplify it here

## One-Line Standard

The public repository should read like a stable wiki-runtime reference package, not like an internal lab dump.
