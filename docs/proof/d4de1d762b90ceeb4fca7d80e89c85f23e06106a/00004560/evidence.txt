# OuterRecord::read_nested_word

The target is the Steam x86 `amrts.exe` with SHA-256 `34c9cacfcd42a816a5a9e886fbe18ae69ca2b82bdb7ed95588772f3079777b59`. The image base is `0x00400000`. The function occupies the half-open RVA interval `[0x4560, 0x456A)` in this build.

At VA `0x005CF85E` the caller sets ECX from EAX and at `0x005CF860` directly calls `0x00404560`. The callee loads a pointer from offset `0x14` of its receiver, loads a 32-bit value from offset `0x130` of that record into EAX and returns at `0x00404569`. The caller then tests EAX for zero. The class, function and field names in the reconstruction describe these observations. The original names, signedness and subsystem are unknown.

REA used Ghidra 12.1.4 on the pinned executable. The `read_function_instructions` observation for `0x00404560` has evidence ID `ev_af72c6d9f4ba1c7cf67c8271c31d1fd03bb757a636549275292234709d257287`. A `read_bytes` observation at the same address has evidence ID `ev_12086a9a4ced8d879f8ebd84fe63e97ed1e8df27c081a08d1a699d5a787f3291`.

From the repository root, run `python reconstruction/build.py --output function.bin`. The default toolchain is Visual Studio 2022 MSVC tools directory 14.44.35207, compiler 19.44.35229 targeting x86. The script compiles the reconstructed method in isolation and reads the single nonempty, relocation-free COFF text section. The script needs no access to the game. Supply `--compiler` to select an explicit x86-targeting cl.exe.

The emitted section measured 10 bytes, SHA-256 `c1ab50a72d6e5e66fe2053f8c261f45a49e3d17aaacfdc3fb9ab134fddcc29b1`. A direct comparison against the original PE mapping for RVA `0x4560` returned equality. These measurements cover this function body alone. Identifying the original compiler and reconstructing the surrounding translation unit and link layout remain open.
