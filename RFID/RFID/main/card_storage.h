#pragma once
#include "card_record.h"
#include "rc522.h"
#include "rc522_picc.h"

esp_err_t card_storage_read(rc522_handle_t scanner, rc522_picc_t *picc,
                            uint8_t record[CARD_RECORD_SIZE]);
esp_err_t card_storage_write(rc522_handle_t scanner, rc522_picc_t *picc,
                             const uint8_t record[CARD_RECORD_SIZE]);
/* Finish once after all read/write/verify operations for the selected card. */
esp_err_t card_storage_finish(rc522_handle_t scanner, rc522_picc_t *picc);
