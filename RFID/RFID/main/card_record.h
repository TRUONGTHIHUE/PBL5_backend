#pragma once
#include <stdbool.h>
#include <stdint.h>

#define CARD_RECORD_SIZE 192
#define CARD_DATA_BLOCK_COUNT 12
typedef struct {
    char store_id[65];
    char ssid[33];
    char password[65];
} card_config_t;

/* Sector 1..4 data blocks only: never block 0 or sector trailers. */
uint8_t card_data_block(unsigned index);
bool card_record_encode(const card_config_t *config, uint8_t record[CARD_RECORD_SIZE]);
bool card_record_decode(const uint8_t record[CARD_RECORD_SIZE], card_config_t *config);
bool card_record_is_blank(const uint8_t record[CARD_RECORD_SIZE]);
