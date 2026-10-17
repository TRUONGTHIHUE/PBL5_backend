#include "firebase_bridge.h"
#include "sdkconfig.h"

#if CONFIG_PBL5_FIREBASE_USB || CONFIG_PBL5_CARD_WIFI
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include "cJSON.h"
#include "driver/uart.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#if !CONFIG_ESP_CONSOLE_UART_DEFAULT || CONFIG_ESP_CONSOLE_UART_NUM != 0
#error "This demo requires the ESP32 UART0 console over USB-UART, not USB-JTAG/custom UART"
#endif

#define FRAME_LIMIT 2048
#define GOT_IP BIT0
#define STARTED BIT1
#define STOPPED BIT2
#define LOOKUP_SECONDS 60

typedef enum { IDLE, WAIT_CONFIG, CONNECTING } phase_t;
static SemaphoreHandle_t lock;
static EventGroupHandle_t events;
static phase_t phase;
static char request_id[32], request_uid[30], connected_store[129];
static int64_t lookup_deadline;
static uint32_t boot_id, sequence;
static bool wifi_started;
static int disconnect_reason;
typedef struct {
    char id[32];
    char uid[30];
    card_config_t config;
} card_job_t;
static QueueHandle_t card_jobs;

static void emit(const char *type, const char *id, const char *uid, const char *status,
                 const char *store_id)
{
    cJSON *json = cJSON_CreateObject();
    if (!json) return;
    cJSON_AddNumberToObject(json, "v", 1);
    cJSON_AddStringToObject(json, "type", type);
    cJSON_AddStringToObject(json, "requestId", id);
    cJSON_AddStringToObject(json, "uid", uid);
    if (status) cJSON_AddStringToObject(json, "status", status);
    if (store_id) cJSON_AddStringToObject(json, "storeId", store_id);
    char *encoded = cJSON_PrintUnformatted(json);
    if (encoded) {
        /* Never serialize SSID/password into an outbound log or status frame. */
        flockfile(stdout);
        printf("PBL5:%s\n", encoded);
        fflush(stdout);
        funlockfile(stdout);
        free(encoded);
    }
    cJSON_Delete(json);
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t event, void *data)
{
    (void)arg;
    if (base == WIFI_EVENT && event == WIFI_EVENT_STA_START) {
        xEventGroupSetBits(events, STARTED);
    } else if (base == WIFI_EVENT && event == WIFI_EVENT_STA_STOP) {
        xEventGroupClearBits(events, GOT_IP);
        xEventGroupSetBits(events, STOPPED);
    } else if (base == WIFI_EVENT && event == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *info = data;
        xSemaphoreTake(lock, portMAX_DELAY);
        disconnect_reason = info->reason;
        connected_store[0] = '\0';
        xSemaphoreGive(lock);
        xEventGroupClearBits(events, GOT_IP);
        /* No automatic reconnect: a failed attempt must finish and be reported. */
    } else if (base == IP_EVENT && event == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(events, GOT_IP);
    }
}

static bool stop_wifi(void)
{
    if (!wifi_started) return true;
    xEventGroupClearBits(events, STOPPED);
    if (esp_wifi_stop() != ESP_OK) return false;
    if (!(xEventGroupWaitBits(events, STOPPED, pdTRUE, pdTRUE,
                             pdMS_TO_TICKS(3000)) & STOPPED)) return false;
    wifi_started = false;
    return true;
}

static bool valid_text(const char *text, size_t minimum, size_t maximum)
{
    if (!text) return false;
    size_t length = strlen(text);
    if (length < minimum || length > maximum) return false;
    for (size_t i = 0; i < length; ++i)
        if ((unsigned char)text[i] < 32 || (unsigned char)text[i] == 127) return false;
    return true;
}

static const char *string_field(cJSON *json, const char *name)
{
    cJSON *field = cJSON_GetObjectItemCaseSensitive(json, name);
    return cJSON_IsString(field) ? field->valuestring : NULL;
}

static bool valid_password(const char *password)
{
    if (!password) return false;
    size_t length = strlen(password);
    if (length == 0) return true;  /* Explicit empty string means an open network. */
    if (!valid_text(password, 8, 64)) return false;
    if (length == 64) {
        for (size_t i = 0; i < length; ++i)
            if (!isxdigit((unsigned char)password[i])) return false;
    }
    return true;
}

static void complete(const char *id, const char *uid, const char *status, const char *store)
{
    emit("status", id, uid, status, store);
    xSemaphoreTake(lock, portMAX_DELAY);
    phase = IDLE;
    xSemaphoreGive(lock);
}

