#!/usr/bin/env python

import matplotlib.pyplot as plt
import mydata
import numpy as np

arr = np.array(mydata.mydata)

plt.figure(figsize=(15,5))
plt.imshow(np.transpose(arr), aspect='auto', origin='lower', cmap="inferno");

plt.show()
