#include "card_storage.h"
#include "picc/rc522_mifare.h"
#include <string.h>

static const rc522_mifare_key_t factory_key = {
    .type = RC522_MIFARE_KEY_A,
    .value = { RC522_MIFARE_KEY_VALUE_DEFAULT },
};

esp_err_t card_storage_read(rc522_handle_t scanner, rc522_picc_t *picc,
                            uint8_t record[CARD_RECORD_SIZE])
{
    if (picc->type != RC522_PICC_TYPE_MIFARE_1K) return ESP_ERR_NOT_SUPPORTED;
    esp_err_t result = ESP_OK;
    for (unsigned i = 0; i < CARD_DATA_BLOCK_COUNT; ++i) {
        uint8_t address = card_data_block(i);
        if (i % 3 == 0) result = rc522_mifare_auth(scanner, picc, address, &factory_key);
        if (result == ESP_OK) result = rc522_mifare_read(scanner, picc, address, record + i * 16);
        if (result != ESP_OK) break;
    }
    return result;
}

static esp_err_t write_block(rc522_handle_t scanner, rc522_picc_t *picc,
                             unsigned index, const uint8_t data[16])
{
    uint8_t address = card_data_block(index);
    /* Defensive guard even if the block mapping is changed in future. */
    if (address < 4 || address > 22 || address % 4 == 3) return ESP_ERR_INVALID_ARG;
    esp_err_t result = rc522_mifare_auth(scanner, picc, address, &factory_key);
    if (result == ESP_OK) result = rc522_mifare_write(scanner, picc, address, data);
    uint8_t actual[16] = {0};
    if (result == ESP_OK) result = rc522_mifare_read(scanner, picc, address, actual);
    if (result == ESP_OK && memcmp(actual, data, 16)) result = ESP_FAIL;
    memset(actual, 0, sizeof(actual));
    return result;
}

esp_err_t card_storage_write(rc522_handle_t scanner, rc522_picc_t *picc,
                             const uint8_t record[CARD_RECORD_SIZE])
{
    if (picc->type != RC522_PICC_TYPE_MIFARE_1K) return ESP_ERR_NOT_SUPPORTED;
    uint8_t invalid_header[16] = {0};
    /* Invalidate first, write payload, commit header last. Torn writes fail CRC. */
    esp_err_t result = write_block(scanner, picc, 0, invalid_header);
    for (unsigned i = 1; i < CARD_DATA_BLOCK_COUNT && result == ESP_OK; ++i)
        result = write_block(scanner, picc, i, record + i * 16);
    if (result == ESP_OK) result = write_block(scanner, picc, 0, record);
    uint8_t actual[CARD_RECORD_SIZE] = {0};
    if (result == ESP_OK) result = card_storage_read(scanner, picc, actual);
    if (result == ESP_OK && memcmp(actual, record, CARD_RECORD_SIZE)) result = ESP_FAIL;
    memset(actual, 0, sizeof(actual));
    return result;
}

esp_err_t card_storage_finish(rc522_handle_t scanner, rc522_picc_t *picc)
{
    return rc522_mifare_deauth(scanner, picc);
}
