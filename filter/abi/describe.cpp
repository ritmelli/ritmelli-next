// Writes the ring layout of ../apo/anel.h as this compiler lays it out. The check compares the file with
// ring.layout.json byte for byte, under g++ and under the cl that builds the filter.
// A field added to anel.h is listed here too: the listed sizes must add up to sizeof, or describe fails.
#include <stdio.h>

#include <iterator>

#include "../apo/anel.h"

struct Constant {
    const char* name;
    uint32_t value;
};

struct Field {
    const char* name;
    size_t offset;
    size_t size;
};

#define CONSTANT(name) Constant{#name, name}
#define FIELD(type, name) Field{#name, offsetof(type, name), sizeof(type::name)}

static const Constant constants[] = {
    CONSTANT(MICFX_PRESET_BYTES), CONSTANT(MICFX_TAXA), CONSTANT(MICFX_CANAIS), CONSTANT(MICFX_QUADROS),
    CONSTANT(MICFX_VOZ_QUADROS), CONSTANT(MICFX_LEITORES), CONSTANT(MICFX_BATIDA_MS), CONSTANT(MICFX_APP_MS),
    CONSTANT(MICFX_PISTA_QUADROS), CONSTANT(MICFX_PISTA_MS),
};

static const Field reader_fields[] = {
    FIELD(MicFxLeitor, lido), FIELD(MicFxLeitor, batida), FIELD(MicFxLeitor, dono),
    FIELD(MicFxLeitor, taxa), FIELD(MicFxLeitor, ep), FIELD(MicFxLeitor, reservado),
};

static const Field ring_fields[] = {
    FIELD(MicFxAnel, magia), FIELD(MicFxAnel, versao), FIELD(MicFxAnel, taxa),
    FIELD(MicFxAnel, canais), FIELD(MicFxAnel, quadros), FIELD(MicFxAnel, leitores),
    FIELD(MicFxAnel, escrito), FIELD(MicFxAnel, ganho), FIELD(MicFxAnel, sem_voz),
    FIELD(MicFxAnel, batida_app), FIELD(MicFxAnel, alvo), FIELD(MicFxAnel, voz_taxa),
    FIELD(MicFxAnel, voz_escrito), FIELD(MicFxAnel, leitor), FIELD(MicFxAnel, dados),
    FIELD(MicFxAnel, voz), FIELD(MicFxAnel, fx_escrito), FIELD(MicFxAnel, preset_seq),
    FIELD(MicFxAnel, preset_n), FIELD(MicFxAnel, preset_feito), FIELD(MicFxAnel, preset_erro),
    FIELD(MicFxAnel, voz_fx), FIELD(MicFxAnel, preset), FIELD(MicFxAnel, voz_dono),
    FIELD(MicFxAnel, fx_dono), FIELD(MicFxAnel, voz_batida), FIELD(MicFxAnel, fx_batida),
    FIELD(MicFxAnel, pista_ligada), FIELD(MicFxAnel, pista_reservado), FIELD(MicFxAnel, pista_escrito),
    FIELD(MicFxAnel, pista_batida), FIELD(MicFxAnel, pista_inicio), FIELD(MicFxAnel, pista_lido),
    FIELD(MicFxAnel, pista),
};

static const wchar_t* const hash_ids[] = {
    L"{00000000-0000-0000-0000-000000000000}",
    L"{A1B2C3D4-E5F6-4711-8899-AABBCCDDEEFF}",
};

static void put_ascii(FILE* f, const wchar_t* s) {
    for (; *s; s++) {
        if (*s == L'\\') {
            fputc('\\', f);
        }
        fputc((char)*s, f);
    }
}

template <size_t N>
static bool put_struct(FILE* f, const char* type, size_t size, const Field (&fields)[N]) {
    size_t sum = 0;
    fprintf(f, "  \"%s\": {\n    \"size\": %zu,\n    \"fields\": [\n", type, size);
    for (size_t i = 0; i < N; i++) {
        fprintf(f, "      {\"name\": \"%s\", \"offset\": %zu, \"size\": %zu}%s\n", fields[i].name,
                fields[i].offset, fields[i].size, i + 1 < N ? "," : "");
        sum += fields[i].size;
    }
    fprintf(f, "    ]\n  },\n");
    if (sum != size) {
        fprintf(stderr, "%s: the listed fields add up to %zu bytes, sizeof is %zu\n", type, sum, size);
    }
    return sum == size;
}

int main(int argc, char** argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: describe <out.json>\n");
        return 2;
    }
    FILE* f = fopen(argv[1], "wb");
    if (!f) {
        perror(argv[1]);
        return 1;
    }
    fprintf(f, "{\n  \"map\": \"");
    put_ascii(f, MICFX_MAPA);
    fprintf(f, "\",\n  \"magic\": %u,\n  \"version\": %u,\n  \"constants\": {\n", MICFX_MAGIA, MICFX_VERSAO);
    for (size_t i = 0; i < std::size(constants); i++) {
        fprintf(f, "    \"%s\": %u%s\n", constants[i].name, constants[i].value,
                i + 1 < std::size(constants) ? "," : "");
    }
    fprintf(f, "  },\n");
    bool sums = put_struct(f, "MicFxLeitor", sizeof(MicFxLeitor), reader_fields);
    sums = put_struct(f, "MicFxAnel", sizeof(MicFxAnel), ring_fields) && sums;
    fprintf(f, "  \"hash\": [\n");
    for (size_t i = 0; i < std::size(hash_ids); i++) {
        fprintf(f, "    {\"id\": \"");
        put_ascii(f, hash_ids[i]);
        fprintf(f, "\", \"value\": %u}%s\n", MicFxHash(hash_ids[i]), i + 1 < std::size(hash_ids) ? "," : "");
    }
    fprintf(f, "  ]\n}\n");
    return fclose(f) == 0 && sums ? 0 : 1;
}
