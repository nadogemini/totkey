#!/usr/bin/env python3
"""Totkey: puts sherpa-onnx (on-device dictation) into the TitanKeys source tree.

Usage: python3 sherpa.py <sherpa-onnx.aar> <android dir>

- Java classes: <android>/libs/sherpa-onnx.jar
- arm64 libraries: <android>/jniLibs/arm64-v8a/libsherpa-onnx-jni.so and its ONNX Runtime as libsherpa-ort.so.

TitanKeys' swipe engine already ships ONNX Runtime 1.23.2 as libonnxruntime.so; sherpa-onnx brings 1.28.2 under the same
name, and each one's symbols carry its own version, so one can't stand in for the other. sherpa's copy is renamed: its
SONAME, and the name sherpa's JNI library asks for, both become libsherpa-ort.so (one character shorter, so the string table
keeps its size; the spare byte is a NUL). Nothing else in either library changes.
"""
import struct
import sys
import zipfile
from pathlib import Path

OLD = b"libonnxruntime.so\0"
NEW = b"libsherpa-ort.so\0"
assert len(NEW) <= len(OLD)


def dynstr_range(data: bytes):
    """The file offsets of .dynstr in a 64-bit little-endian ELF."""
    assert data[:4] == b"\x7fELF" and data[4] == 2 and data[5] == 1, "not a 64-bit little-endian ELF"
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    def section(i):
        name, kind, flags, addr, offset, size = struct.unpack_from("<IIQQQQ", data, shoff + i * shentsize)
        return name, kind, offset, size
    _, _, stroff, _ = section(shstrndx)
    for i in range(shnum):
        name, kind, offset, size = section(i)
        end = data.index(b"\0", stroff + name)
        if data[stroff + name:end] == b".dynstr":
            return offset, offset + size
    raise SystemExit("no .dynstr")


def rename(data: bytes) -> bytes:
    start, end = dynstr_range(data)
    table = data[start:end]
    count = table.count(OLD)
    # The name must stand alone in the table (not the tail of a longer string).
    at = table.find(OLD)
    if count != 1 or (at > 0 and table[at - 1] != 0):
        raise SystemExit(f"expected one {OLD!r} in .dynstr, found {count}")
    patched = table[:at] + NEW + b"\0" * (len(OLD) - len(NEW)) + table[at + len(OLD):]
    assert len(patched) == len(table)
    return data[:start] + patched + data[end:]


def main(aar: str, android: str):
    out = Path(android)
    libs = out / "libs"
    jni = out / "jniLibs" / "arm64-v8a"
    libs.mkdir(parents=True, exist_ok=True)
    jni.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(aar) as archive:
        (libs / "sherpa-onnx.jar").write_bytes(archive.read("classes.jar"))
        (jni / "libsherpa-onnx-jni.so").write_bytes(rename(archive.read("jni/arm64-v8a/libsherpa-onnx-jni.so")))
        (jni / "libsherpa-ort.so").write_bytes(rename(archive.read("jni/arm64-v8a/libonnxruntime.so")))
    print("sherpa-onnx: classes, libsherpa-onnx-jni.so and libsherpa-ort.so in place")


if __name__ == "__main__":
    main(*sys.argv[1:3])
