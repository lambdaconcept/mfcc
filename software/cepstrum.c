#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <poll.h>
#include <sys/ioctl.h>

#include "serial.h"
#include "cepstrum.h"

#define POWER_THRESHOLD 100000000

int cepstrum_get_column(int fd, int16_t *buf, int ncepstrums)
{
    int i;
    int n;
    int remain;
    uint8_t *p;
    int size;

    size = ncepstrums * sizeof(int16_t);
    p = (uint8_t *)buf;
    remain = size;

    /* Align on the next magic */

    expect_magic(fd);

    while (remain > 0) {
        n = read(fd, p, remain);
        if (n <= 0) {
            printf("read failed\n");
            return -1;
        }

        p += n;
        remain -= n;

        // printf("recv %d, remain %d\n", n, remain);
    }

#ifdef MFCC_DEBUG
    printf("Column received (%d)\n", size);

    p = (uint8_t *)buf;
    for (i=0; i<size; i++) {
        printf("%02x ", p[i]);
    }
    printf("\n");
#endif

    /* Endian conversion... */

    for (i=0; i<ncepstrums; i++) {
        buf[i] = ntohs(buf[i]);
    }

#ifdef MFCC_DEBUG
    for (i=0; i<ncepstrums; i++) {
        printf("%04x ", buf[i] & 0xffff);
    }
    printf("\n");
#endif

    return 0;
}

int cepstrum_get_window(int fd, int16_t *buf, int ncepstrums, int nframes)
{
    int ret;
    int remain;
    int16_t *p;

    p = buf;
    remain = nframes;

    while (remain > 0) {
        ret = cepstrum_get_column(fd, p, ncepstrums);
        if (ret < 0) {
            return ret;
        }

        p += ncepstrums;
        remain--;
    }

    printf("Window received (%d x %d)\n", ncepstrums, nframes);
    return 0;
}

int cepstrum_refill_window(int fd, struct circular_s *circ,
                           int ncepstrums, int nframes,
                           void (*callback)(int16_t*, int))
{
    int ret;
    int size;
    int avail;
    int newsets = 0;
    struct pollfd fds[1];

    /* Prepare the File Descriptor for poll */

    memset(fds, 0, sizeof(struct pollfd));
    fds[0].fd      = fd;
    fds[0].events  = POLLIN;

    ret = poll(fds, 1, 10);
    if (ret < 0) {
        printf("ERROR: poll failed: %d\n", errno);
        return ret;

    } else if (fds[0].revents & POLLIN) {

        /* Check how many cepstrums columns we have available */

        ret = ioctl(fd, FIONREAD, (unsigned long)&avail);
        if (ret < 0) {
            printf("ERROR: ioctl failed: %d\n", errno);
        }
        size = (ncepstrums + 1) * sizeof(int16_t); // with magic header
        avail /= size;

        /* Discard the old data */

        if (circ->count > 0) {
            circ->count -= ncepstrums * avail;
        }

        /* Fill the circular buffer */

        while (circ->count < circ->size) {

            ret = cepstrum_get_column(fd, circ->head, ncepstrums);
            if (ret < 0) {
                return ret;
            }
            if (callback) {
                callback(circ->head, ncepstrums);
            }
            newsets++;

            circ->head += ncepstrums;
            if (circ->head >= (circ->array + circ->size)) {
                circ->head = circ->array; // this works as long as size is multiple of cepstrums
            }

            circ->count += ncepstrums;
            if (circ->count >= circ->size) { // should not happen
                circ->count = circ->size;
            }
        }
    }

    // printf("Exit: array %p, head %p, count %d, new: %d\n",
    //        circ->array, circ->head, circ->count, newsets);
    return newsets;
}

bool cepstrum_eval_power(const struct circular_s *circ, int ncepstrums)
{
    int i;
    int16_t *p;
    int power = 0;
    const int first = 1 * circ->size / 3;
    const int last  = 2 * circ->size / 3;

    /* Sum the first cepstrum coeff over the central part of the time frame */

    for (i=first; i<last; i+=ncepstrums) {

        p = circ->head + i;
        if (p >= circ->array + circ->size) {
            p -= circ->size;
        }

        power += (*p) * (*p);
    }

    // printf("Total power: %d\n", power);
    return (power >= POWER_THRESHOLD);
}
