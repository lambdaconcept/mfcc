import os
import pathlib

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import tensorflow as tf

from tensorflow.keras.layers.experimental import preprocessing
from tensorflow.keras import layers
from tensorflow.keras import models


seed = 42
tf.random.set_seed(seed)
np.random.seed(seed)

# Import the Speech Commands dataset

# data_dir = pathlib.Path("data/speech_commands_v0_01")
data_dir = pathlib.Path("dataset")
commands = np.array(tf.io.gfile.listdir(str(data_dir)))
commands = commands[commands != "README.md"]
print("Commands:", commands)

filenames = tf.io.gfile.glob(str(data_dir) + "/*/*.mfcc")
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
    mfcc = tf.reshape(mfcc, [-1, 32])
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

# rows = 3
# cols = 3
# n = rows * cols
# fig, axes = plt.subplots(rows, cols, figsize=(15, 8))
# for i, (mfcc, label) in enumerate(mfcc_ds.take(n)):
#     r = i // cols
#     c = i % cols
#     ax = axes[r][c]
#     ax.imshow(mfcc, aspect="auto", origin="lower", cmap="inferno")
#     # ax.set_yticks(np.arange(-1.2, 1.2, 0.2))
#     label = label.numpy().decode("utf-8")
#     ax.set_title(label)
# plt.show()

# def pad_mfcc(mfcc):
#     p = tf.constant([[0, 0], [0, 93 - mfcc.shape[1]]])
#     mfcc = tf.pad(mfcc, p, "CONSTANT")
#     return mfcc

def get_mfcc_and_label_id(mfcc, label):
    label_id = tf.argmax(label == commands)
    mfcc = tf.expand_dims(mfcc, -1)
    return mfcc, label_id

mfcc_ds = mfcc_ds.map(get_mfcc_and_label_id, num_parallel_calls=AUTOTUNE)

# # rows = 3
# # cols = 3
# # n = rows * cols
# # fig, axes = plt.subplots(rows, cols, figsize=(10, 10))
# # for i, (spectrogram, label_id) in enumerate(spectrogram_ds.take(n)):
# #     r = i // cols
# #     c = i % cols
# #     ax = axes[r][c]
# #     plot_spectrogram(np.squeeze(spectrogram.numpy()), ax)
# #     ax.set_title(commands[label_id.numpy()])
# #     ax.axis("off")

# Build and train the model

def preprocess_dataset(files):
    files_ds = tf.data.Dataset.from_tensor_slices(files)
    output_ds = files_ds.map(get_mfcc_and_label, num_parallel_calls=AUTOTUNE)
    output_ds = output_ds.map(get_mfcc_and_label_id, num_parallel_calls=AUTOTUNE)
    return output_ds

train_ds = mfcc_ds
val_ds = preprocess_dataset(val_files)
test_ds = preprocess_dataset(test_files)

batch_size = 64
train_ds = train_ds.batch(batch_size)
val_ds = val_ds.batch(batch_size)

train_ds = train_ds.cache().prefetch(AUTOTUNE)
val_ds = val_ds.cache().prefetch(AUTOTUNE)

for mfcc, _ in mfcc_ds.take(1):
    input_shape = mfcc.shape

print("Input shape:", input_shape)
num_labels = len(commands)

# model = models.Sequential([
#     layers.Input(input_shape),
#     layers.LSTM(512, return_sequences=True),
#     layers.LSTM(512, return_sequences=False),
#     layers.Dropout(0.3),
#     layers.Dense(288, activation="relu"),
#     layers.Dropout(0.5),
#     layers.Dense(num_labels, activation="softmax"),
# ])

model = models.Sequential([
    layers.Input(shape=input_shape),
    layers.Conv2D(8, 9, activation='relu'),
    layers.Dropout(0.25),
    layers.Flatten(),
    layers.Dense(num_labels, activation="softmax"),
])

model.summary()

import datetime
log_dir = "logs/fitmfcc/" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=log_dir, histogram_freq=1)

model.compile(
    optimizer=tf.keras.optimizers.Adam(),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=["accuracy"],
)

EPOCHS = 50
history = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=EPOCHS,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", patience=3, factor=0.2, min_lr=0.001),
    ]
)

save_path = "saved/model_mfcc/"
tf.saved_model.save(model, save_path)

# Evaluate test set performance

test_audio = []
test_labels = []

for audio, label in test_ds:
    test_audio.append(audio.numpy())
    test_labels.append(label.numpy())

test_audio = np.array(test_audio)
test_labels = np.array(test_labels)

y_pred = np.argmax(model.predict(test_audio), axis=1)
y_true = test_labels

test_acc = sum(y_pred == y_true) / len(y_true)
print(f"Test set accuracy: {test_acc:.0%}")

## Display a confusion matrix

confusion_mtx = tf.math.confusion_matrix(y_true, y_pred)
plt.figure(figsize=(10, 8))
sns.heatmap(confusion_mtx, xticklabels=commands, yticklabels=commands,
            annot=True, fmt="g")
plt.xlabel("Prediction")
plt.ylabel("Label")

# # Run inference on an audio file

# sample_file = data_dir/"no/01bb6a2a_nohash_0.wav"
# sample_ds = preprocess_dataset([str(sample_file)])

# for spectrogram, label in sample_ds.batch(1):
#     prediction = model(spectrogram)

# plt.bar(commands, tf.nn.softmax(prediction[0]))
# plt.title(f"Predictions for \"{commands[label[0]]}\"")

# plt.show()
