#include "card_record.h"
#include <string.h>
#include <ctype.h>

uint8_t card_data_block(unsigned index)
{
    return index < CARD_DATA_BLOCK_COUNT ? (uint8_t)(4 + (index / 3) * 4 + index % 3) : 255;
}

static uint32_t checksum(const uint8_t *record)
{
    uint32_t crc = 0xffffffffu;
    for (unsigned i = 0; i < CARD_RECORD_SIZE; ++i) {
        if (i >= 8 && i < 12) continue;
        crc ^= record[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320u : 0);
    }
    return crc ^ 0xffffffffu;
}

static bool text(const char *value, size_t min, size_t max)
{
    size_t n = strnlen(value, max + 1);
    if (n < min || n > max) return false;
    for (size_t i = 0; i < n; ++i)
        if ((unsigned char)value[i] < 32 || (unsigned char)value[i] == 127) return false;
    return true;
}

static bool valid(const card_config_t *c)
{
    if (!text(c->store_id, 1, 64) || !text(c->ssid, 1, 32) || !text(c->password, 0, 64))
        return false;
    size_t n = strlen(c->password);
    if (n && n < 8) return false;
    if (n == 64)
        for (size_t i = 0; i < n; ++i)
            if (!isxdigit((unsigned char)c->password[i])) return false;
    return true;
}

bool card_record_encode(const card_config_t *c, uint8_t record[CARD_RECORD_SIZE])
{
    if (!c || !record || !valid(c)) return false;
    memset(record, 0, CARD_RECORD_SIZE);
    memcpy(record, "P5W1", 4);
    record[4] = 1;
    record[5] = strlen(c->store_id);
    record[6] = strlen(c->ssid);
    record[7] = strlen(c->password);
    size_t offset = 16;
    memcpy(record + offset, c->store_id, record[5]); offset += record[5];
    memcpy(record + offset, c->ssid, record[6]); offset += record[6];
    memcpy(record + offset, c->password, record[7]);
    uint32_t crc = checksum(record);
    for (unsigned i = 0; i < 4; ++i) record[8 + i] = (crc >> (8 * i)) & 0xff;
    return true;
}

bool card_record_decode(const uint8_t record[CARD_RECORD_SIZE], card_config_t *c)
{
    if (!record || !c) return false;
    memset(c, 0, sizeof(*c));
    if (memcmp(record, "P5W1", 4) || record[4] != 1 ||
        !record[5] || record[5] > 64 || !record[6] || record[6] > 32 || record[7] > 64)
        return false;
    uint32_t expected = 0;
    for (unsigned i = 0; i < 4; ++i) expected |= (uint32_t)record[8 + i] << (8 * i);
    if (expected != checksum(record)) return false;
    size_t offset = 16;
    memcpy(c->store_id, record + offset, record[5]); offset += record[5];
    memcpy(c->ssid, record + offset, record[6]); offset += record[6];
    memcpy(c->password, record + offset, record[7]);
    /* Embedded NUL must not silently truncate a declared field. */
    if (strlen(c->store_id) != record[5] || strlen(c->ssid) != record[6] ||
        strlen(c->password) != record[7] || !valid(c)) {
        memset(c, 0, sizeof(*c));
        return false;
    }
    return true;
}

bool card_record_is_blank(const uint8_t record[CARD_RECORD_SIZE])
{
    bool zero = true, ones = true;
    for (unsigned i = 0; i < CARD_RECORD_SIZE; ++i) {
        zero &= record[i] == 0;
        ones &= record[i] == 0xff;
    }
    return zero || ones;
}
