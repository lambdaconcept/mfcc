#include "ft601.h"

#include <libusb-1.0/libusb.h>
#include <stdarg.h>
#include <stdlib.h>

struct ft601_ctrl_req {
    unsigned int idx;
    unsigned char pipe;
    unsigned char cmd;
    unsigned char unk1;
    unsigned char unk2;
    unsigned int len;
    unsigned int unk4;
    unsigned int unk5;
} __attribute__ ((packed));

static inline int ft601_error(struct ft601_context *ctx, char *format, ...)
{
    int rc = 0;
    if (ctx->log_cb) {
        va_list ap;
        va_start(ap, format);
        rc = ctx->log_cb(ctx, FT601_LOG_LEVEL_ERROR, format, ap);
        va_end(ap);
    }
    return rc;
}

static inline int ft601_info(struct ft601_context *ctx, char *format, ...)
{
    int rc = 0;
    if (ctx->log_cb) {
        va_list ap;
        va_start(ap, format);
        rc = ctx->log_cb(ctx, FT601_LOG_LEVEL_INFO, format, ap);
        va_end(ap);
    }
    return rc;
}

static inline int ft601_debug(struct ft601_context *ctx, char *format, ...)
{
    int rc = 0;
    if (ctx->log_cb) {
        va_list ap;
        va_start(ap, format);
        rc = ctx->log_cb(ctx, FT601_LOG_LEVEL_DEBUG, format, ap);
        va_end(ap);
    }
    return rc;
}

static libusb_device *__ft601_find_device(struct ft601_context *ctx)
{
    libusb_device **device_list;
    libusb_device *device = NULL;

    ssize_t device_count = libusb_get_device_list(ctx->usb_ctx, &device_list);
    if (device_count < 0) {
        ft601_error(ctx, "libusb_get_device_list: %s\n", libusb_strerror(device_count));
        goto err_exit;
    }

    int found = 0;
    struct libusb_device_descriptor desc;
    for (ssize_t i = 0; i < device_count; i++) {
        device = device_list[i];

        int err = libusb_get_device_descriptor(device, &desc);
        if (err) {
            ft601_error(ctx, "libusb_get_device_descriptor: %s\n", libusb_strerror(err));
            goto err_exit;
        }

        if ((desc.idVendor == FT601_ID_VENDOR) && (desc.idProduct == FT601_ID_PRODUCT)) {
            ft601_info(ctx, "Using FT601 device %04x:%04x (bus %d, device %d)\n",
                desc.idVendor, desc.idProduct,
                libusb_get_bus_number(device),
                libusb_get_device_address(device)
            );
            found = 1;
            break;
        }
    }

    if (!found) {
        ft601_error(ctx, "No FT601 device was found\n");
        goto err_exit;
    }

    libusb_free_device_list(device_list, 1);
    return device;

err_exit:
    libusb_free_device_list(device_list, 1);
    return NULL;
}

