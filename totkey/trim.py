#!/usr/bin/env python3
"""Totkey: keep only the languages in KEEP inside the APK.

The other languages' data is not deleted from anywhere: it stays in TitanKeys' source at the pinned tag (UPSTREAM_REF).
To bring a language back, add its id to KEEP (and its Rime schema to KEEP_SCHEMAS) and build again.

English is built in (assets/swipe, im/languages.json "en") and has no folder under im/, so it is not listed.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

KEEP = {"vi", "zh-pinyin"}
KEEP_SCHEMAS = {"tk_pinyin"}
# languages.json is keyed by language (zh covers every Chinese method), index.json by input method.
KEEP_LANGUAGES = {"$global", "en", "vi", "zh"}

assets = Path("android/assets")
im = assets / "im"

# Input methods: the index, the language pages, and each removed method's folder.
index = json.loads((im / "index.json").read_text())
removed = [entry["id"] for entry in index if entry["id"] not in KEEP]
(im / "index.json").write_text(json.dumps([e for e in index if e["id"] in KEEP], ensure_ascii=False, indent=1) + "\n")
languages = json.loads((im / "languages.json").read_text())
(im / "languages.json").write_text(
    json.dumps({k: v for k, v in languages.items() if k in KEEP_LANGUAGES}, ensure_ascii=False, indent=1) + "\n")
for method in removed:
    shutil.rmtree(im / method, ignore_errors=True)

# Japanese (Mozc): its dictionary only.
shutil.rmtree(assets / "mozc", ignore_errors=True)

# Rime: only the kept schemas' files, and the shared ones.
rime = assets / "rime"
groups = {}
for line in (assets / "rime.schemas").read_text().splitlines():
    if "\t" in line:
        schema, path = line.split("\t", 1)
        groups.setdefault(schema, set()).add(path)
needed = set().union(*(groups[s] for s in KEEP_SCHEMAS))
gone = set().union(*(paths for s, paths in groups.items() if s not in KEEP_SCHEMAS)) - needed
for schema in groups:
    if schema not in KEEP_SCHEMAS:
        gone |= {f"{schema}.schema.yaml", f"build/{schema}.schema.yaml", f"build/{schema}.prism.bin"}
# Files only the removed Cantonese schemas include.
gone |= {"symbols_cantonese.yaml", "tk_jyutping_algebra.yaml", "tk_jyutping_algebra_strict.yaml"}
for path in gone:
    (rime / path).unlink(missing_ok=True)

for default in (rime / "default.yaml", rime / "build" / "default.yaml"):
    text = default.read_text()
    text = re.sub(r"(schema_list:\n)((?:  - schema: \S+\n)+)",
                  lambda m: m.group(1) + "".join(f"  - schema: {s}\n" for s in sorted(KEEP_SCHEMAS)), text)
    default.write_text(text)

(assets / "rime.schemas").write_text("".join(
    f"{schema}\t{path}\n" for schema in sorted(KEEP_SCHEMAS) for path in sorted(groups[schema])))

manifest = []
for line in (assets / "rime.sha256").read_text().splitlines():
    if not line.strip():
        continue
    path = line.split("  ", 1)[1]
    file = rime / path
    if file.exists():
        manifest.append(f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {path}")
(assets / "rime.sha256").write_text("\n".join(manifest) + "\n")

print("Kept input methods:", sorted(KEEP), "Removed:", removed)
print("Rime files removed:", sorted(gone))
