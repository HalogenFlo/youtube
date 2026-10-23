"""Synthesize a batch with one CPU model load in the isolated VieNeu runtime.

Keeps the studio's torch/transformers versions intact. Official SDK API:
https://github.com/pnnbao97/VieNeu-TTS#sdk
"""
from pathlib import Path
import json
import sys


def main():
    from vieneu import Vieneu
    jobs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    model = Vieneu(mode="v3turbo", backend="onnx", precision="fp32")
    for job in jobs:
        audio = model.infer(job["text"], voice=job["voice"])
        model.save(audio, job["wav"])


if __name__ == "__main__":
    main()
