// Layout names are descriptive. Only these two field offsets are established.
struct NestedRecord {
    unsigned char unknown_000[0x130];
    unsigned int word_130;
};

struct OuterRecord {
    unsigned char unknown_00[0x14];
    const NestedRecord* record_14;
    unsigned int read_nested_word() const;
};

static_assert(sizeof(void*) == 4, "Compile for x86");
static_assert(sizeof(unsigned int) == 4, "Expected a 32-bit word");

unsigned int OuterRecord::read_nested_word() const {
    return record_14->word_130;
}
