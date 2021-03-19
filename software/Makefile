all:
	gcc *.c libwav/src/*.c -I libwav/include -lusb-1.0 -o mfcc

run:
	# ./mfcc ../f2bjrop1.0.wav cepstrum.bin
	# python view.py cepstrum.bin
	./mfcc dataset
