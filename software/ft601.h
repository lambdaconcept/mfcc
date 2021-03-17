#ifndef __FT601_H
#define __FT601_H

#ifdef __cplusplus
extern "C" {
#endif

#include <libusb-1.0/libusb.h>
#include <stdarg.h>

#define FT601_ID_VENDOR  0x0403
#define FT601_ID_PRODUCT 0x601f

enum ft601_interface {
    FT601_IFACE_CTRL = 0,
    FT601_IFACE_DATA = 1,
};

enum ft601_endpoint {
    FT601_EP_CTRL_OUT = 0x01,
    FT601_EP_DATA_IN = 0x82,
    FT601_EP_DATA_OUT = 0x02,
};

enum ft601_error {
    FT601_SUCCESS = 0,
    FT601_ERROR_INVALID_PARAM = -101,
    FT601_ERROR_NOT_FOUND = -102,
    FT601_ERROR_NO_MEM = -103,
    FT601_ERROR_BUSY = -104,
    FT601_ERROR_OTHER = -200,
};

enum ft601_log_level {
    FT601_LOG_LEVEL_NONE = 0,
    FT601_LOG_LEVEL_ERROR = 1,
    FT601_LOG_LEVEL_INFO = 2,
    FT601_LOG_LEVEL_DEBUG = 3,
};

struct ft601_context;

typedef int (*ft601_log_cb)(struct ft601_context *ctx, enum ft601_log_level level,
                            char *format, va_list ap);

struct ft601_context {
    libusb_context *usb_ctx;
    libusb_device_handle *usb_dev;
    unsigned int ctrl_req_idx;
    ft601_log_cb log_cb;
};

int ft601_open(struct ft601_context *ctx);
void ft601_close(struct ft601_context *ctx);
int ft601_read(struct ft601_context *ctx, void *data, int size);
int ft601_write(struct ft601_context *ctx, void *data, int size);

#ifdef __cplusplus
}
#endif

#endif // !__FT601_H
