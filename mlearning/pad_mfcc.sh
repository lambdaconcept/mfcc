for file in $(find . -name "*.mfcc"); do
	i_size=$(stat --printf="%s" $file)
	pad=$((5952 - $i_size))
	dd if=/dev/zero of=$file bs=1 count=$pad seek=$i_size
	echo "padded $file"
done

rm validation_list.txt testing_list.txt speech_commands_v0.01.tar.gz README.md md5deep.txt LICENSE
