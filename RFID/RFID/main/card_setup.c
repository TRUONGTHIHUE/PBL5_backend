#include "card_setup.h"
#include "sdkconfig.h"

#if CONFIG_PBL5_CARD_WRITER
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cJSON.h"
#include "card_storage.h"
#include "driver/uart.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#if !CONFIG_ESP_CONSOLE_UART_DEFAULT || CONFIG_ESP_CONSOLE_UART_NUM != 0
#error "Provisioning requires the default UART0 USB-UART console"
#endif

static SemaphoreHandle_t writer_lock;
static bool armed, writing;
static bool allow_replace;
static int64_t deadline;
static char target_uid[30], request_id[33];
static uint8_t pending[CARD_RECORD_SIZE];

static void notify(const char *id, const char *status, const char *uid)
{
    cJSON *json = cJSON_CreateObject();
    if (!json) return;
    cJSON_AddNumberToObject(json, "v", 1);
    cJSON_AddStringToObject(json, "type", "provision_status");
    cJSON_AddStringToObject(json, "requestId", id);
    cJSON_AddStringToObject(json, "status", status);
    if (uid) cJSON_AddStringToObject(json, "uid", uid);
    char *encoded = cJSON_PrintUnformatted(json);
    if (encoded) {
        flockfile(stdout);
        printf("PBL5CARD:%s\n", encoded);
        fflush(stdout);
        funlockfile(stdout);
        free(encoded);
    }
    cJSON_Delete(json);
}

static const char *field(cJSON *json, const char *name)
{
    cJSON *value = cJSON_GetObjectItemCaseSensitive(json, name);
    return cJSON_IsString(value) ? value->valuestring : NULL;
}

