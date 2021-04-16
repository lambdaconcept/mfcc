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
CCFLAGS="-fno-builtin -fno-exceptions -fcheck-new -Wall -Wshadow -Wundef -mcpu=cortex-m7 -mthumb -mfloat-abi=soft -isystem "${TOPDIR}/include" -D__NuttX__ -DTFLITE_EMULATE_FLOAT" CXXFLAGS="-fno-builtin -fno-exceptions -fcheck-new -fno-rtti -Wall -Wshadow -mcpu=cortex-m7 -mthumb -mfloat-abi=soft -fpermissive -isystem "${TOPDIR}/include/libcxx" -isystem "${TOPDIR}/include" -D__NuttX__ -DTFLITE_EMULATE_FLOAT" make TARGET_TOOLCHAIN_PREFIX=arm-none-eabi- -j libtensorflow-microlite.a
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

cp nuttx.bin /run/media/po/DIS_F746NG/