static void connect_store(const char *id, const char *uid, const char *store,
                          const char *ssid, const char *password)
{
    emit("status", id, uid, "CONFIG_RECEIVED", store);
    xSemaphoreTake(lock, portMAX_DELAY);
    connected_store[0] = '\0';
    disconnect_reason = 0;
    xSemaphoreGive(lock);
    if (!stop_wifi()) {
        complete(id, uid, "WIFI_STOP_FAILED", NULL);
        return;
    }
    wifi_config_t config = {0};
    memcpy(config.sta.ssid, ssid, strlen(ssid));
    memcpy(config.sta.password, password, strlen(password));
    config.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    config.sta.threshold.authmode = password[0] ? WIFI_AUTH_WPA_PSK : WIFI_AUTH_OPEN;
    esp_err_t result = esp_wifi_set_config(WIFI_IF_STA, &config);
    memset(&config, 0, sizeof(config));
    xEventGroupClearBits(events, GOT_IP | STARTED);
    if (result == ESP_OK) {
        result = esp_wifi_start();
        wifi_started = result == ESP_OK;
    }
    if (result == ESP_OK && !(xEventGroupWaitBits(events, STARTED, pdTRUE, pdTRUE,
                                                pdMS_TO_TICKS(3000)) & STARTED))
        result = ESP_ERR_TIMEOUT;
    if (result == ESP_OK) result = esp_wifi_connect();
    emit("status", id, uid, "WIFI_CONNECTING", store);
    bool ready = result == ESP_OK &&
        (xEventGroupWaitBits(events, GOT_IP, pdFALSE, pdTRUE,
                            pdMS_TO_TICKS(20000)) & GOT_IP);
    if (ready) {
        xSemaphoreTake(lock, portMAX_DELAY);
        /* Recheck after locking so a disconnect cannot publish a stale store. */
        ready = (xEventGroupGetBits(events) & GOT_IP) != 0;
        if (ready) snprintf(connected_store, sizeof(connected_store), "%s", store);
        xSemaphoreGive(lock);
    }
    if (!ready) {
        bool stopped = stop_wifi();
        xSemaphoreTake(lock, portMAX_DELAY);
        int reason = disconnect_reason;
        xSemaphoreGive(lock);
        const char *status = !stopped ? "WIFI_STOP_FAILED" :
            reason ? "WIFI_FAILED" : "WIFI_TIMEOUT";
        complete(id, uid, status, NULL);
        return;
    }
    complete(id, uid, "WIFI_CONNECTED", store);
}

static void __attribute__((unused)) process_line(char *line)
{
    if (strncmp(line, "PBL5:", 5) != 0) return;
    /* cJSON stores strings as C strings: reject escaped NUL to avoid truncation. */
    if (strstr(line, "\\u0000")) return;
    const char *end = NULL;
    cJSON *json = cJSON_ParseWithLengthOpts(line + 5, strlen(line + 5) + 1, &end, true);
    if (!json) return;  /* Truncated/invalid lines never trigger a connection. */
    cJSON *version = cJSON_GetObjectItemCaseSensitive(json, "v");
    const char *id = string_field(json, "requestId");
    const char *uid = string_field(json, "uid");
    const char *type = string_field(json, "type");
    xSemaphoreTake(lock, portMAX_DELAY);
    bool match = cJSON_IsNumber(version) && version->valuedouble == 1 && id && uid &&
        phase == WAIT_CONFIG && strcmp(id, request_id) == 0 && strcmp(uid, request_uid) == 0 &&
        esp_timer_get_time() < lookup_deadline;
    xSemaphoreGive(lock);
    if (!match || !type) goto cleanup;
    if (strcmp(type, "lookup_error") == 0) {
        complete(id, uid, "LOOKUP_FAILED", NULL);
        goto cleanup;
    }
    if (strcmp(type, "store_config") != 0) goto cleanup;
    const char *store = string_field(json, "storeId");
    const char *name = string_field(json, "storeName");
    const char *ssid = string_field(json, "wifiSSID");
    const char *password = string_field(json, "wifiPassword");
    if (!valid_text(store, 1, 128) || !valid_text(name, 1, 600) ||
        !valid_text(ssid, 1, 32) || !valid_password(password)) {
        complete(id, uid, "INVALID_CONFIG", NULL);
        goto cleanup;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    phase = CONNECTING;
    xSemaphoreGive(lock);
    connect_store(id, uid, store, ssid, password);
cleanup:
    {
        cJSON *secret = cJSON_GetObjectItemCaseSensitive(json, "wifiPassword");
        if (cJSON_IsString(secret)) memset(secret->valuestring, 0, strlen(secret->valuestring));
    }
    cJSON_Delete(json);
}

static void receive_task(void *arg)
{
    (void)arg;
#if CONFIG_PBL5_CARD_WIFI
    card_job_t job;
    while (true) {
        if (xQueueReceive(card_jobs, &job, portMAX_DELAY) == pdTRUE) {
            connect_store(job.id, job.uid, job.config.store_id, job.config.ssid, job.config.password);
            memset(&job, 0, sizeof(job));
        }
    }
#else
    char line[FRAME_LIMIT + 1];
    size_t used = 0;
    bool discard = false;
    while (true) {
        uint8_t byte;
        int received = uart_read_bytes(UART_NUM_0, &byte, 1, pdMS_TO_TICKS(100));
        if (received == 1) {
            if (byte == '\n') {
                if (!discard) {
                    line[used] = '\0';
                    process_line(line);
                }
                memset(line, 0, sizeof(line));
                used = 0;
                discard = false;
            } else if (byte == 0 || used >= FRAME_LIMIT) {
                discard = true;
            } else if (!discard) {
                line[used++] = (char)byte;
            }
        }
        char id[32], uid[30];
        xSemaphoreTake(lock, portMAX_DELAY);
        bool expired = phase == WAIT_CONFIG && esp_timer_get_time() >= lookup_deadline;
        snprintf(id, sizeof(id), "%s", request_id);
        snprintf(uid, sizeof(uid), "%s", request_uid);
        xSemaphoreGive(lock);
        if (expired) complete(id, uid, "LOOKUP_TIMEOUT", NULL);
    }
#endif
}

bool firebase_bridge_prepare_card(const char *uid)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    bool ready = phase == IDLE;
    if (ready) connected_store[0] = '\0';
    xSemaphoreGive(lock);
    if (!ready) emit("busy", "", uid, "BUSY_RESCAN_AFTER_RESULT", NULL);
    return ready;
}

