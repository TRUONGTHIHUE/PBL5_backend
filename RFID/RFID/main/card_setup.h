#pragma once
#include "rc522.h"
#include "rc522_picc.h"

esp_err_t card_setup_init(void);
void card_setup_scan(rc522_handle_t scanner, rc522_picc_t *picc, const char *uid);
