#include <stdio.h>
#include <string.h>
#include <esp_log.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"

#include "esp_event.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_http_server.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#include "rc522.h"
#include "driver/rc522_spi.h"
#include "rc522_picc.h"


static const char *TAG = "PBL5_RFID";


/* =========================================================
 * WIFI
 * ========================================================= */

#define WIFI_SSID       CONFIG_PBL5_LEGACY_WIFI_SSID

#define WIFI_PASSWORD   CONFIG_PBL5_LEGACY_WIFI_PASSWORD

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

#define MAX_RETRY 10

static EventGroupHandle_t wifi_event_group;

static int retry_num = 0;


/* =========================================================
 * RC522
 * ========================================================= */

#define RC522_GPIO_MISO 19
#define RC522_GPIO_MOSI 23
#define RC522_GPIO_SCLK 18
#define RC522_GPIO_SDA   5
#define RC522_GPIO_RST  22

static rc522_driver_handle_t driver;
static rc522_handle_t scanner;

static char current_store_id[10] = "";


/* =========================================================
 * BANG CAU HINH CUA HANG
 *
 * Day la du lieu mau cho PBL5. Khong dua mat khau Wi-Fi
 * that len GitHub hoac gui mat khau len Render.
 * ========================================================= */

typedef struct
{
    const char *uid;
    const char *wifi_ssid;
    const char *wifi_password;
    const char *host_url;
    const char *store_id;
} store_config_t;


static const store_config_t store_configs[] =
{
    {
        .uid = "CD 4B 1E 03",
        .wifi_ssid = "STORE001_WIFI",
        .wifi_password = "DEMO_PASS_001",
        .host_url = "https://pbl5-render-api.onrender.com",
        .store_id = "STORE001",
    },
    {
        .uid = "F0 78 0E 04",
        .wifi_ssid = "STORE002_WIFI",
        .wifi_password = "DEMO_PASS_002",
        .host_url = "https://pbl5-render-api.onrender.com",
        .store_id = "STORE002",
    },
    {
        .uid = "C7 9A 0C 03",
        .wifi_ssid = "STORE003_WIFI",
        .wifi_password = "DEMO_PASS_003",
        .host_url = "https://pbl5-render-api.onrender.com",
        .store_id = "STORE003",
    },
};


#define STORE_CONFIG_COUNT \
    (sizeof(store_configs) / sizeof(store_configs[0]))


static const store_config_t *current_store_config = NULL;


static rc522_spi_config_t driver_config =
{
    .host_id = SPI3_HOST,

    .bus_config = &(spi_bus_config_t)
    {
        .miso_io_num = RC522_GPIO_MISO,
        .mosi_io_num = RC522_GPIO_MOSI,
        .sclk_io_num = RC522_GPIO_SCLK,
    },

    .dev_config =
    {
        .spics_io_num = RC522_GPIO_SDA,
    },

    .rst_io_num = RC522_GPIO_RST,
};


/* =========================================================
 * WIFI EVENT
 * ========================================================= */

static void wifi_event_handler(
    void *arg,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data)
{
    /*
     * ESP32 bat dau Wi-Fi
     */
    if (event_base == WIFI_EVENT &&
        event_id == WIFI_EVENT_STA_START)
    {
        ESP_LOGI(
            TAG,
            "Wi-Fi bat dau ket noi..."
        );

        esp_wifi_connect();
    }


    /*
     * Wi-Fi bi mat ket noi
     */
    else if (
        event_base == WIFI_EVENT &&
        event_id == WIFI_EVENT_STA_DISCONNECTED)
    {
        if (retry_num < MAX_RETRY)
        {
            esp_wifi_connect();

            retry_num++;

            ESP_LOGI(
                TAG,
                "Dang thu ket noi lai... (%d/%d)",
                retry_num,
                MAX_RETRY
            );
        }
        else
        {
            ESP_LOGE(
                TAG,
                "Khong the ket noi Wi-Fi"
            );

            xEventGroupSetBits(
                wifi_event_group,
                WIFI_FAIL_BIT
            );
        }
    }


    /*
     * ESP32 da nhan duoc IP
     */
    else if (
        event_base == IP_EVENT &&
        event_id == IP_EVENT_STA_GOT_IP)
    {
        ip_event_got_ip_t *event =
            (ip_event_got_ip_t *)event_data;

        ESP_LOGI(
            TAG,
            "Da ket noi Wi-Fi!"
        );

        ESP_LOGI(
            TAG,
            "IP: " IPSTR,
            IP2STR(&event->ip_info.ip)
        );

        retry_num = 0;

        xEventGroupSetBits(
            wifi_event_group,
            WIFI_CONNECTED_BIT
        );
    }
}


