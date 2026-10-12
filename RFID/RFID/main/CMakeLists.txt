idf_component_register(SRCS "main.c"
                    INCLUDE_DIRS "."
                    REQUIRES esp_http_client esp_http_server esp_wifi esp_event esp_netif mbedtls nvs_flash)
