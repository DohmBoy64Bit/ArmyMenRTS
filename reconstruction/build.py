"""Compile the reconstructed function and extract its standalone COFF code section."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import tempfile


def locate_compiler():
    root = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    candidates = sorted(root.glob(
        "Microsoft Visual Studio/*/*/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x86/cl.exe"
    ))
    if not candidates:
        raise SystemExit("Supply --compiler with the path to an x86-targeting MSVC cl.exe")
    return candidates[0]


def function_code(obj):
    machine, count = struct.unpack_from("<HH", obj)
    optional_size = struct.unpack_from("<H", obj, 16)[0]
    if machine != 0x14c or optional_size != 0:
        raise ValueError("Expected an i386 COFF object")
    sections = []
    for index in range(count):
        header = 20 + 40 * index
        if obj[header:header + 8].rstrip(b"\0").split(b"$", 1)[0] != b".text":
            continue
        size, offset = struct.unpack_from("<II", obj, header + 16)
        if not size:
            continue
        relocations = struct.unpack_from("<H", obj, header + 32)[0]
        if relocations or offset + size > len(obj):
            raise ValueError("Expected complete, relocation-free code")
        sections.append(obj[offset:offset + size])
    if len(sections) != 1:
        raise ValueError("Expected exactly one nonempty .text section")
    return sections[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compiler", type=Path)
    args = parser.parse_args()
    compiler = (args.compiler or locate_compiler()).resolve()
    source = Path(__file__).with_name("read_nested_word.cpp").resolve()
    env = {k: v for k, v in os.environ.items() if k.upper() not in {"CL", "_CL_"}}
    with tempfile.TemporaryDirectory() as tmp:
        obj = Path(tmp) / "function.obj"
        subprocess.run([str(compiler), "/nologo", "/c", "/O1", "/Gy-", "/GS-", "/Zl",
                        "/Fo" + str(obj), str(source)], cwd=tmp, env=env, check=True)
        code = function_code(obj.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(code)


if __name__ == "__main__":
    main()
