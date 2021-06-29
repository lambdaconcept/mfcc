#ifndef __CEPSTRUM_H
#define __CEPSTRUM_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C"
{
#endif

struct circular_s
{
    int16_t *array;
    int16_t *head;
    size_t size;
    size_t count;
};

int cepstrum_get_column(int fd, int16_t *buf, int ncepstrums);
int cepstrum_get_window(int fd, int16_t *buf, int ncepstrums, int nframes);
int cepstrum_refill_window(int fd, struct circular_s *circ,
                           int ncepstrums, int nframes,
                           void (*callback)(int16_t*, int));
bool cepstrum_eval_power(const struct circular_s *circ, int ncepstrums);

#ifdef __cplusplus
}
#endif

#endif /* __CEPSTRUM_H */
