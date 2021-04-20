import numpy as np

# https://github.com/google/gemmlowp/blob/master/fixedpoint/fixedpoint.h

# Correctly-rounded-to-nearest division by a power-of-two.
# Also known as a rounding arithmetic right shift.
def RoundingDivideByPOT(x, exponent):
    assert(exponent >= 0)
    assert(exponent <= 31)
    mask = ((1 << exponent) - 1)
    remainder = x & mask
    threshold = (mask >> 1) + (1 if (x < 0) else 0)
    return (x >> exponent) + (1 if (remainder > threshold) else 0)

# Returns the integer that represents the product of two fixed-point
# numbers, interpreting all integers as fixed-point values in the
# interval [-1, 1), rounding to the nearest value, and saturating
# -1 * -1 to the maximum value (since 1 is not in the half-open
# interval [-1, 1)).
def SaturatingRoundingDoublingHighMul(a, b):
    overflow = (a == b) and (a == -2147483648) # std::numeric_limits<std::int32_t>::min()
    ab_64 = np.int64(a) * np.int64(b)
    nudge = (1 << 30) if (ab_64 >= 0) else (1 - (1 << 30))
    ab_x2_high32 = np.int32(((ab_64 + nudge) / (1 << 31)))
    return 2147483647 if overflow else ab_x2_high32; # std::numeric_limits<std::int32_t>::max()

# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/kernels/internal/common.h
def MultiplyByQuantizedMultiplier(x, quantized_multiplier, shift):
    left_shift = shift if (shift > 0) else 0
    right_shift = 0 if (shift > 0) else -shift
    return RoundingDivideByPOT(SaturatingRoundingDoublingHighMul(
                                   x * (1 << left_shift), quantized_multiplier),
                               right_shift)
