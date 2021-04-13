import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras import models
import kerastuner as kt

import dataset as ds

def model_builder(hp):

  model = models.Sequential([
    layers.Reshape((-1, ds.nframes, ds.ncepstrums, 1), input_shape=ds.input_shape),

    layers.Conv2D(
        hp.Int('units_0', min_value=6, max_value=64, step=2),
        kernel_size=(
            hp.Int("kern_0_h", min_value=3, max_value=15, step=2),
            hp.Int("kern_0_w", min_value=3, max_value=15, step=2),
        ),
        strides=(
            hp.Int("stride_0_h", min_value=1, max_value=5, step=1),
            hp.Int("stride_0_w", min_value=1, max_value=5, step=1),
        ),
        padding="same",
        activation="relu",
    ),
    layers.Dropout(
        hp.Float("dropout_0", min_value=0.15, max_value=0.5, step=0.025),
    ),

    layers.Conv2D(
        hp.Int("unit_1", min_value=6, max_value=32, step=2),
        kernel_size=(
            hp.Int("kern_1_h", min_value=3, max_value=7, step=1),
            hp.Int("kern_1_w", min_value=3, max_value=7, step=1),
        ),
        strides=(
            hp.Int("stride_1_h", min_value=1, max_value=4, step=1),
            hp.Int("stride_1_w", min_value=1, max_value=4, step=1),
        ),
        padding="same",
        activation="relu"
    ),
    layers.Dropout(
        hp.Float("dropout_1", min_value=0.15, max_value=0.5, step=0.025),
    ),

    layers.Flatten(),
    layers.Dense(ds.num_labels, activation="softmax"),
  ])

  # Tune the learning rate for the optimizer
  # Choose an optimal value from 0.01, 0.001, or 0.0001
  hp_learning_rate = hp.Choice('learning_rate', values=[1e-2, 1e-3, 1e-4])

  model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=hp_learning_rate),
                loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                metrics=['accuracy'])

  return model

tuner = kt.Hyperband(model_builder,
                     objective='val_accuracy',
                     max_epochs=200,
                     factor=3,
                     directory='tuning',
                     project_name='tiny_embedding_conv')

stop_early = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5)
tuner.search(
        ds.train_ds,
        validation_data=ds.val_ds,
        epochs=200,
        callbacks=[stop_early]
)

tuner.results_summary()

best_hps=tuner.get_best_hyperparameters(num_trials=1)[0]

model = tuner.hypermodel.build(best_hps)
history = model.fit(
        ds.train_ds,
        validation_data=ds.val_ds,
        epochs=200)

val_acc_per_epoch = history.history['val_accuracy']
best_epoch = val_acc_per_epoch.index(max(val_acc_per_epoch)) + 1
print('Best epoch: %d' % (best_epoch,))
