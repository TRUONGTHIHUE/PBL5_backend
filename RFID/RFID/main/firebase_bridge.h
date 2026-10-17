#pragma once
#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"
#include "card_record.h"

esp_err_t firebase_bridge_init(void);
void firebase_bridge_scan(const char *uid);
/* Only returns a store while its Wi-Fi connection has an IP address. */
bool firebase_bridge_connected_store(char *destination, size_t size);
bool firebase_bridge_card_config(const char *uid, const card_config_t *config);
bool firebase_bridge_prepare_card(const char *uid);
