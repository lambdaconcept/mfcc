#!/usr/bin/env python

import os
import sys
import glob
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile

NCEPSTRUMS = 32

def lifter(cepstra, L=22):
    """Apply a cepstral lifter the the matrix of cepstra. This has the effect of increasing the
    magnitude of the high frequency DCT coeffs.
    :param cepstra: the matrix of mel-cepstra, will be numframes * numcep in size.
    :param L: the liftering coefficient to use. Default is 22. L <= 0 disables lifter.
    """
    if L > 0:
        nframes,ncoeff = np.shape(cepstra)
        print("nframes", nframes, "ncoeff", ncoeff)
        n = np.arange(ncoeff)
        lift = 1 + (L/2.)*np.sin(np.pi*n/L)
        return lift*cepstra
    else:
        # values of L <= 0, do nothing
        return cepstra

def main(path):
    filenames = sorted(glob.glob(path + "/*/*.mfcc"))
    for mfcc in filenames:
        root, ext = os.path.splitext(mfcc)
        lift = root + ".lift"
        print(mfcc, lift)

        raw = np.fromfile(mfcc, dtype=np.int16)
        arr = np.reshape(raw, (-1, NCEPSTRUMS))
        print("cepstrum sets:", arr.shape)
        arr = lifter(arr)
        arr.astype(np.int16).tofile(lift)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: {} dirname".format(sys.argv[0]))
        sys.exit(1)

    main(sys.argv[1])
