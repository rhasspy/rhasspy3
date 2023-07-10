from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, Semaphore
from typing import Dict

from .const import ClientData


@dataclass
class WakeWordState:
    embeddings_ready: Semaphore = field(default_factory=Semaphore)
    embeddings_lock: Lock = field(default_factory=Lock)


@dataclass
class State:
    models_dir: Path

    is_running: bool = True
    clients: Dict[str, ClientData] = field(default_factory=dict)
    clients_lock: Lock = field(default_factory=Lock)

    audio_ready: Semaphore = field(default_factory=Semaphore)
    audio_lock: Lock = field(default_factory=Lock)

    mels_ready: Semaphore = field(default_factory=Semaphore)
    mels_lock: Lock = field(default_factory=Lock)

    wake_words: Dict[str, WakeWordState] = field(default_factory=dict)
