.PHONY: all clean

all:
	mkdir -p build
	cd build && cmake ../src -DCMAKE_BUILD_TYPE=Release && make
	mkdir -p bin && cp build/speexdsp-cli bin/

clean:
	rm -rf build/
