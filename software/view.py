#!/usr/bin/env python

import sys
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile

NCEPSTRUMS = 32

def main(path):
    wav = path + ".wav"
    mfcc = path + ".mfcc"

    fig, axs = plt.subplots(2, figsize=(15,8))

    sample_rate, audio = wavfile.read(wav)
    axs[0].plot(np.linspace(0, len(audio) / sample_rate, num=len(audio)), audio)
    axs[0].grid(True)

    raw = np.fromfile(mfcc, dtype=np.int16)
    arr = np.reshape(raw, (-1, NCEPSTRUMS))
    print("cepstrum sets:", arr.shape)

    axs[1].imshow(np.transpose(arr), aspect='auto', origin='lower', cmap="inferno");

    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: {} basename".format(sys.argv[0]))
        sys.exit(1)

    main(sys.argv[1])
