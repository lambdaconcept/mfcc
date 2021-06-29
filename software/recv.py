import serial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

NFRAMES = 93
NCEPSTRUMS = 16

MAGIC_H = 0xa5
MAGIC_L = 0x5a

def expect_magic(sdev):

    aligned = False
    while not aligned:

        # Our serial transmission is in big endian order
        while sdev.read(1) != bytes([MAGIC_H]):
            print("Dropping...")
            pass
        if sdev.read(1) == bytes([MAGIC_L]):
            aligned = True
            print("Aligned on magic")

def get_frame(frame, sdev, ax):
    ax.cla()

    im = []
    for i in range(NFRAMES):

        expect_magic(sdev)

        data = sdev.read(NCEPSTRUMS * 2)
        print(data.hex())

        raw = np.zeros(NCEPSTRUMS, dtype=np.int16)
        for i in range(NCEPSTRUMS):
            raw[i] = (data[2*i] << 8) | data[2*i + 1]

        im.append(raw)

    # ax.imshow(np.transpose(im), aspect='auto', origin='lower', cmap="inferno")

def main():
    sdev = serial.Serial("/dev/ttyUSB2", baudrate=1e6)
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)

    while True:
        get_frame(fig, sdev, ax)
    # ani = FuncAnimation(fig, get_frame, fargs=(sdev, ax), interval=1)
    plt.show()

if __name__ == "__main__":
    main()
