// Names are inferred. The returned subobject type is unknown.
struct OuterRecord {
    unsigned char unknown_00[8];
    unsigned char* nested;
    void* address_at_nested_offset_14() const;
};

void* OuterRecord::address_at_nested_offset_14() const {
    return nested + 0x14;
}
