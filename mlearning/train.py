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

ncepstrums = 32
nframes = ds.input_shape[0] // ncepstrums

# Define and train the model

model = models.Sequential([
    layers.Reshape((-1, nframes, ncepstrums, 1), input_shape=ds.input_shape),
    layers.Conv2D(8, 9, activation='relu'),
    layers.Dropout(0.25),
    layers.Flatten(),
    layers.Dense(ds.num_labels, activation="softmax"),
])

model.summary()

log_dir = "logs/fitmfcc/" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=log_dir, histogram_freq=1)

model.compile(
    optimizer=tf.keras.optimizers.Adam(),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=["accuracy"],
)

EPOCHS = 50
history = model.fit(
    ds.train_ds,
    validation_data=ds.val_ds,
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
