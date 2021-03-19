#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>

#include "ft601.h"
#include "wav.h"

#define NFFT        512
#define STEPSIZE    170
#define NCEPSTRUMS  32
#define SAMPLERATE  16000

struct mfcc_s
{
    struct ft601_context ft601;
};

int mfcc_softreset(struct mfcc_s *sess)
{
    int ret;
    uint32_t val;

    val = 0x80000000;
    ret = ft601_write(&sess->ft601, &val, sizeof(uint32_t));
    if (ret) {
        printf("Error ft601_write %d\n", ret);
        return ret;
    }

    return 0;
}

int mfcc_open(struct mfcc_s *sess)
{
    int ret;

    memset(&sess->ft601, 0, sizeof(struct ft601_context));

    ret = ft601_open(&sess->ft601);
    if (ret) {
        printf("Error ft601_open %d\n", ret);
        return ret;
    }

    mfcc_softreset(sess);

    return 0;
}

void mfcc_close(struct mfcc_s *sess)
{
    // ft601_close(&ft601);
}

WavFile *mfcc_wav_open(const char *path)
{
    WavFile *in;
    WavU16 format;
    WavU32 samplerate;
    size_t samplesize;
    size_t nsamples;
    size_t nframes;

    in = wav_open(path, "rb");
    if (!in) {
        printf("Failed to open: %s\n", path);
        return NULL;
    }

    format = wav_get_format(in);
    if (format != WAV_FORMAT_PCM) {
        printf("Unexpected format: %04x\n", format);
        wav_close(in);
        return NULL;
    };

    samplesize = wav_get_sample_size(in);
    if (samplesize != sizeof(int16_t)) {
        printf("Unexpected samplesize: %d\n", samplesize);
        wav_close(in);
        return NULL;
    };

    samplerate = wav_get_sample_rate(in);
    if (samplerate != SAMPLERATE) {
        printf("Unexpected samplerate: %d\n", samplerate);
        wav_close(in);
        return NULL;
    }

    nsamples = wav_get_length(in);
    nframes = ((nsamples - NFFT) / STEPSIZE) + 1 /* padding */ + 1;

    return in;
}

int mfcc_convert(struct mfcc_s *sess, const char *path_in, const char *path_out)
{
    int i;
    int ret;
    bool eof;
    int index;
    int amount;
    int16_t sample;
    int16_t cepstrum;
    uint32_t buffer[NFFT];
    FILE *out = NULL;
    WavFile *in = NULL;

    mfcc_softreset(sess);

    in = mfcc_wav_open(path_in);
    if (!in) {
        return -1;
    }

    out = fopen(path_out, "wb");
    if (!out) {
        printf("Failed to open %s: %s\n", path_out, strerror(errno));
        return -1;
    }

    index = 0;
    eof = false;
    while (!eof) {

        /* On the first round, we need to send the entire FFT size to
         * produce the first cepstrum set. On the next rounds, we send only
         * the amount for the step size */

        amount = (index++ == 0) ? NFFT : STEPSIZE;
        memset(buffer, 0, sizeof(uint32_t) * amount);

        for (i=0; i<amount; i++) {
            ret = wav_read(in, &sample, 1);
            if (ret == 1) {
                buffer[i] = (sample & 0xffff);
            } else {
                eof = true;
            }
        }

        /* Send the audio samples */

        ret = ft601_write(&sess->ft601, buffer, sizeof(uint32_t) * amount);
        if (ret) {
            printf("Error ft601_write %d\n", ret);
            goto out;
        }

        /* Get the corresponding cepstrums */

        ret = ft601_read(&sess->ft601, buffer, sizeof(uint32_t) * NCEPSTRUMS);
        if (ret) {
            printf("Error ft601_read %d\n", ret);
            goto out;
        }

        for (i=0; i<NCEPSTRUMS; i++) {
            cepstrum = (int16_t)buffer[i];
            fwrite(&cepstrum, sizeof(cepstrum), 1, out);
        }
    }

out:
    if (out) {
        fclose(out);
    }
    if (in) {
        wav_close(in);
    }

    return 0;
}

/*
int main(int argc, char *argv[])
{
    int ret;
    struct mfcc_s sess;

    if (argc < 3) {
        printf("Usage: %s <audio.wav> <cepstrum.raw>\n", argv[0]);
        return 1;
    }

    ret = mfcc_open(&sess);
    if (ret) {
        return ret;
    }

    ret = mfcc_convert(&sess, argv[1], argv[2]);
    if (ret) {
        return ret;
    }

    mfcc_close(&sess);

    return 0;
}
*/

void show_dir_content(struct mfcc_s *sess, char * path)
{
    int ret;
    DIR * d = opendir(path);
    if(d==NULL) return;
    struct dirent * dir;
    char *d_path = malloc(512);
    char *d_out = malloc(512);
    char *p;

    while ((dir = readdir(d)) != NULL)
    {
        if(dir-> d_type != DT_DIR){
            p = dir->d_name + strlen(dir->d_name)-4;
            if(!strncmp(p, ".wav", 4)){

                snprintf(d_path, 512, "%s/%s", path, dir->d_name);
                memset(d_out, 0, 512);

                strncpy(d_out, d_path, strlen(d_path) - 3);
                strcat(d_out, "mfcc");

                printf("%s %s \n", d_path, d_out);
                ret = mfcc_convert(sess, d_path, d_out);
                if (ret) {
                    printf("failed\n");
                    return;
                }

            }
        }
        else
            if(dir -> d_type == DT_DIR && strcmp(dir->d_name,".")!=0 && strcmp(dir->d_name,"..")!=0 )
            {
                snprintf(d_path, 512, "%s/%s", path, dir->d_name);
                show_dir_content(sess, d_path);
            }
    }
    free(d_path);
    free(d_out);
    closedir(d);
}

int main(int argc, char *argv[])
{
    int ret;
    struct mfcc_s sess;

    if (argc != 2) {
        printf("Usage: %s <wavdir>\n", argv[0]);
        return 1;
    }

    ret = mfcc_open(&sess);
    if (ret) {
        return ret;
    }

    /*
    uint32_t drop;
    for (int i=0; i<NCEPSTRUMS; i++) {
        ft601_read(&sess.ft601, &drop, sizeof(uint32_t));
        printf("flushed %d\n", i);
    }
    */

    show_dir_content(&sess, argv[1]);

    mfcc_close(&sess);

    return 0;
}
