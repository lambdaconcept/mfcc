#ifndef __SERIAL_H
#define __SERIAL_H

#ifdef __cplusplus
extern "C"
{
#endif

int set_interface_attribs (int fd, int speed, int parity);
void set_blocking (int fd, int should_block);
int open_serial(const char *devpath);
int expect_magic(int fd);

#ifdef __cplusplus
}
#endif

#endif /* __SERIAL_H */
