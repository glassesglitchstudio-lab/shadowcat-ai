# -*- coding: utf-8 -*-
"""Shadowcat GPU benchmark gunu — A1 (matmul TFLOPS) + A2 (bant genisligi)."""
import json
import time
import torch

SONUC_DOSYA = "benchmark_results.json"

def matmul_tflops(dtype, boyut=4096, tur=20):
    a = torch.randn(boyut, boyut, device="cuda", dtype=dtype)
    b = torch.randn(boyut, boyut, device="cuda", dtype=dtype)
    for _ in range(5):  # isinma
        _ = a @ b
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(tur):
        _ = a @ b
    torch.cuda.synchronize()
    sure = (time.perf_counter() - t0) / tur
    flops = 2 * (boyut ** 3) / sure
    del a, b
    torch.cuda.empty_cache()
    return flops / 1e12

def bant_genisligi(megabayt=1024, tur=20):
    cpu_veri = torch.randn(megabayt * 1024 * 1024 // 4)  # float32
    gpu_veri = cpu_veri.cuda()
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(tur):
        _ = cpu_veri.cuda()
    torch.cuda.synchronize()
    h2d = (megabayt / 1024) / ((time.perf_counter() - t0) / tur)

    t0 = time.perf_counter()
    for _ in range(tur):
        _ = gpu_veri.cpu()
    torch.cuda.synchronize()
    d2h = (megabayt / 1024) / ((time.perf_counter() - t0) / tur)

    del cpu_veri, gpu_veri
    torch.cuda.empty_cache()
    return h2d, d2h

def main():
    ad = torch.cuda.get_device_name(0)
    ozellik = torch.cuda.get_device_capability(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {ad} | sm_{ozellik[0]}{ozellik[1]} | {vram:.1f} GB VRAM")

    fp16 = matmul_tflops(torch.float16)
    fp32 = matmul_tflops(torch.float32)
    h2d, d2h = bant_genisligi()

    print(f"A1 Matmul TFLOPS: fp16={fp16:.2f} | fp32={fp32:.2f}")
    print(f"A2 Bant genisligi: H2D={h2d:.2f} GB/s | D2H={d2h:.2f} GB/s")

    kayit = {
        "tarih": time.strftime("%Y-%m-%d %H:%M"),
        "benchmark_gunu": "03.09.2026",
        "gpu": {"ad": ad, "sm": f"sm_{ozellik[0]}{ozellik[1]}", "vram_gb": round(vram, 1),
                "matmul_tflops_fp16": round(fp16, 2), "matmul_tflops_fp32": round(fp32, 2),
                "bant_h2d_gbs": round(h2d, 2), "bant_d2h_gbs": round(d2h, 2)}
    }

    try:
        with open(SONUC_DOSYA, encoding="utf-8") as f:
            mevcut = json.load(f)
    except Exception:
        mevcut = {}
    mevcut.setdefault("oturumlar", []).append(kayit)
    with open(SONUC_DOSYA, "w", encoding="utf-8") as f:
        json.dump(mevcut, f, ensure_ascii=False, indent=2)
    print(f"OK: {SONUC_DOSYA} guncellendi")

if __name__ == "__main__":
    main()