int ft601_open(struct ft601_context *ctx)
{
    int err;

    if (!ctx) {
        return FT601_ERROR_INVALID_PARAM;
    }

    err = libusb_init(&ctx->usb_ctx);
    if (err) {
        ft601_error(ctx, "libusb_init: %s\n", libusb_strerror(err));
        goto err_exit;
    }

    libusb_device *device = __ft601_find_device(ctx);
    if (!device) {
        err = FT601_ERROR_NOT_FOUND;
        goto err_free_usb_ctx;
    }

    err = libusb_open(device, &ctx->usb_dev);
    if (err) {
        ft601_error(ctx, "libusb_open: %s\n", libusb_strerror(err));
        goto err_free_usb_ctx;
    }

    err = libusb_reset_device(ctx->usb_dev);
    if (err) {
        ft601_error(ctx, "libusb_reset_device: %s\n", libusb_strerror(err));
        goto err_free_usb_ctx;
    }

    err = libusb_kernel_driver_active(ctx->usb_dev, FT601_IFACE_CTRL);
    if (err < 0) {
        ft601_error(ctx, "libusb_kernel_driver_active (interface %d): %s\n",
                    FT601_IFACE_CTRL, libusb_strerror(err));
        goto err_free_usb_ctx;
    }
    if (err == 1) {
        ft601_error(ctx, "libusb_kernel_driver_active (interface %d): already active\n",
                    FT601_IFACE_CTRL);
        goto err_free_usb_ctx;
    }

    err = libusb_claim_interface(ctx->usb_dev, FT601_IFACE_CTRL);
    if (err) {
        ft601_error(ctx, "libusb_claim_interface (interface %d): %s\n", FT601_IFACE_CTRL,
                    libusb_strerror(err));
        goto err_free_usb_ctx;
    }

    err = libusb_claim_interface(ctx->usb_dev, FT601_IFACE_DATA);
    if (err) {
        ft601_error(ctx, "libusb_claim_interface (interface %d): %s\n", FT601_IFACE_DATA,
                    libusb_strerror(err));
        goto err_free_usb_ctx;
    }

    return FT601_SUCCESS;

err_free_usb_ctx:
    ft601_close(ctx);
err_exit:
    return err;
}

void ft601_close(struct ft601_context *ctx)
{
    if (ctx) {
        if (ctx->usb_ctx) {
            libusb_exit(ctx->usb_ctx);
            ctx->usb_ctx = NULL;
        }
        if (ctx->usb_dev) {
            libusb_close(ctx->usb_dev);
            ctx->usb_dev = NULL;
        }
    }
}

static int __ft601_send_cmd_read(struct ft601_context *ctx, int size)
{
    int err;
    int transferred = 0;
    struct ft601_ctrl_req ctrl_req = {
        .idx  = ctx->ctrl_req_idx,
        .pipe = FT601_EP_DATA_IN,
        .cmd  = 1,
        .len  = size
    };

    err = libusb_bulk_transfer(ctx->usb_dev, FT601_EP_CTRL_OUT, (void *)&ctrl_req, sizeof(struct ft601_ctrl_req),
                               &transferred, /*timeout=*/1000);
    if (err < 0) {
        ft601_error(ctx, "libusb_bulk_transfer (endpoint %02x): %s\n", FT601_EP_CTRL_OUT,
                    libusb_strerror(err));
    } else {
        ctx->ctrl_req_idx++;
    }
    // TODO: handle transferred != sizeof(struct ft601_ctrl_req)
    return err;
}

int ft601_read(struct ft601_context *ctx, void *data, int size)
{
    int err;
    int transferred = 0;
    unsigned char *uc_data = data;

    while (size != 0) {
        err = __ft601_send_cmd_read(ctx, size);
        if (err) {
            return err;
        }

        err = libusb_bulk_transfer(ctx->usb_dev, FT601_EP_DATA_IN, uc_data, size, &transferred, /*timeout=*/0);
        if (err < 0) {
            ft601_error(ctx, "libusb_bulk_transfer (endpoint %02x): %s\n", FT601_EP_DATA_IN,
                        libusb_strerror(err));
            return err;
        }
        size    -= transferred;
        uc_data += transferred;
    }

    return FT601_SUCCESS;
}

int ft601_write(struct ft601_context *ctx, void *data, int size)
{
    int err;
    int transferred = 0;
    unsigned char *uc_data = data;

    while (size != 0) {
        err = libusb_bulk_transfer(ctx->usb_dev, FT601_EP_DATA_OUT, uc_data, size, &transferred, /*timeout=*/0);
        if (err < 0) {
            ft601_error(ctx, "libusb_bulk_transfer (endpoint %02x): %s\n", FT601_EP_DATA_OUT,
                        libusb_strerror(err));
            return err;
        }
        size    -= transferred;
        uc_data += transferred;
    }

    return FT601_SUCCESS;
}
