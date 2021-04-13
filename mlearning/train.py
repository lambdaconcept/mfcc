import os
import pathlib
import datetime

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import tensorflow as tf

import dataset as ds

from tensorflow.keras.layers.experimental import preprocessing
from tensorflow.keras import layers
from tensorflow.keras import models

seed = 42
tf.random.set_seed(seed)
np.random.seed(seed)

# Define and train the model

store = {}

# Conv
# store["conv"] = models.Sequential([
#     layers.Reshape((-1, ds.nframes, ds.ncepstrums, 1), input_shape=ds.input_shape),
#     layers.Conv2D(64, (20, 8), strides=(1, 1), padding="same", activation="relu"),
#     layers.Dropout(0.25),
#     layers.MaxPool2D(pool_size=(2, 2), strides=(2, 2), padding="same"),
#     layers.Conv2D(64, (10, 4), strides=(1, 1), padding="same", activation="relu"),
#     layers.Dropout(0.25),
#     layers.Flatten(),
#     layers.Dense(ds.num_labels, activation="softmax"),
# ])

# Low Latency Conv
# Trainable params: 3,061,593
# Test set accuracy: 81%
store["low_latency_conv"] = models.Sequential([
    layers.Reshape((-1, ds.nframes, ds.ncepstrums, 1), input_shape=ds.input_shape),
    layers.Conv2D(16, (32, 9), strides=(1, 1), padding="same", activation="relu"),
    layers.Dropout(0.25),
    layers.Flatten(),
    layers.Dense(64),
    layers.Dropout(0.25),
    layers.Dense(128),
    layers.Dropout(0.25),
    layers.Dense(ds.num_labels, activation="softmax"),
])

# Tiny Conv
# Trainable params: 54,809
# Test set accuracy: 73%
store["tiny_conv"] = models.Sequential([
    layers.Reshape((-1, ds.nframes, ds.ncepstrums, 1), input_shape=ds.input_shape),
    layers.Conv2D(8, (9, 9), strides=(2, 2), padding="same", activation="relu"),
    layers.Dropout(0.25),
    layers.Flatten(),
    layers.Dense(ds.num_labels, activation="softmax"),
])

# Tiny Embedding Conv
# (32 cepstrums)
# Trainable params: 55,393
# Test set accuracy: 84%-86%
# (16 cepstrums)
# Trainable params: 28,321
# Test set accuracy: 85%
store["tiny_embedding_conv"] = models.Sequential([
    layers.Reshape((-1, ds.nframes, ds.ncepstrums, 1), input_shape=ds.input_shape),
    layers.Conv2D(8, (9, 9), strides=(2, 2), padding="same", activation="relu"),
    layers.Dropout(0.25),
    layers.Conv2D(8, (3, 3), strides=(1, 1), padding="same", activation="relu"),
    layers.Dropout(0.25),
    layers.Flatten(),
    # layers.Dense(64),
    # layers.Dropout(0.25),
    layers.Dense(ds.num_labels, activation="softmax"),
])

# From kaggle
store["kaggle"] = models.Sequential([
    layers.Reshape((-1, ds.nframes, ds.ncepstrums, 1), input_shape=ds.input_shape),
    layers.Conv2D(8, (9, 3), strides=(2, 2), padding="same", activation="relu"),
    # layers.Conv2D(8, (1, 7), strides=(1, 1), padding="same", activation="relu"),
    layers.Conv2D(16, (1, 9), strides=(1, 1), padding="same", activation="relu"),
    layers.Conv2D(16, (9, 1), strides=(1, 1), padding="same", activation="relu"),
    layers.Dropout(0.25),
    layers.Flatten(),
    layers.Dense(64),
    layers.Dropout(0.25),
    layers.Dense(ds.num_labels, activation="softmax"),
])

# LSTM (Not convertible ?)
# Trainable params: 25,481
# Test set accuracy: 73%
store["lstm"] = models.Sequential([
    layers.Reshape((ds.nframes, ds.ncepstrums), input_shape=ds.input_shape),
    layers.LSTM(64, return_sequences=False),
    layers.Dropout(0.25),
    layers.Dense(64, activation="relu"),
    layers.Dropout(0.25),
    layers.Flatten(),
    layers.Dense(ds.num_labels, activation="softmax"),
])

name = "tiny_embedding_conv"
model = store[name]
model.summary()

log_dir = "logs/fit_" + name + "/" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=log_dir, histogram_freq=1)

model.compile(
    optimizer=tf.keras.optimizers.Adam(),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=["accuracy"],
)

EPOCHS = 200
history = model.fit(
    ds.train_ds,
    validation_data=ds.val_ds,
    epochs=EPOCHS,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", patience=3, factor=0.2, min_lr=0.001),
        tensorboard_callback,
    ]
)

save_path = "saved/model_" + name + "/"
tf.saved_model.save(model, save_path)

# Evaluate test set performance

test_audio = []
test_labels = []

for audio, label in ds.test_ds:
    test_audio.append(audio.numpy())
    test_labels.append(label.numpy())

test_audio = np.array(test_audio)
test_labels = np.array(test_labels)

y_pred = np.argmax(model.predict(test_audio), axis=1)
y_true = test_labels

test_acc = sum(y_pred == y_true) / len(y_true)
print(f"Test set accuracy: {test_acc:.0%}")

# Display a confusion matrix

confusion_mtx = tf.math.confusion_matrix(y_true, y_pred)
plt.figure(figsize=(10, 8))
sns.heatmap(confusion_mtx, xticklabels=ds.commands, yticklabels=ds.commands,
            annot=True, fmt="g")
plt.xlabel("Prediction")
plt.ylabel("Label")

# # Run inference on an audio file

# sample_file = data_dir/"no/01bb6a2a_nohash_0.wav"
# sample_ds = preprocess_dataset([str(sample_file)])

# for spectrogram, label in sample_ds.batch(1):
#     prediction = model(spectrogram)

# plt.bar(ds.commands, tf.nn.softmax(prediction[0]))
# plt.title(f"Predictions for \"{ds.commands[label[0]]}\"")

# plt.show()