bool firebase_bridge_card_config(const char *uid, const card_config_t *config)
{
    if (!card_jobs || !config) return false;
    card_job_t job = {0};
    xSemaphoreTake(lock, portMAX_DELAY);
    if (phase != IDLE) {
        xSemaphoreGive(lock);
        emit("busy", "", uid, "BUSY_RESCAN_AFTER_RESULT", NULL);
        return false;
    }
    snprintf(job.id, sizeof(job.id), "%08" PRIx32 "-%" PRIu32, boot_id, ++sequence);
    snprintf(job.uid, sizeof(job.uid), "%s", uid);
    job.config = *config;
    phase = CONNECTING;
    connected_store[0] = '\0';
    xSemaphoreGive(lock);
    bool queued = xQueueSend(card_jobs, &job, 0) == pdTRUE;
    if (!queued) complete(job.id, uid, "QUEUE_FAILED", NULL);
    memset(&job, 0, sizeof(job));
    return queued;
}

void firebase_bridge_scan(const char *uid)
{
    char id[32];
    xSemaphoreTake(lock, portMAX_DELAY);
    if (phase != IDLE) {
        xSemaphoreGive(lock);
        emit("busy", "", uid, "BUSY_RESCAN_AFTER_RESULT", NULL);
        return;
    }
    snprintf(request_id, sizeof(request_id), "%08" PRIx32 "-%" PRIu32, boot_id, ++sequence);
    snprintf(request_uid, sizeof(request_uid), "%s", uid);
    snprintf(id, sizeof(id), "%s", request_id);
    /* Selecting a different/unknown card must not leave the old store usable. */
    connected_store[0] = '\0';
    lookup_deadline = esp_timer_get_time() + LOOKUP_SECONDS * 1000000LL;
    phase = WAIT_CONFIG;
    xSemaphoreGive(lock);
    emit("scan", id, uid, NULL, NULL);
}

bool firebase_bridge_connected_store(char *destination, size_t size)
{
    if (!destination || size == 0) return false;
    xSemaphoreTake(lock, portMAX_DELAY);
    bool ready = connected_store[0] && (xEventGroupGetBits(events) & GOT_IP) &&
        strlen(connected_store) < size;
    snprintf(destination, size, "%s", ready ? connected_store : "");
    xSemaphoreGive(lock);
    return ready;
}

esp_err_t firebase_bridge_init(void)
{
    lock = xSemaphoreCreateMutex();
    events = xEventGroupCreate();
    if (!lock || !events) return ESP_ERR_NO_MEM;
    boot_id = esp_random();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    if (!esp_netif_create_default_wifi_sta()) return ESP_ERR_NO_MEM;
    wifi_init_config_t wifi = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wifi));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, NULL));
#if CONFIG_PBL5_FIREBASE_USB
    /* UART RX is only used by the old Python bridge, never in card-reader mode. */
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 4096, 0, 0, NULL, 0));
#else
    card_jobs = xQueueCreate(1, sizeof(card_job_t));
    if (!card_jobs) return ESP_ERR_NO_MEM;
#endif
    if (xTaskCreate(receive_task, "firebase_serial", 8192, NULL, 5, NULL) != pdPASS)
        return ESP_ERR_NO_MEM;
    emit("ready", "", "", "READY", NULL);
    return ESP_OK;
}
#endif
