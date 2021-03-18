#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "ft601.h"

#define NFFT        512
#define STEPSIZE    170
#define NCEPTRUMS   32

int main()
{
    int i, j;
    int err;
    int amount;
    FILE *file;
    int16_t sample;
    uint32_t buffer[NFFT];
    struct ft601_context ft601;

    file = fopen("../f2bjrop1.0.raw", "rb");
    if (!file) {
        printf("Cant open\n");
    }

    memset(&ft601, 0, sizeof(struct ft601_context));
    err = ft601_open(&ft601);
    if (err) {
        printf("Error ft601_open %d\n", err);
        goto out;
    }

    /* Send a software reset */

    buffer[0] = 0x80000000;
    err = ft601_write(&ft601, buffer, sizeof(uint32_t));
    if (err) {
        printf("Error ft601_write %d\n", err);
        goto out;
    }

    printf("mydata = [\n");

    for (j=0; j<1000; j++) {

        /* On the first round, we need to send the entire FFT size to
         * produce the first ceptrum set. On the next rounds, we send only
         * the amount for the step size */

        amount = (j == 0) ? NFFT : STEPSIZE;

        memset(buffer, 0, sizeof(uint32_t) * amount);

        for (i=0; i<amount; i++) {
            fread(&sample, sizeof(sample), 1, file);
            buffer[i] = sample & 0xffff;
        }

        err = ft601_write(&ft601, buffer, sizeof(uint32_t) * amount);
        if (err) {
            printf("Error ft601_write %d\n", err);
            goto out;
        }

        err = ft601_read(&ft601, buffer, sizeof(uint32_t) * NCEPTRUMS);
        if (err) {
            printf("Error ft601_read %d\n", err);
            goto out;
        }

        printf("[");
        for (i=0; i<NCEPTRUMS; i++) {
            printf("%d, ", (int)buffer[i]);
        }
        printf("],\n");
    }

    printf("]\n");

    // ft601_close(&ft601);

out:
    fclose(file);

    return 0;
}
