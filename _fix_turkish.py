from pathlib import Path
p = Path(r"C:\Users\ErCuM\CascadeProjects\shadowcat\model_hub.py")
c = p.read_text(encoding="utf-8")
rep = [
    ("Model dizinini istedigin gibi degistirebilirsin. LM Studio gibi C:, D:, USB tum yollar gecerli.",
     "Model dizinini istediğin gibi değiştirebilirsin. LM Studio gibi C:, D:, USB tüm yollar geçerli."),
    ("GGUF dosyalarinin bulundugu klasor. Bu klasordeki .gguf dosyalari otomatik listelenir.",
     "GGUF dosyalarının bulunduğu klasör. Bu klasördeki .gguf dosyaları otomatik listelenir."),
    ("Studio'ya don", "Studio'ya dön"),
    ("Varsayilana don", "Varsayılana dön"),
    ('>Iptal<', '>İptal<'),
    ('return confirm(\'Varsayilana dizine donmek istedigine emin misin?\')',
     'return confirm(\'Varsayılan dizine dönmek istediğine emin misin?\')'),
    ("Sayfayi yenileyebilir veya Studio'ya donebilirsin.",
     "Sayfayı yenileyebilir veya Studio'ya dönebilirsin."),
    ('"bos olamaz"', '"boş olamaz"'),
    ("Klasor olusturulamadi", "Klasör oluşturulamadı"),
    ("Klasor yok (kaydedince olusturulur)",
     "Klasör yok (kaydedince oluşturulur)"),
    ("Henuz model yok. Hub sekmesinden GGUF indir.",
     "Henüz model yok. Hub sekmesinden GGUF indir."),
    ("Varsayilana donuldu: ", "Varsayılana dönüldü: "),
    ('"models_dir bos olamaz"', '"models_dir boş olamaz"'),
]
n = 0
for o, nw in rep:
    if o in c:
        c = c.replace(o, nw)
        n += 1
        print("OK:", o[:50])
    else:
        print("YOK:", o[:50])
p.write_text(c, encoding="utf-8")
print(f"\nToplam {n} degisiklik yapildi.")