/* =========================================================
 * KHOI TAO WIFI
 * ========================================================= */

static void __attribute__((unused)) wifi_init_sta(void)
{
    wifi_event_group =
        xEventGroupCreate();


    /*
     * Khoi tao TCP/IP stack
     */
    ESP_ERROR_CHECK(
        esp_netif_init()
    );


    /*
     * Tao event loop
     */
    ESP_ERROR_CHECK(
        esp_event_loop_create_default()
    );


    /*
     * Tao giao dien Wi-Fi Station
     */
    esp_netif_create_default_wifi_sta();


    /*
     * Khoi tao Wi-Fi driver
     */
    wifi_init_config_t cfg =
        WIFI_INIT_CONFIG_DEFAULT();

    ESP_ERROR_CHECK(
        esp_wifi_init(&cfg)
    );


    /*
     * Dang ky Wi-Fi event
     */
    ESP_ERROR_CHECK(
        esp_event_handler_register(
            WIFI_EVENT,
            ESP_EVENT_ANY_ID,
            &wifi_event_handler,
            NULL
        )
    );


    /*
     * Dang ky IP event
     */
    ESP_ERROR_CHECK(
        esp_event_handler_register(
            IP_EVENT,
            IP_EVENT_STA_GOT_IP,
            &wifi_event_handler,
            NULL
        )
    );


    /*
     * Cau hinh Wi-Fi
     */
    wifi_config_t wifi_config =
    {
        .sta =
        {
            .threshold.authmode =
                WIFI_AUTH_WPA2_PSK,
        },
    };


    strcpy(
        (char *)wifi_config.sta.ssid,
        WIFI_SSID
    );

    strcpy(
        (char *)wifi_config.sta.password,
        WIFI_PASSWORD
    );


    /*
     * Chon Station mode
     */
    ESP_ERROR_CHECK(
        esp_wifi_set_mode(WIFI_MODE_STA)
    );


    /*
     * Nap cau hinh Wi-Fi
     */
    ESP_ERROR_CHECK(
        esp_wifi_set_config(
            WIFI_IF_STA,
            &wifi_config
        )
    );


    /*
     * Bat Wi-Fi
     */
    ESP_ERROR_CHECK(
        esp_wifi_start()
    );


    ESP_LOGI(
        TAG,
        "Dang cho ESP32 ket noi Wi-Fi..."
    );


    /*
     * Cho ket qua ket noi
     */
    EventBits_t bits =
        xEventGroupWaitBits(
            wifi_event_group,
            WIFI_CONNECTED_BIT |
            WIFI_FAIL_BIT,
            pdFALSE,
            pdFALSE,
            portMAX_DELAY
        );


    if (bits & WIFI_CONNECTED_BIT)
    {
        ESP_LOGI(
            TAG,
            "=============================="
        );

        ESP_LOGI(
            TAG,
            "WIFI KET NOI THANH CONG"
        );

        ESP_LOGI(
            TAG,
            "=============================="
        );
    }
    else if (bits & WIFI_FAIL_BIT)
    {
        ESP_LOGE(
            TAG,
            "WIFI KET NOI THAT BAI"
        );
    }
}


/* =========================================================
 * TIM CAU HINH THEO UID RFID
 * ========================================================= */

static const store_config_t *find_store_config(const char *uid)
{
    for (size_t index = 0; index < STORE_CONFIG_COUNT; index++)
    {
        if (strcmp(uid, store_configs[index].uid) == 0)
        {
            return &store_configs[index];
        }
    }

    return NULL;
}


/* =========================================================
 * GUI CUA HANG VUA QUET LEN RENDER
 *
 * Khong gui wifi_password. Trang thai o buoc nay la
 * NOT_SWITCHED vi chua trien khai chuyen Wi-Fi tu dong.
 * ========================================================= */

