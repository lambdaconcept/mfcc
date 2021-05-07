#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <termios.h>

#include "libcolormap/tinycolormap.hpp"
#include "serial.h"
#include "cepstrum.h"

#include "SDL2/SDL.h"

#define NCEPSTRUMS 32
#define NFRAMES 93

int load_pixels(int fd, uint8_t *output, int width, int height) // output should be 3*size
{
    int i;
    int size;
    int16_t val;
    int16_t *input;
    uint8_t *src, *dst;
    uint32_t scale;
    int mymax = -32768;
    int mymin = 32767;
    double x;

    size = width * sizeof(int16_t);
    input = (int16_t *)malloc(size);
    memset(input, 0, size);

    cepstrum_get_column(fd, input, width);

    // shift buf
    src = output + (width * 3);
    dst = output;
    memmove(dst, src, (height-1) * width * 3);
    dst = output + (height-1) * width * 3;

    // there is no grayscale... use rgb...
    for (i=0; i<width; i++) {
        val = input[i];
        if (val > mymax) {
            mymax = val;
        }
        if (val < mymin) {
            mymin = val;
        }

        // attempt to rescale
        scale = (((int)val) + 3000); // try to augment contrast
        scale *= 4;
        // scale = ((int)val + 32768) >> 8; // try to augment contrast

        x = (double)scale / 65535.0;
        const tinycolormap::Color color = tinycolormap::GetColor(x, tinycolormap::ColormapType::Inferno);
        // printf("scale %d, x: %f, color.b %f\n", scale, x, color.b());

        dst[3*i] = color.r() * 255;
        dst[3*i+1] = color.g() * 255;
        dst[3*i+2] = color.b() * 255;

        // dst[3*i] = scale; // red
        // dst[3*i+1] = scale; // green
        // dst[3*i+2] = scale; // blue
    }

    // printf("min %d, max %d\n", mymin, mymax);
    free(input);

    return 0;
}

int main(int argc, char *argv[])
{
    SDL_Window *window;
    SDL_Renderer *renderer;
    SDL_Texture *texture;
    SDL_Event event;
    SDL_Surface *surface;

    int ret;
    int fd;
    int width, height;
    int size;
    uint8_t *pixels;

    fd = open("/dev/ttyUSB1", O_RDWR | O_NOCTTY | O_SYNC);
    if (fd < 0) {
        fprintf(stderr, "ERROR: open failed: %d\n", errno);
        return -1;
    }

    set_interface_attribs (fd, B1000000, 0);
    set_blocking (fd, 0);

    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Couldn't initialize SDL: %s", SDL_GetError());
        return -1;
    }

    width = NCEPSTRUMS;
    height = 5* NFRAMES;

    window = SDL_CreateWindow("MFCC",
            SDL_WINDOWPOS_UNDEFINED,
            SDL_WINDOWPOS_UNDEFINED,
            3* width * 5, 3* height,
            SDL_WINDOW_RESIZABLE);

    renderer = SDL_CreateRenderer(window, -1, 0);

    // there is no grayscale... use rgb...
    texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGB24, SDL_TEXTUREACCESS_TARGET, width, height);
    if (!texture){
        printf("Cant create texture\n");
        return -1;
    }

    size = width * height;
    pixels = (uint8_t*)malloc(3*size); // there is no grayscale... use rgb...
    memset(pixels, 0, 3*size);

    while (1) {
        SDL_PollEvent(&event);
        if(event.type == SDL_QUIT)
            break;

        SDL_RenderClear(renderer);

        /* get image */

        ret = load_pixels(fd, pixels, width, height);
        if (ret != 0)
        {
            printf("cant load pixels\n");
            goto end;
        }
        if (SDL_UpdateTexture(texture, NULL, pixels, 3*width) < 0)
        {
            printf("SDL_UpdateTexture failed: %s\n", SDL_GetError());
        }

        SDL_SetRenderTarget(renderer, texture);

        /* show */

        SDL_SetRenderTarget(renderer, NULL);
        SDL_RenderCopy(renderer, texture, NULL, NULL);
        SDL_RenderPresent(renderer);
    }

end:
    printf("exit\n");
    free(pixels);

    SDL_DestroyRenderer(renderer);
    SDL_Quit();

    close(fd);

    return 0;
}
