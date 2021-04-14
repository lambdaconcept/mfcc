import os
import sys
import pathlib

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf

import dataset as ds

# Helper function to run inference on a TFLite model
def run_tflite_model(tflite_file, test_image_indices):
    global test_audio

    # Initialize the interpreter
    interpreter = tf.lite.Interpreter(model_path=str(tflite_file))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    print("input_details quantization:", input_details["quantization"])
    print("output_details quantization:", output_details["quantization"])

    predictions = np.zeros((len(test_image_indices),), dtype=int)
    probas = []
    for i, test_index in enumerate(test_image_indices):
        test_image = test_audio[test_index]

        # Check if the input type is quantized, then rescale input data to int8
        if input_details['dtype'] == np.int8:
            input_scale, input_zero_point = input_details["quantization"]
            test_image = test_image / input_scale + input_zero_point

        test_image = np.expand_dims(test_image, axis=0).astype(input_details["dtype"])
        interpreter.set_tensor(input_details["index"], test_image)
        interpreter.invoke()
        output = interpreter.get_tensor(output_details["index"])[0]

        if output_details['dtype'] == np.int8:
            output_scale, output_zero_point = output_details["quantization"]
            if i == 0:
                print("Output quantized:", output)
            output = (output.astype(np.float32) - output_zero_point) * output_scale
        if i == 0:
            print("Output:", output)

        predictions[i] = output.argmax()
        probas.append(output)

    return predictions, probas

## Helper function to test the models on one image
def test_model(tflite_file, test_index, model_type):
    global test_labels

    predictions, probas = run_tflite_model(tflite_file, [test_index])
    print(probas[0])

    # plt.imshow(tf.reshape(test_audio[test_index], [-1, ds.ncepstrums]))
    plt.bar(ds.commands, probas[0])

    val = test_labels[test_index]
    if val != "?":
        val = str(ds.commands[int(val)])
    predict = str(ds.commands[int(predictions[0])])

    template = model_type + " Model \n True:{true}, Predicted:{predict}"
    plt.title(template.format(true=val, predict=predict))
    plt.grid(False)
    plt.show()

# Helper function to evaluate a TFLite model on all images
def evaluate_model(tflite_file, model_type):
    global test_audio
    global test_labels

    test_image_indices = range(test_audio.shape[0])
    predictions, _ = run_tflite_model(tflite_file, test_image_indices)

    accuracy = (np.sum(test_labels== predictions) * 100) / len(test_audio)

    print('%s model accuracy is %.4f%% (Number of test samples=%d)' % (
        model_type, accuracy, len(test_audio)))

# Evaluate test set performance
def run_all():
    global test_audio
    global test_labels

    for audio, label in ds.test_ds:
        test_audio.append(audio.numpy())
        test_labels.append(label.numpy())

    test_audio = np.array(test_audio)
    test_labels = np.array(test_labels)

    test_index = 0
    print("Working on MFCC file:", ds.test_files[test_index])
    test_model(tflite_model_file, test_index, model_type="Float")
    test_model(tflite_model_quant_file, test_index, model_type="Quantized")

    evaluate_model(tflite_model_file, model_type="Float")
    evaluate_model(tflite_model_quant_file, model_type="Quantized")

def run_one(sample_file):
    global test_audio
    global test_labels

    mfcc_binary = tf.io.read_file(sample_file)
    mfcc = ds.decode_mfcc(mfcc_binary)

    test_audio.append(mfcc.numpy())
    test_labels.append("?")

    test_model(tflite_model_quant_file, 0, model_type="Quantized")

test_audio = []
test_labels = []

name = "tiny_embedding_conv"
save_path = "saved/model_" + name + "/"
tflite_model_file = os.path.join(save_path, "model_float.tflite")
tflite_model_quant_file = os.path.join(save_path, "model.tflite")

if len(sys.argv) < 2:
    run_all()
else:
    run_one(sys.argv[1])
