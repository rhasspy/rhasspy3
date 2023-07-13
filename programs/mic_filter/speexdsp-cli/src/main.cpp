#include <cstdio>
#include <iostream>

#include <speex/speex_preprocess.h>

using namespace std;

void ensureArg(int argc, char *argv[], int argi);
void printUsage(char *argv[]);

int main(int argc, char *argv[]) {

  int sample_rate = 16000;
  size_t frame_size = 320; // 20ms

  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];

    if (arg == "-r" || arg == "--rate") {
      ensureArg(argc, argv, i);
      sample_rate = atoi(argv[++i]);
    } else if (arg == "-s" || arg == "--samples") {
      ensureArg(argc, argv, i);
      frame_size = (size_t)atoi(argv[++i]);
    } else if (arg == "-h" || arg == "--help") {
      printUsage(argv);
      exit(0);
    }
  }

  // Re-open stdin/stdout in binary mode
  // freopen(NULL, "rb", stdin);
  // freopen(NULL, "wb", stdout);

  SpeexPreprocessState *state =
      speex_preprocess_state_init(frame_size, sample_rate);

  int16_t samples[frame_size];

  size_t frames_read = fread(samples, sizeof(int16_t), frame_size, stdin);
  while (frames_read == frame_size) {
    speex_preprocess_run(state, samples);
    fwrite(samples, sizeof(int16_t), frame_size, stdout);
    fflush(stdout);
    frames_read = fread(samples, sizeof(int16_t), frame_size, stdin);
  }

  speex_preprocess_state_destroy(state);
  state = nullptr;

  return 0;
}

void ensureArg(int argc, char *argv[], int argi) {
  if ((argi + 1) >= argc) {
    printUsage(argv);
    exit(0);
  }
}

void printUsage(char *argv[]) {
  cerr << endl;
  cerr << "usage: " << argv[0] << " [options]" << endl;
  cerr << endl;
  cerr << "options:" << endl;
  cerr << "   -h           --help              show this message and exit"
       << endl;
  cerr << "   -r  RATE     --rate     RATE     sample rate (default: 16000)"
       << endl;
  cerr << "   -s  SAMPLES  --samples  SAMPLES  frame size (default: 320)"
       << endl;
  cerr << endl;
}
