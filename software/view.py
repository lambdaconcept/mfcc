#!/usr/bin/env python

import sys
import matplotlib.pyplot as plt
import numpy as np

NCEPSTRUMS = 32

def main(path):
    raw = np.fromfile(path, dtype=np.int16)
    arr = np.reshape(raw, (-1, NCEPSTRUMS))
    print("cepstrum sets:", arr.shape)

    plt.figure(figsize=(15,5))
    plt.imshow(np.transpose(arr), aspect='auto', origin='lower', cmap="inferno");

    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: {} cepstrum.bin".format(sys.argv[0]))
        sys.exit(1)

    main(sys.argv[1])
