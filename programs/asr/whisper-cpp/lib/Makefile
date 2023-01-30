UNAME_M := $(shell uname -m)

CFLAGS   = -Iwhisper.cpp -O3 -std=c11   -fPIC
CXXFLAGS = -Iwhisper.cpp -O3 -std=c++11 -fPIC --shared -static-libstdc++
LDFLAGS  =

# Linux
CFLAGS   += -pthread
CXXFLAGS += -pthread

AVX1_M := $(shell grep "avx " /proc/cpuinfo)
ifneq (,$(findstring avx,$(AVX1_M)))
	CFLAGS += -mavx
endif
AVX2_M := $(shell grep "avx2 " /proc/cpuinfo)
ifneq (,$(findstring avx2,$(AVX2_M)))
	CFLAGS += -mavx2
endif
FMA_M := $(shell grep "fma " /proc/cpuinfo)
ifneq (,$(findstring fma,$(FMA_M)))
	CFLAGS += -mfma
endif
F16C_M := $(shell grep "f16c " /proc/cpuinfo)
ifneq (,$(findstring f16c,$(F16C_M)))
	CFLAGS += -mf16c
endif
SSE3_M := $(shell grep "sse3 " /proc/cpuinfo)
ifneq (,$(findstring sse3,$(SSE3_M)))
	CFLAGS += -msse3
endif

# amd64 and arm64 only
ifeq ($(UNAME_M),amd64)
	CFLAGS += -mavx -mavx2 -mfma -mf16c
endif

ifneq ($(filter armv8%,$(UNAME_M)),)
	# Raspberry Pi 4
	CFLAGS += -mfp16-format=ieee -mno-unaligned-access
endif

default: libwhisper.so

libwhisper.so: whisper.cpp/ggml.o whisper.cpp/whisper.cpp
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)
