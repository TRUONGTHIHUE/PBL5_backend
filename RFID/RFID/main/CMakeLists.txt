idf_component_register(SRCS "main.c" "firebase_bridge.c" "card_record.c" "card_storage.c" "card_setup.c"
                    INCLUDE_DIRS "."
                    REQUIRES esp_http_client esp_http_server esp_wifi esp_event esp_netif mbedtls nvs_flash json esp_driver_uart esp_timer)
