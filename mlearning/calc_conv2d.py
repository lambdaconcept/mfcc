import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf

import dataset as ds
import fixedpoint as fp
import utils

def run(tflite_file, input_data):
    # Initialize the interpreter
    interpreter = tf.lite.Interpreter(model_path=str(tflite_file),
                                      experimental_preserve_all_tensors=True) # pip install tf-nightly
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    # Check if the input type is quantized, then rescale input data to int8
    if input_details['dtype'] == np.int8:
        input_scale, input_zero_point = input_details["quantization"]
        input_data = input_data / input_scale + input_zero_point

    input_data = np.expand_dims(input_data, axis=0).astype(input_details["dtype"])
    interpreter.set_tensor(input_details["index"], input_data)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details["index"])[0]

    if output_details['dtype'] == np.int8:
        output_scale, output_zero_point = output_details["quantization"]
        output = (output.astype(np.float32) - output_zero_point) * output_scale

    return interpreter

def show(interpreter):
    # Print intermediate tensors
    for t in interpreter.get_tensor_details():
        print(t['index'], t['name'], interpreter.get_tensor(t['index']))

# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/kernels/internal/reference/integer_ops/conv.h
def my_conv2d(din, din_details,
              kernels, kernels_details,
              bias, bias_details,
              dout_details, quantized=True):

    nkernels, h, w, _ = kernels.shape
    print("nkernels:", nkernels)
    fig, axs = plt.subplots(nrows=1, ncols=nkernels)

    # XXX no stride
    ivs = din[0][..., 0]
    ih, iw = ivs.shape
    # XXX no padding, odd size kernel
    oh = ih - (h - 1)
    ow = iw - (w - 1)

    if quantized:
        # Scales & Zero points
        iscale, izp = din_details["quantization"]
        oscale, ozp = dout_details["quantization"]
        print("zero points:", izp, ozp)
        kscales = kernels_details["quantization_parameters"]["scales"]
        print("kscales:", kscales)

        # Populate multiplier and shift using affine quantization
        params = utils.PopulateConvolutionQuantizationParams(
            iscale, izp, oscale, ozp, kscales
        )
        per_channel_multshifts, output_act_min, output_act_max = params
        print("per_channel_multshifts:", per_channel_multshifts)
        print("activation min max:", output_act_min, output_act_max)
    else:
        izp, ozp = 0, 0

    if quantized:
        dout = np.zeros((1, oh, ow, nkernels), dtype=np.int8)
    else:
        dout = np.zeros((1, oh, ow, nkernels))

    for k in range(nkernels):
        kernel = kernels[k]

        # Get rid of the channel shape # XXX
        kernel = kernel[..., 0]
        print("kernel:", kernel)

        for oi in range(oh):
            for oj in range(ow):

                # Conv
                acc = 0
                for i in range(h):
                    for j in range(w):
                        ival = ivs[oi + i][oj + j]
                        acc += (ival - izp) * kernel[i][j]

                # Bias
                acc += bias[k]

                if quantized:
                    # Per channel multiplier
                    output_multiplier, output_shift = per_channel_multshifts[k]
                    acc = fp.MultiplyByQuantizedMultiplier(acc, output_multiplier, output_shift)
                    acc += ozp

                    # Activation
                    if acc > output_act_max:
                        acc = output_act_max
                    if acc < output_act_min:
                        acc = output_act_min

                else:
                    # Activation (ReLU)
                    acc = acc if acc > 0 else 0

                dout[0][oi][oj][k] = acc

        axs[k].imshow(kernel) # , vmin=-128, vmax=127)

    return dout

def validate(din1, din2, quantized=True):
    nerrors = 0
    if quantized:
        EPSILON = 0
    else:
        EPSILON = 1e-5
    _, nrows, ncols, nchannels = din1.shape
    for k in range(nchannels):
        for i in range(nrows):
            for j in range(ncols):
                err = abs(din1[0][i][j][k] - din2[0][i][j][k])
                if err > EPSILON:
                    print("Error: [{}][{}][{}]: err: {}".format(i, j, k, err))
                    nerrors += 1
    return nerrors

def main():
    np.set_printoptions(precision=5,
                        threshold=sys.maxsize,
                        linewidth=256)
    # int or float ?
    quantized = True

    name = "simple"
    save_path = "saved/model_" + name + "/"
    if quantized:
        tflite_model_file = os.path.join(save_path, "model.tflite")
    else:
        tflite_model_file = os.path.join(save_path, "model_float.tflite")

    sample_file = "dataset/one/c37a72d3_nohash_0.mfcc"
    mfcc_binary = tf.io.read_file(sample_file)
    mfcc = ds.decode_mfcc(mfcc_binary).numpy()

    interpreter = run(tflite_model_file, mfcc)
    # show(interpreter)

    # For now tensor indexes are hardcoded
    if quantized:
        tensors = {
            "conv2d_in": 7,
            "conv2d_kernels": 3,
            "conv2d_bias": 4,
            "conv2d_out": 8,
        }
    else:
        tensors = {
            "conv2d_in": 7,
            "conv2d_kernels": 6,
            "conv2d_bias": 2,
            "conv2d_out": 8,
        }

    # Get Conv2D tensors
    conv2d_in       = interpreter.get_tensor(tensors["conv2d_in"])
    conv2d_kernels  = interpreter.get_tensor(tensors["conv2d_kernels"])
    conv2d_bias     = interpreter.get_tensor(tensors["conv2d_bias"])
    conv2d_out      = interpreter.get_tensor(tensors["conv2d_out"])

    details = interpreter.get_tensor_details()
    conv2d_in_details = details[tensors["conv2d_in"]]
    conv2d_kernels_details = details[tensors["conv2d_kernels"]]
    conv2d_bias_details = details[tensors["conv2d_bias"]]
    conv2d_out_details = details[tensors["conv2d_out"]]

    nkernels = len(conv2d_kernels)
    print("conv2d_bias:", conv2d_bias)

    # Show input image
    print("conv2d_in:", conv2d_in[0][..., 0]) # Show first input channel (from first batch)
    plt.figure()
    plt.imshow(conv2d_in[0][..., 0]) # vmin=-128, vmax=127)

    # Invoke our Conv2D
    my_out = my_conv2d(conv2d_in, conv2d_in_details,
                       conv2d_kernels, conv2d_kernels_details,
                       conv2d_bias, conv2d_bias_details,
                       conv2d_out_details, quantized=quantized)
    print("my_out:", my_out[0][..., 0]) # Show first input channel (from first batch)
    fig, axs = plt.subplots(nrows=1, ncols=nkernels)
    for i in range(nkernels):
        axs[i].imshow(my_out[0][..., i]) # , vmin=-128, vmax=127)

    # Compare with output from model
    print("conv2d_out:", conv2d_out[0][..., 0]) # Show first output channel (from first batch)
    fig, axs = plt.subplots(nrows=1, ncols=nkernels)
    for i in range(nkernels):
        axs[i].imshow(conv2d_out[0][..., i]) # , vmin=-128, vmax=127)

    ret = validate(my_out, conv2d_out, quantized=quantized)
    print("validate: nerrors:", ret)

    plt.show()

if __name__ == "__main__":
    main()
