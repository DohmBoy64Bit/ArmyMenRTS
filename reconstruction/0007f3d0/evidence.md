# Inferred nested address accessor

The Steam x86 amrts.exe has SHA-256 34c9cacfcd42a816a5a9e886fbe18ae69ca2b82bdb7ed95588772f3079777b59. Subtracting the PE image base 0x400000 from the REA addresses gives the inclusive body at RVA 0x7f3d0 through 0x7f3d6.

REA instruction evidence ev_fc39b76b779273aa3044a8f0d955c6c177ad3ee1da8bcc0e50fff7326698d1ad identifies a single range. MOV loads EAX from [ECX + 8], ADD advances the result by 0x14 bytes, and RET ends the function. A direct relative CALL at RVA 0x7f400 targets the first instruction.

The source models ECX as an x86 member-function receiver. The class, method and field names are inferred. The nested object type and returned subobject type are unknown. The body has no external address operands or unresolved references.

The local build used x86 MSVC toolset 14.44.35207 with cl.exe /nologo /c /O1 /Gy- /GS- /Zl /Fo<temporary-object> nested_address.cpp. The builder extracted one relocation-free COFF code section. All seven emitted bytes matched the pinned executable on the first build.
