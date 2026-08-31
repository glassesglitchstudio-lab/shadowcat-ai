# GulmezCetinerMax - Yama Notları (Changelog)

## v1.2.0 (2026-05-17) - "Evolution Update"
### Değişiklikler
- **Base Model:** qwen2.5-coder:14b (değişmedi, stabil)
- **Temperature:** 0.85 → 0.7 (daha tutarlı kod çıktıları)
- **Top_p:** 0.95 → 0.85 (daha odaklı yanıtlar)
- **Repeat Penalty:** 1.05 eklendi (tekrarları önler)
- **Num Predict:** 4096 eklendi (uzun yanıt desteği)
- **Encoding:** ASCII → UTF-8 (Türkçe karakterler artık düzgün çalışıyor)
- **System Prompt:** Kodlama standartları ve davranış kuralları eklendi

### Test Sonuçları
- Kendini tanıtma: Başarılı (Berkay patron referansı, Shadowcat Software)
- Binary Search Tree: Hatısız Python kodu
- Flask REST API: GET/POST endpoint'leri, hata yönetimi dahil

---

## v1.1.0 (2026-05-17) - "System Prompt Update"
### Değişiklikler
- System prompt Türkçe karakterlerden ASCII'ye çevrildi (Ollama uyumluluğu)
- Temperature: 0.0 → 0.85
- Top_p: 0.9 → 0.95
- Num_ctx: 8192 → 16384

---

## v1.0.0 (2026-05-16) - "Initial Release"
### Özellikler
- Base: qwen2.5-coder:14b
- Monolithic AGI mimarisi
- GlassesCat AI entegrasyonu
- CEO Berkay yetkilendirmesi
