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

#include "SDL2/SDL.h"

#define NCEPSTRUMS 32
#define NFRAMES 93

#define MAGIC_H 0xa5
#define MAGIC_L 0x5a

int
set_interface_attribs (int fd, int speed, int parity)
{
        struct termios tty;
        if (tcgetattr (fd, &tty) != 0)
        {
                printf ("error %d from tcgetattr", errno);
                return -1;
        }

        cfsetospeed (&tty, speed);
        cfsetispeed (&tty, speed);

        tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;     // 8-bit chars
        // disable IGNBRK for mismatched speed tests; otherwise receive break
        // as \000 chars
        tty.c_iflag &= ~IGNBRK;         // disable break processing
        tty.c_lflag = 0;                // no signaling chars, no echo,
                                        // no canonical processing
        tty.c_oflag = 0;                // no remapping, no delays
        tty.c_cc[VMIN]  = 0;            // read doesn't block
        tty.c_cc[VTIME] = 5;            // 0.5 seconds read timeout

        tty.c_iflag &= ~(IXON | IXOFF | IXANY); // shut off xon/xoff ctrl

        tty.c_cflag |= (CLOCAL | CREAD);// ignore modem controls,
                                        // enable reading
        tty.c_cflag &= ~(PARENB | PARODD);      // shut off parity
        tty.c_cflag |= parity;
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CRTSCTS;

        if (tcsetattr (fd, TCSANOW, &tty) != 0)
        {
                printf ("error %d from tcsetattr", errno);
                return -1;
        }
        return 0;
}

void
set_blocking (int fd, int should_block)
{
        struct termios tty;
        memset (&tty, 0, sizeof tty);
        if (tcgetattr (fd, &tty) != 0)
        {
                printf ("error %d from tggetattr", errno);
                return;
        }

        tty.c_cc[VMIN]  = should_block ? 1 : 0;
        tty.c_cc[VTIME] = 5;            // 0.5 seconds read timeout

        if (tcsetattr (fd, TCSANOW, &tty) != 0)
                printf ("error %d setting term attributes", errno);
}

int expect_magic(int fd)
{
    int n;
    uint8_t val;
    bool aligned = false;

    while (!aligned) {

        // Our serial transmission is in big endian order

        do {
            n = read(fd, &val, 1);
            if (n <= 0) {
                printf("Align read failed\n");
                return -1;
            }
            // printf("Dropping... %02x\n", val);
        } while (val != MAGIC_H);

        n = read(fd, &val, 1);
        if (n <= 0) {
            printf("Align read failed\n");
            return -1;
        }

        if (val == MAGIC_L) {
            aligned = true;
            // printf("Aligned on magic\n");
        }
    }

    return 0;
}

int load_pixels(int fd, uint8_t *output, int width, int height) // output should be 3*size
{
    int i;
    uint8_t *input, *p;
    uint8_t *src, *dst;
    int remain;
    int n;
    int size;
    int16_t val;
    uint32_t scale;
    int mymax = -32768;
    int mymin = 32767;

    double x;

    size = width * 2;
    input = (uint8_t*)malloc(size);
    memset(input, 0, size);
    p = input;
    remain = size;

    // printf("waiting for column...\n");

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
    printf("frame received (%d)\n", size);

    // shift buf
    for (i=height-2; i>=0; i--) {
        src = output + (i * width * 3);
        dst = output + ((i+1) * width * 3);
        memcpy(dst, src, width * 3);
    }

    // there is no grayscale... use rgb...
    for (i=0; i<width; i++) {
        val = ((int16_t)input[2*i] << 8) | (input[2*i + 1]);
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
        printf("scale %d, x: %f, color.b %f\n", scale, x, color.b());

        output[3*i] = color.r() * 255;
        output[3*i+1] = color.g() * 255;
        output[3*i+2] = color.b() * 255;

        // output[3*i] = scale; // red
        // output[3*i+1] = scale; // green
        // output[3*i+2] = scale; // blue
    }

    printf("min %d, max %d\n", mymin, mymax);
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

    fd = open("/dev/ttyUSB5", O_RDWR | O_NOCTTY | O_SYNC);
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
