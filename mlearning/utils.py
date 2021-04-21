import math
import numpy as np

# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/kernels/internal/quantization_util.cc
def QuantizeMultiplier(double_multiplier):
    if (double_multiplier == 0.):
        return (0, 0)

    q, shift = math.frexp(double_multiplier)
    q_fixed = round(q * (1 << 31))

    if (q_fixed == (1 << 31)):
        q_fixed /= 2
        shift += 1

    if (shift < -31):
        shift = 0
        q_fixed = 0

    return (np.int32(q_fixed), shift)

def CalculateActivationRangeQuantizedImpl(qmin, qmax, scale, zero_point):
    # ReLU
    act_min = zero_point
    act_max = qmax
    return (act_min, act_max)

# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/kernels/kernel_util.cc
def CalculateActivationRangeQuantized(output_scale, output_zero_point):
    qmin = -128 # std::numeric_limits<int8_t>::min();
    qmax = 127 # std::numeric_limits<int8_t>::max();

    return CalculateActivationRangeQuantizedImpl(qmin, qmax, output_scale, output_zero_point)

# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/kernels/kernel_util.cc
def PopulateConvolutionQuantizationParams(input_scale, input_zero_point,
                                          output_scale, output_zero_point,
                                          filter_scales):
    # Populate multiplier and shift using affine quantization.
    per_channel_multshifts = []

    nfilters = len(filter_scales)
    for i in range(nfilters):
        effective_output_scale = input_scale * filter_scales[i] / output_scale
        mult, shift = QuantizeMultiplier(effective_output_scale)
        per_channel_multshifts.append((mult, shift))

    act_min, act_max = CalculateActivationRangeQuantized(output_scale, output_zero_point)
    return per_channel_multshifts, act_min, act_max
