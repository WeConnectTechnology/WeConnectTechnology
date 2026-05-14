#!/usr/bin/env python3
"""Rewrite Anypoint-style $ref paths to filesystem-relative paths.

Anypoint conventions:
  - "/foo/bar.yaml" => relative to nearest project root. Project root is the
    enclosing exchange_modules/<group>/<asset>/<version>/ if the file lives
    inside one, otherwise the API root.
  - "../../foo" that escapes the API root => clamp to API root (Anypoint
    quirk where extra .. segments are absorbed).
  - Other relative paths => normal filesystem resolution from the file's dir.
  - "#/..." internal refs => left alone.
"""

import os
import re
import sys
from pathlib import Path

API_ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

REF_RE = re.compile(r'''(\$ref:\s*)(["'])([^"']+)\2''')


def module_root_for(file_path: Path):
    parts = file_path.resolve().relative_to(API_ROOT).parts
    if len(parts) >= 4 and parts[0] == "exchange_modules":
        return API_ROOT.joinpath(*parts[:4])
    return None


def resolve_target(file_path: Path, ref_path: str) -> Path:
    """Try multiple Anypoint-flavored roots; return the first candidate that
    exists on disk, otherwise the most likely candidate."""
    stripped = ref_path.lstrip("/")
    mod = module_root_for(file_path)

    candidates = []
    candidates.append((file_path.parent / ref_path).resolve())
    if mod:
        candidates.append((mod / stripped).resolve())
    candidates.append((API_ROOT / stripped).resolve())
    m = re.match(r"^(?:\.\./)+(.*)$", ref_path)
    if m:
        candidates.append((API_ROOT / m.group(1)).resolve())

    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def rewrite(file_path: Path, ref: str) -> str:
    if ref.startswith("#"):
        return ref
    if "#" in ref:
        path_part, hash_part = ref.split("#", 1)
        hash_suffix = "#" + hash_part
    else:
        path_part, hash_suffix = ref, ""
    target = resolve_target(file_path, path_part)
    if not target.exists():
        print(f"  WARN missing: {ref}  ->  {target}", file=sys.stderr)
    rel = os.path.relpath(target, start=file_path.parent.resolve())
    return rel + hash_suffix


MAPPING_HEADER_RE = re.compile(r'^(\s*)mapping:\s*$')
MAPPING_VALUE_RE = re.compile(r'''^(\s+)([A-Za-z0-9_.-]+):\s*(["'])([^"']+)\3\s*$''')


def rewrite_discriminator_mappings(file_path: Path, text: str) -> str:
    """Rewrite the string values under `discriminator.mapping:` blocks too.
    These values are URI-style refs (per OAS 3.0) but never appear behind a
    `$ref:` key, so the main regex misses them."""
    out_lines = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        m = MAPPING_HEADER_RE.match(line.rstrip("\n"))
        if not m:
            out_lines.append(line)
            i += 1
            continue
        header_indent = len(m.group(1))
        out_lines.append(line)
        i += 1
        while i < len(lines):
            inner = lines[i]
            stripped = inner.lstrip(" ")
            indent = len(inner) - len(stripped)
            if stripped.strip() == "" or indent <= header_indent:
                break
            vm = MAPPING_VALUE_RE.match(inner.rstrip("\n"))
            if vm:
                lead, name, quote, ref = vm.group(1), vm.group(2), vm.group(3), vm.group(4)
                new_ref = rewrite(file_path, ref)
                inner = f"{lead}{name}: {quote}{new_ref}{quote}\n"
            out_lines.append(inner)
            i += 1
    return "".join(out_lines)


changed = 0
for yf in API_ROOT.rglob("*.yaml"):
    original = yf.read_text()

    def sub(m):
        prefix, quote, ref = m.group(1), m.group(2), m.group(3)
        return f"{prefix}{quote}{rewrite(yf, ref)}{quote}"

    new = REF_RE.sub(sub, original)
    new = rewrite_discriminator_mappings(yf, new)
    if new != original:
        yf.write_text(new)
        changed += 1
        print(f"rewrote refs in {yf.relative_to(API_ROOT)}")

print(f"\nTotal files rewritten: {changed}")
