import os
import pathlib
import tensorflow as tf

name = "tiny_embedding_conv"
save_path = "saved/model_" + name + "/"
converter = tf.lite.TFLiteConverter.from_saved_model(save_path)
# converter = tf.compat.v1.lite.TFLiteConverter.from_saved_model(save_path)
# converter.experimental_new_converter = True
# converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS,
#                                        tf.lite.OpsSet.SELECT_TF_OPS]
tflite_model = converter.convert()

export_path = os.path.join(save_path, "model_float.tflite")
with open(export_path, 'wb') as f:
    f.write(tflite_model)

# # # Post-training quantization
# https://www.tensorflow.org/lite/performance/post_training_quantization

seed = 42
tf.random.set_seed(seed)

def decode_mfcc(mfcc_binary):
    mfcc = tf.io.decode_raw(mfcc_binary, tf.int16)
    mfcc = tf.reshape(mfcc, [-1, 32])
    return mfcc

def get_mfcc(file_path):
    mfcc_binary = tf.io.read_file(file_path)
    mfcc = decode_mfcc(mfcc_binary)
    return mfcc

def representative_dataset():
    AUTOTUNE = tf.data.AUTOTUNE
    data_dir = pathlib.Path("dataset")
    filenames = tf.io.gfile.glob(str(data_dir) + "/*/*.mfcc")
    filenames = tf.random.shuffle(filenames)
    files_ds = tf.data.Dataset.from_tensor_slices(filenames)
    mfcc_ds = files_ds.map(get_mfcc, num_parallel_calls=AUTOTUNE)

    for data in mfcc_ds.batch(1).take(100):
        yield [tf.expand_dims(tf.dtypes.cast(data, tf.float32), -1)]

converter = tf.lite.TFLiteConverter.from_saved_model(save_path)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
# converter.optimizations = [tf.lite.Optimize.OPTIMIZE_FOR_SIZE]
# converter.experimental_new_converter = True
# converter.experimental_new_quantizer = True
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8
tflite_model = converter.convert()

export_path = os.path.join(save_path, "model.tflite")
with open(export_path, 'wb') as f:
    f.write(tflite_model)
