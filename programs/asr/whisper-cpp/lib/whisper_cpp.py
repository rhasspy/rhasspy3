import ctypes
from pathlib import Path
from typing import Iterable, Union

import numpy as np

# Must match struct in whisper.h
class WhisperFullParams(ctypes.Structure):
    _fields_ = [
        ("strategy", ctypes.c_int),
        #
        ("n_max_text_ctx", ctypes.c_int),
        ("n_threads", ctypes.c_int),
        ("offset_ms", ctypes.c_int),
        ("duration_ms", ctypes.c_int),
        #
        ("translate", ctypes.c_bool),
        ("no_context", ctypes.c_bool),
        ("single_segment", ctypes.c_bool),
        ("print_special", ctypes.c_bool),
        ("print_progress", ctypes.c_bool),
        ("print_realtime", ctypes.c_bool),
        ("print_timestamps", ctypes.c_bool),
        #
        ("token_timestamps", ctypes.c_bool),
        ("thold_pt", ctypes.c_float),
        ("thold_ptsum", ctypes.c_float),
        ("max_len", ctypes.c_int),
        ("max_tokens", ctypes.c_int),
        #
        ("speed_up", ctypes.c_bool),
        ("audio_ctx", ctypes.c_int),
        #
        ("prompt_tokens", ctypes.c_void_p),
        ("prompt_n_tokens", ctypes.c_int),
        #
        ("language", ctypes.c_char_p),
        #
        ("suppress_blank", ctypes.c_bool),
        #
        ("temperature_inc", ctypes.c_float),
        ("entropy_thold", ctypes.c_float),
        ("logprob_thold", ctypes.c_float),
        ("no_speech_thold", ctypes.c_float),
        #
        ("greedy", ctypes.c_int * 1),
        ("beam_search", ctypes.c_int * 3),
        #
        ("new_segment_callback", ctypes.c_void_p),
        ("new_segment_callback_user_data", ctypes.c_void_p),
        #
        ("encoder_begin_callback", ctypes.c_void_p),
        ("encoder_begin_callback_user_data", ctypes.c_void_p),
    ]


class WhisperError(Exception):
    pass


class Whisper:
    def __init__(
        self,
        model_path: Union[str, Path],
        libwhisper_path: Union[str, Path] = "libwhisper.so",
        language: str = "en",
    ):
        self.model_path = Path(model_path)
        self.whisper = ctypes.CDLL(str(libwhisper_path))

        # Set return types
        self.whisper.whisper_init_from_file.restype = ctypes.c_void_p
        self.whisper.whisper_full_default_params.restype = WhisperFullParams
        self.whisper.whisper_full_get_segment_text.restype = ctypes.c_char_p

        # initialize whisper.cpp context
        filename_bytes = str(self.model_path.absolute()).encode("utf-8")
        self.ctx = self.whisper.whisper_init_from_file(filename_bytes)

        # get default whisper parameters and adjust as needed
        self.params = self.whisper.whisper_full_default_params()
        self.params.print_realtime = False
        self.params.print_special = False
        self.params.print_progress = False
        self.params.print_timestamps = False
        self.params.language = language.encode("utf-8")

    def transcribe(self, audio_array: np.ndarray) -> Iterable[str]:
        """Transcribe float32 audio in [0, 1] to text."""
        result = self.whisper.whisper_full(
            ctypes.c_void_p(self.ctx),
            self.params,
            audio_array.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            len(audio_array),
        )
        if result != 0:
            raise WhisperError(str(result))

        num_segments = self.whisper.whisper_full_n_segments(ctypes.c_void_p(self.ctx))
        for i in range(num_segments):
            text_bytes = self.whisper.whisper_full_get_segment_text(
                ctypes.c_void_p(self.ctx), i
            )
            yield text_bytes.decode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.whisper.whisper_free(ctypes.c_void_p(self.ctx))
        self.whisper = None
        self.ctx = None
