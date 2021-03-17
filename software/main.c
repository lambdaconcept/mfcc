#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "ft601.h"

#define STEP_SIZE   170
#define NCEPTRUMS   32

int main()
{
    int i, j;
    int err;
    FILE *file;
    int16_t sample;
    uint32_t buffer[512];
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

    printf("mydata = [\n");

    for (j=0; j<1000; j++) {

        for (i=0; i<STEP_SIZE; i++) {
            fread(&sample, sizeof(sample), 1, file);
            buffer[i] = sample;
        }

        err = ft601_write(&ft601, buffer, sizeof(uint32_t) * STEP_SIZE);
        if (err) {
            printf("Error ft601_write %d\n", err);
            goto out;
        }

        err = ft601_read(&ft601, buffer, sizeof(uint32_t) * NCEPTRUMS);
        if (err) {
            printf("Error ft601_read %d\n", err);
            goto out;
        }

        // printf("FRAME %d\n", j);
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
