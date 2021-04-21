import os
import sys

import numpy as np

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: {} file.mfcc mfcc.h".format(sys.argv[0]))
        sys.exit(1)

    file_path = sys.argv[1]
    raw = np.fromfile(file_path, dtype=np.int16)
    arr = np.reshape(raw, (-1, 32))
    arr = arr[:,:16]

    file_bin = "/tmp/mfcc.bin"
    arr.tofile(file_bin)

    file_h = sys.argv[2]
    os.system("xxd -i {} | sed 's/_tmp_mfcc_bin/g_mfcc/' > {}".format(file_bin, file_h))