static int hex(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static void prepare(char *line)
{
    if (strncmp(line, "PBL5CARD:", 9) || strstr(line, "\\u0000")) return;
    cJSON *json = cJSON_ParseWithLengthOpts(line + 9, strlen(line + 9) + 1, NULL, true);
    if (!json) return;
    const char *id = field(json, "requestId"), *uid = field(json, "uid");
    const char *payload = field(json, "recordHex"), *type = field(json, "type");
    cJSON *version = cJSON_GetObjectItemCaseSensitive(json, "v");
    cJSON *replace = cJSON_GetObjectItemCaseSensitive(json, "replace");
    uint8_t record[CARD_RECORD_SIZE] = {0};
    card_config_t config = {0};
    size_t uid_length = uid ? strlen(uid) : 0;
    bool valid = id && strlen(id) == 32 && uid &&
        (uid_length == 11 || uid_length == 20 || uid_length == 29) &&
        type && strcmp(type, "prepare") == 0 && cJSON_IsNumber(version) &&
        version->valuedouble == 1 && cJSON_IsBool(replace) &&
        payload && strlen(payload) == CARD_RECORD_SIZE * 2;
    if (valid) {
        for (unsigned i = 0; i < 32; ++i) if (hex(id[i]) < 0) valid = false;
        for (unsigned i = 0; i < uid_length; ++i) {
            if (i % 3 == 2) { if (uid[i] != ' ') valid = false; }
            else if (hex(uid[i]) < 0 || (uid[i] >= 'a' && uid[i] <= 'f')) valid = false;
        }
        for (unsigned i = 0; i < CARD_RECORD_SIZE; ++i) {
            int a = hex(payload[i * 2]), b = hex(payload[i * 2 + 1]);
            if (a < 0 || b < 0) { valid = false; break; }
            record[i] = (a << 4) | b;
        }
        valid = valid && card_record_decode(record, &config);
    }
    if (valid) {
        xSemaphoreTake(writer_lock, portMAX_DELAY);
        if (armed || writing) {
            xSemaphoreGive(writer_lock);
            notify(id, "BUSY", uid);
        } else {
            memcpy(pending, record, sizeof(pending));
            snprintf(target_uid, sizeof(target_uid), "%s", uid);
            snprintf(request_id, sizeof(request_id), "%s", id);
            allow_replace = cJSON_IsTrue(replace);
            deadline = esp_timer_get_time() + 90000000LL;
            armed = true;
            xSemaphoreGive(writer_lock);
            notify(id, "ARMED", uid);
        }
    } else {
        notify("", "INVALID_REQUEST", NULL);
    }
    memset(record, 0, sizeof(record));
    memset(&config, 0, sizeof(config));
    cJSON *secret = cJSON_GetObjectItemCaseSensitive(json, "recordHex");
    if (cJSON_IsString(secret)) memset(secret->valuestring, 0, strlen(secret->valuestring));
    cJSON_Delete(json);
}

static void receiver(void *arg)
{
    (void)arg;
    char line[1025];
    size_t used = 0;
    bool discard = false;
    while (true) {
        uint8_t byte;
        if (uart_read_bytes(UART_NUM_0, &byte, 1, pdMS_TO_TICKS(100)) == 1) {
            if (byte == '\n') {
                if (!discard) { line[used] = '\0'; prepare(line); }
                memset(line, 0, sizeof(line)); used = 0; discard = false;
            } else if (byte == 0 || used >= 1024) discard = true;
            else if (!discard) line[used++] = byte;
        }
        char id[33] = {0};
        xSemaphoreTake(writer_lock, portMAX_DELAY);
        bool expired = armed && esp_timer_get_time() >= deadline;
        if (expired) {
            snprintf(id, sizeof(id), "%s", request_id);
            armed = false;
            memset(pending, 0, sizeof(pending));
        }
        xSemaphoreGive(writer_lock);
        if (expired) notify(id, "EXPIRED", NULL);
    }
}

void card_setup_scan(rc522_handle_t scanner, rc522_picc_t *picc, const char *uid)
{
    uint8_t record[CARD_RECORD_SIZE] = {0}, previous[CARD_RECORD_SIZE] = {0};
    char id[33] = {0};
    bool replace;
    xSemaphoreTake(writer_lock, portMAX_DELAY);
    if (!armed || writing || esp_timer_get_time() >= deadline) {
        xSemaphoreGive(writer_lock);
        notify("", "NOT_ARMED", uid);
        return;
    }
    snprintf(id, sizeof(id), "%s", request_id);
    if (strcmp(uid, target_uid)) {
        xSemaphoreGive(writer_lock);
        notify(id, "TARGET_MISMATCH", uid);
        return;
    }
    writing = true; armed = false;
    memcpy(record, pending, sizeof(record));
    memset(pending, 0, sizeof(pending));
    replace = allow_replace;
    xSemaphoreGive(writer_lock);
    const char *status = "READ_OR_AUTH_FAILED";
    esp_err_t result = card_storage_read(scanner, picc, previous);
    card_config_t existing = {0};
    if (result == ESP_ERR_NOT_SUPPORTED) status = "UNSUPPORTED_CARD";
    else if (result == ESP_OK) {
        bool blank = card_record_is_blank(previous);
        bool ours = card_record_decode(previous, &existing);
        if (!blank && !ours) status = "UNRECOGNIZED_DATA_NO_WRITE";
        else if (ours && !replace) status = "ALREADY_PROVISIONED_USE_REPLACE";
        else {
            result = card_storage_write(scanner, picc, record);
            status = result == ESP_OK ? "WRITE_VERIFIED" : "WRITE_FAILED_REMOVE_AND_RECHECK";
        }
    }
    esp_err_t finish = card_storage_finish(scanner, picc);
    if (finish != ESP_OK && strcmp(status, "WRITE_VERIFIED") == 0)
        status = "WRITE_FAILED_REMOVE_AND_RECHECK";
    memset(record, 0, sizeof(record));
    memset(previous, 0, sizeof(previous));
    memset(&existing, 0, sizeof(existing));
    notify(id, status, uid);
    xSemaphoreTake(writer_lock, portMAX_DELAY);
    writing = false;
    xSemaphoreGive(writer_lock);
}

esp_err_t card_setup_init(void)
{
    writer_lock = xSemaphoreCreateMutex();
    if (!writer_lock) return ESP_ERR_NO_MEM;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 4096, 0, 0, NULL, 0));
    if (xTaskCreate(receiver, "card_provision", 6144, NULL, 5, NULL) != pdPASS)
        return ESP_ERR_NO_MEM;
    notify("", "WRITER_READY", NULL);
    return ESP_OK;
}
#endif