static void send_store_update_task(void *parameter)
{
    const store_config_t *store_config =
        (const store_config_t *)parameter;

    EventBits_t wifi_bits =
        xEventGroupGetBits(wifi_event_group);

    if ((wifi_bits & WIFI_CONNECTED_BIT) == 0)
    {
        ESP_LOGW(
            TAG,
            "Chua co Wi-Fi, khong gui duoc RFID len Render"
        );

        vTaskDelete(NULL);
        return;
    }

    char update_url[256] = {0};
    char json_body[512] = {0};

    snprintf(
        update_url,
        sizeof(update_url),
        "%s/rfid_update.php",
        store_config->host_url
    );

    snprintf(
        json_body,
        sizeof(json_body),
        "{\"uid\":\"%s\","
        "\"store_id\":\"%s\","
        "\"wifi_ssid\":\"%s\","
        "\"host_url\":\"%s\","
        "\"wifi_status\":\"NOT_SWITCHED\"}",
        store_config->uid,
        store_config->store_id,
        store_config->wifi_ssid,
        store_config->host_url
    );

    esp_http_client_config_t client_config =
    {
        .url = update_url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 15000,
        .crt_bundle_attach = esp_crt_bundle_attach,
    };

    esp_http_client_handle_t client =
        esp_http_client_init(&client_config);

    if (client == NULL)
    {
        ESP_LOGE(TAG, "Khong tao duoc HTTP client");
        vTaskDelete(NULL);
        return;
    }

    esp_http_client_set_header(
        client,
        "Content-Type",
        "application/json"
    );

    esp_http_client_set_post_field(
        client,
        json_body,
        strlen(json_body)
    );

    ESP_LOGI(
        TAG,
        "Dang gui %s len Render...",
        store_config->store_id
    );

    esp_err_t result =
        esp_http_client_perform(client);

    if (result == ESP_OK)
    {
        int status_code =
            esp_http_client_get_status_code(client);

        ESP_LOGI(
            TAG,
            "Render HTTP status: %d",
            status_code
        );

        if (status_code == 200)
        {
            ESP_LOGI(
                TAG,
                "GUI TRANG THAI RFID LEN RENDER THANH CONG"
            );
        }
    }
    else
    {
        ESP_LOGE(
            TAG,
            "Gui Render that bai: %s",
            esp_err_to_name(result)
        );
    }

    esp_http_client_cleanup(client);
    vTaskDelete(NULL);
}


/* =========================================================
 * HTTP SERVER: GET /store
 * ========================================================= */

static esp_err_t store_get_handler(httpd_req_t *request)
{
    httpd_resp_set_type(
        request,
        "text/plain; charset=utf-8"
    );

    httpd_resp_set_hdr(
        request,
        "Access-Control-Allow-Origin",
        "*"
    );

    if (current_store_id[0] == '\0')
    {
        httpd_resp_set_status(
            request,
            "503 Service Unavailable"
        );

        return httpd_resp_sendstr(
            request,
            "NO_STORE"
        );
    }

    ESP_LOGI(
        TAG,
        "GET /store -> %s",
        current_store_id
    );

    return httpd_resp_sendstr(
        request,
        current_store_id
    );
}


static httpd_handle_t __attribute__((unused)) start_webserver(void)
{
    httpd_handle_t server = NULL;

    httpd_config_t config =
        HTTPD_DEFAULT_CONFIG();

    httpd_uri_t store_uri =
    {
        .uri = "/store",
        .method = HTTP_GET,
        .handler = store_get_handler,
        .user_ctx = NULL,
    };

    esp_err_t result =
        httpd_start(&server, &config);

    if (result == ESP_OK)
    {
        ESP_ERROR_CHECK(
            httpd_register_uri_handler(
                server,
                &store_uri
            )
        );

        ESP_LOGI(
            TAG,
            "HTTP SERVER DA SAN SANG"
        );

        ESP_LOGI(
            TAG,
            "Endpoint: http://<ESP32_IP>/store"
        );

        return server;
    }

    ESP_LOGE(
        TAG,
        "Khong khoi dong duoc HTTP server: %s",
        esp_err_to_name(result)
    );

    return NULL;
}


/* =========================================================
 * XU LY RFID
 * ========================================================= */

