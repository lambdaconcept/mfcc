#!/usr/bin/env python

import os
import sys
import glob
import sklearn
import librosa
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile

NCEPSTRUMS = 32

def main(path):
    filenames = sorted(glob.glob(path + "/*/*.wav"))
    for wav in filenames:
        root, ext = os.path.splitext(wav)
        fspec = root + ".spec"
        fsklearn = root + ".sklearn"
        print(wav, fspec)

        samples, sample_rate = librosa.load(wav, sr=None)
        spec = librosa.feature.mfcc(samples, sr=sample_rate,
                                    hop_length=170, n_mfcc=NCEPSTRUMS) # , lifter=22)
        scale = sklearn.preprocessing.scale(spec, axis=1)

        spec.astype(np.int16).tofile(fspec)
        scale.astype(np.int16).tofile(fsklearn)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: {} dirname".format(sys.argv[0]))
        sys.exit(1)

    main(sys.argv[1])
