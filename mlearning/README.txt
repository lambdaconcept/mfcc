Tensorflow lite with NuttX
==========================

1. Clone the submodules
-----------------------

git submodule update --init --recursive

2. Install libcxx
-----------------

cd libcxx
./install.sh ../nuttx/
cd ..

cd nuttx/include/libcxx
sed -i 's/^.*define _LIBCPP_HAS_QUICK_EXIT/\/\/ #define _LIBCPP_HAS_QUICK_EXIT/' __config
cd ../../../

3. Configure Nuttx
------------------

cd nuttx
./tools/configure.sh stm32f746g-disco:nsh
make context
cd ..

4. Build Tensorflow lite library
--------------------------------

TOPDIR="$(pwd)/nuttx"

cd tensorflow/
make -f tensorflow/lite/micro/tools/make/Makefile generate_projects
cd tensorflow/lite/micro/tools/make/gen/linux_x86_64_default/prj/hello_world/make

# ARM

CCFLAGS="-fno-builtin -fno-exceptions -fcheck-new -Wall -Wshadow -Wundef -mcpu=cortex-m7 -mthumb -mfloat-abi=soft -isystem "${TOPDIR}/include" -D__NuttX__ -DTFLITE_EMULATE_FLOAT" CXXFLAGS="-fno-builtin -fno-exceptions -fcheck-new -fno-rtti -Wall -Wshadow -mcpu=cortex-m7 -mthumb -mfloat-abi=soft -fpermissive -isystem "${TOPDIR}/include/libcxx" -isystem "${TOPDIR}/include" -D__NuttX__ -DTFLITE_EMULATE_FLOAT" make TARGET_TOOLCHAIN_PREFIX=arm-none-eabi- -j libtensorflow-microlite.a

# RISC-V

CCFLAGS="-fno-builtin -fno-exceptions -fcheck-new -Wall -Wshadow -Wundef -march=rv32im -mabi=ilp32 -isystem "${TOPDIR}/include" -D__NuttX__ -DTFLITE_EMULATE_FLOAT" CXXFLAGS="-fno-builtin -fno-exceptions -fcheck-new -fno-rtti -Wall -Wshadow -march=rv32im -mabi=ilp32 -fpermissive -isystem "${TOPDIR}/include/libcxx" -isystem "${TOPDIR}/include" -D__NuttX__ -DTFLITE_EMULATE_FLOAT" make TARGET_TOOLCHAIN_PREFIX=riscv64-elf- -j libtensorflow-microlite.a

cd ../../../../../../../../../../../

5. Train the model
------------------

This requires the dataset with generated mfcc files
cd dataset
sh ../pad_mfcc.sh
cd ..

python train.py

6. Convert to TFLite
--------------------

python convert.py

xxd -i saved/model_tiny_embedding_conv/model.tflite > apps/examples/helloxx/model.h
sed -i 's/unsigned char .*\[\]/unsigned char g_model[]/' apps/examples/helloxx/model.h

Invoke float/quantized models with python API to check accuracy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

python invoke.py

Visualize quantized model
^^^^^^^^^^^^^^^^^^^^^^^^^

python /mnt/data/prog/tensorflow/tensorflow/lite/tools/visualize.py saved/model_tiny_embedding_conv/model.tflite saved/model_tiny_embedding_conv/model.html

7. Build Nuttx
--------------

TFLIBDIR="$(pwd)/tensorflow/tensorflow/lite/micro/tools/make/gen/linux_x86_64_default/prj/hello_world/make"

cd nuttx
EXTRA_LIBS="${TFLIBDIR}/libtensorflow-microlite.a" make -j

8. Program the device
---------------------

# STM32F746 DISCO

cp nuttx.bin /run/media/po/DIS_F746NG/

# ECPIX

flterm --speed 1000000 --kernel nuttx.bin --kernel-addr 0x17000 /dev/ttyUSB1
BIOS> serialboot

================================================================================
Profiling the model
===================

1. Install bazel
----------------

yay -S bazel3

2. Build the benchmark tool
---------------------------

cd tensorflow//
bazel build -c opt tensorflow/lite/tools/benchmark:benchmark_model
bazel build -c opt tensorflow/lite/tools/benchmark:benchmark_model_performance_options

3. Run
------

bazel-bin/tensorflow/lite/tools/benchmark/benchmark_model --graph=../saved/model_tiny_embedding_conv/model.tflite --num_threads=1 --enable_op_profiling=true
bazel-bin/tensorflow/lite/tools/benchmark/benchmark_model_performance_options --graph=../saved/model_tiny_embedding_conv/model.tflite --num_threads=1 --enable_op_profiling=true
