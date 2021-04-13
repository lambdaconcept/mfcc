import os
import pathlib

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf

seed = 42
tf.random.set_seed(seed)
np.random.seed(seed)

nmfcc = 32
ncepstrums = 16

# Import the Speech Commands dataset

data_dir = pathlib.Path("dataset")
commands = np.array(sorted(tf.io.gfile.listdir(str(data_dir))))
commands = commands[commands != "README.md"]
print("Commands:", commands)

filenames = sorted(tf.io.gfile.glob(str(data_dir) + "/*/*.mfcc"))
filenames = tf.random.shuffle(filenames)
num_samples = len(filenames)
print("Number of total examples:", num_samples)
print("Number of examples per label:", len(tf.io.gfile.listdir(str(data_dir/commands[0]))))
print("Example file tensor:", filenames[0])

sts = int(num_samples * 0.80)
svs = int(num_samples * 0.90)
train_files = filenames[:sts]
val_files = filenames[sts:svs]
test_files = filenames[svs:]
print("Training set size:", len(train_files))
print("Validation set size:", len(val_files))
print("Test set size:", len(test_files))

# Reading audio files and their labels

def decode_mfcc(mfcc_binary):
    mfcc = tf.io.decode_raw(mfcc_binary, tf.int16)
    mfcc = tf.reshape(mfcc, [-1, nmfcc])
    mfcc = tf.reshape(mfcc[:,:ncepstrums], [-1])
    return mfcc

def get_label(file_path):
    parts = tf.strings.split(file_path, os.path.sep)
    return parts[-2]

def get_mfcc_and_label(file_path):
    label = get_label(file_path)
    mfcc_binary = tf.io.read_file(file_path)
    mfcc = decode_mfcc(mfcc_binary)
    return mfcc, label

AUTOTUNE = tf.data.AUTOTUNE
files_ds = tf.data.Dataset.from_tensor_slices(train_files)
mfcc_ds = files_ds.map(get_mfcc_and_label, num_parallel_calls=AUTOTUNE)

def get_mfcc_and_label_id(mfcc, label):
    label_id = tf.argmax(label == commands)
    # mfcc = tf.expand_dims(mfcc, -1)
    return mfcc, label_id

mfcc_ds = mfcc_ds.map(get_mfcc_and_label_id, num_parallel_calls=AUTOTUNE)

def preprocess_dataset(files):
    files_ds = tf.data.Dataset.from_tensor_slices(files)
    output_ds = files_ds.map(get_mfcc_and_label, num_parallel_calls=AUTOTUNE)
    output_ds = output_ds.map(get_mfcc_and_label_id, num_parallel_calls=AUTOTUNE)
    return output_ds

train_ds = mfcc_ds
val_ds = preprocess_dataset(val_files)
test_ds = preprocess_dataset(test_files)

batch_size = 256
train_ds = train_ds.batch(batch_size)
val_ds = val_ds.batch(batch_size)

train_ds = train_ds.cache().prefetch(AUTOTUNE)
val_ds = val_ds.cache().prefetch(AUTOTUNE)

for mfcc, _ in mfcc_ds.take(1):
    input_shape = mfcc.shape

print("Input shape:", input_shape)
num_labels = len(commands)

nframes = input_shape[0] // ncepstrums
print("N frames:", nframes)