static void on_picc_state_changed(
    void *arg,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data)
{
    rc522_picc_state_changed_event_t *event =
        (rc522_picc_state_changed_event_t *)event_data;

    rc522_picc_t *picc = event->picc;


    /*
     * Phat hien the
     */
    if (picc->state == RC522_PICC_STATE_ACTIVE)
    {
        char uid[
            RC522_PICC_UID_STR_BUFFER_SIZE_MAX
        ] = {0};


        ESP_LOGI(
            TAG,
            "=============================="
        );

        ESP_LOGI(
            TAG,
            "DA PHAT HIEN THE RFID"
        );


        /*
         * In thong tin the
         */
        rc522_picc_print(picc);


        /*
         * Chuyen UID thanh chuoi
         */
        if (
            rc522_picc_uid_to_str(
                &picc->uid,
                uid,
                sizeof(uid)
            ) == ESP_OK
        )
        {
            ESP_LOGI(
                TAG,
                "UID: %s",
                uid
            );


            /*
             * Tim cau hinh cua hang tu UID
             */
#if CONFIG_PBL5_FIREBASE_USB
            /* UID comes from the card; store metadata is resolved by Python. */
            printf("RFID_UID:%s\n", uid);
            fflush(stdout);
            return;
#endif
            current_store_config =
                find_store_config(uid);


            if (current_store_config != NULL)
            {
                snprintf(
                    current_store_id,
                    sizeof(current_store_id),
                    "%s",
                    current_store_config->store_id
                );


                ESP_LOGI(
                    TAG,
                    "STORE ID: %s",
                    current_store_id
                );

                ESP_LOGI(
                    TAG,
                    "WIFI SSID (cau hinh): %s",
                    current_store_config->wifi_ssid
                );

                ESP_LOGI(
                    TAG,
                    "HOST URL: %s",
                    current_store_config->host_url
                );

                BaseType_t task_created =
                    xTaskCreate(
                        send_store_update_task,
                        "render_update",
                        8192,
                        (void *)current_store_config,
                        5,
                        NULL
                    );

                if (task_created != pdPASS)
                {
                    ESP_LOGE(
                        TAG,
                        "Khong tao duoc task gui Render"
                    );
                }
            }
            else
            {
                current_store_config = NULL;
                current_store_id[0] = '\0';

                ESP_LOGW(
                    TAG,
                    "THE RFID CHUA DUOC DANG KY"
                );
            }
        }
        else
        {
            current_store_config = NULL;
            current_store_id[0] = '\0';

            ESP_LOGW(
                TAG,
                "KHONG DOC DUOC UID"
            );
        }


        ESP_LOGI(
            TAG,
            "=============================="
        );
    }


    /*
     * The RFID duoc lay ra
     */
    else if (
        picc->state == RC522_PICC_STATE_IDLE &&
        event->old_state >= RC522_PICC_STATE_ACTIVE)
    {
        ESP_LOGI(
            TAG,
            "------------------------------"
        );

        ESP_LOGI(
            TAG,
            "DA LAY THE RFID RA"
        );

        ESP_LOGI(
            TAG,
            "------------------------------"
        );
    }
}


/* =========================================================
 * CHUONG TRINH CHINH
 * ========================================================= */

void app_main(void)
{
    ESP_LOGI(
        TAG,
        "=============================="
    );

    ESP_LOGI(
        TAG,
        "PBL5 RFID (transport configured in menuconfig)"
    );

    ESP_LOGI(
        TAG,
        "=============================="
    );


    /* =====================================================
     * KHOI TAO NVS
     * ===================================================== */

    esp_err_t ret =
        nvs_flash_init();

    if (
        ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND
    )
    {
        ESP_ERROR_CHECK(
            nvs_flash_erase()
        );

        ret = nvs_flash_init();
    }

    ESP_ERROR_CHECK(ret);


    /* =====================================================
     * KHOI TAO WIFI
     * ===================================================== */

#if !CONFIG_PBL5_FIREBASE_USB
    ESP_LOGI(
        TAG,
        "Khoi dong Wi-Fi..."
    );

    wifi_init_sta();


    /* =====================================================
     * KHOI TAO HTTP SERVER
     * ===================================================== */

    start_webserver();
#endif


    /* =====================================================
     * KHOI TAO RC522
     * ===================================================== */

    ESP_LOGI(
        TAG,
        "Khoi dong RC522..."
    );

    ESP_LOGI(
        TAG,
        "Dang cho the RFID..."
    );


    /*
     * Tao SPI driver
     */
    ESP_ERROR_CHECK(
        rc522_spi_create(
            &driver_config,
            &driver
        )
    );


    /*
     * Cai dat driver
     */
    ESP_ERROR_CHECK(
        rc522_driver_install(driver)
    );


    /*
     * Tao scanner
     */
    rc522_config_t scanner_config =
    {
        .driver = driver,
    };


    ESP_ERROR_CHECK(
        rc522_create(
            &scanner_config,
            &scanner
        )
    );


    /*
     * Dang ky su kien
     */
    ESP_ERROR_CHECK(
        rc522_register_events(
            scanner,
            RC522_EVENT_PICC_STATE_CHANGED,
            on_picc_state_changed,
            NULL
        )
    );


    /*
     * Bat dau quet
     */
    ESP_ERROR_CHECK(
        rc522_start(scanner)
    );


    ESP_LOGI(
        TAG,
        "RC522 DA SAN SANG"
    );

    ESP_LOGI(
        TAG,
        "Dang cho the RFID..."
    );
}
