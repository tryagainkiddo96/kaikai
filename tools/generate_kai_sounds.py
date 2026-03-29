#!/usr/bin/env python3
"""Generate ambient sound WAV files for Kai companion."""
import math
import struct
import os
import sys

SAMPLE_RATE = 22050

def make_wav(samples, path):
    clipped = [max(-1.0, min(1.0, s)) for s in samples]
    pcm = struct.pack(f"<{len(clipped)}h", *[int(s * 32767) for s in clipped])
    data_size = len(pcm)
    header = struct.pack("<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, SAMPLE_RATE,
        SAMPLE_RATE * 2, 2, 16,
        b"data", data_size)
    with open(path, "wb") as f:
        f.write(header + pcm)
    print(f"  Generated: {path} ({len(samples)} samples)")

def gen_sniff(path):
    samples = []
    for i in range(int(SAMPLE_RATE * 0.3)):
        t = i / SAMPLE_RATE
        env = 0.0
        if 0.05 < t < 0.12:
            env = math.sin((t - 0.05) / 0.07 * math.pi) * 0.3
        elif 0.15 < t < 0.22:
            env = math.sin((t - 0.15) / 0.07 * math.pi) * 0.25
        noise = (hash(i * 7919) % 1000 - 500) / 500.0
        samples.append(noise * env)
    make_wav(samples, path)

def gen_wag(path):
    samples = []
    for i in range(int(SAMPLE_RATE * 0.15)):
        t = i / SAMPLE_RATE
        freq = 60 + 40 * (1 - t / 0.15)
        val = math.sin(2 * math.pi * freq * t) * 0.4 * (1 - t / 0.15)
        samples.append(val)
    make_wav(samples, path)

def gen_huff(path):
    samples = []
    for i in range(int(SAMPLE_RATE * 0.2)):
        t = i / SAMPLE_RATE
        env = math.sin(t / 0.2 * math.pi) * 0.35
        noise = (hash(i * 3571) % 1000 - 500) / 500.0
        val = noise * env * (0.5 + 0.5 * math.sin(2 * math.pi * 200 * t))
        samples.append(val)
    make_wav(samples, path)

def gen_paw(path):
    samples = []
    for i in range(int(SAMPLE_RATE * 0.06)):
        t = i / SAMPLE_RATE
        env = (1 - t / 0.06) ** 3
        val = math.sin(2 * math.pi * 120 * t) * 0.2 * env
        samples.append(val)
    make_wav(samples, path)

def gen_sigh(path):
    samples = []
    for i in range(int(SAMPLE_RATE * 0.6)):
        t = i / SAMPLE_RATE
        env = math.sin(t / 0.6 * math.pi) * 0.2
        noise = (hash(i * 2311) % 1000 - 500) / 500.0
        val = noise * env * (0.3 + 0.7 * math.sin(2 * math.pi * 150 * t))
        samples.append(val)
    make_wav(samples, path)

def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "kai_companion/assets/kai/audio"
    os.makedirs(out_dir, exist_ok=True)
    print(f"[KAI_SOUNDS] Generating ambient sounds to {out_dir}/")
    gen_sniff(os.path.join(out_dir, "kai_sniff.wav"))
    gen_wag(os.path.join(out_dir, "kai_wag.wav"))
    gen_huff(os.path.join(out_dir, "kai_huff.wav"))
    gen_paw(os.path.join(out_dir, "kai_paw.wav"))
    gen_sigh(os.path.join(out_dir, "kai_sigh.wav"))
    print("[KAI_SOUNDS] Done!")

if __name__ == "__main__":
    main()
