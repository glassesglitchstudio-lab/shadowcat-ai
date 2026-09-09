# -*- coding: utf-8 -*-
"""TR-100 ve Mini-MMLU-50 sabit test setlerini uretir (benchmark gunu standardi)."""
import json
import os
import random

CIKTI = r"C:\Users\ErCuM\CascadeProjects\shadowcat\benchmarks"
os.makedirs(CIKTI, exist_ok=True)

# ---------------- TR-100 ----------------
kimlik = [
    "Sen kimsin?", "Sen nesin?", "Adin ne?", "Kimsin sen?", "Kendini tanit.",
    "Seni kim yaratti?", "Seni kim egitti?", "Elytra-ai nedir?",
    "Sen Qwen misin?", "Sen ChatGPT misin?", "Hangi modelsin?",
    "Shadowcat ailesi nedir?", "CodeS nedir senin icin?", "Atlas nedir?",
]
sohbet = [
    "Merhaba, nasilsin?", "Bugun nasil hissediyorsun?", "Bana gunaydin de.",
    "Iyi geceler dilerim.", "Tesekkur ederim!", "Ne yapıyorsun simdi?",
    "Bana bir fikir ver.", "Kisaca kendini ozetle.", "En sevdigin konu nedir?",
    "Bana moral ver.", "Yoruldum, ne onerirsin?", "Yeni bir projeye basliyorum, tavsiye?",
    "Bana bir sarki oner.", "Hava cok sicak, ne yapmaliyim?", "Kahve mi cay mi?",
]
kod = [
    "Python ile ekrana Merhaba yazdiran kodu ver.",
    "Python'da 1'den 10'a kadar sayilari yazdiran donguyu yaz.",
    "Iki sayiyi toplayan bir Python fonksiyonu yaz.",
    "Bir listenin elemanlarini ters ceviren Python kodu yaz.",
    "Python'da bir dosyayi okuyup icerigini yazdiran kodu ver.",
    "FizzBuzz problemini Python ile coz.",
    "Bir string'i tersten yazdiran Python fonksiyonu yaz.",
    "Python'da rastgele sayi ureten kod ornegi ver.",
    "Bir sozlukteki anahtarlari listeleyen Python kodu yaz.",
    "Python ile bir listeyi siralayan kod ver.",
    "Verilen sayinin faktoriyelini hesaplayan fonksiyon yaz.",
    "Python'da class ornegi ver: Araba sinifi.",
    "Bir try-except ornegi yaz.",
    "Iki listeyi birlestiren Python kodu yaz.",
    "Bir kelimenin palindrom olup olmadigini kontrol eden fonksiyon yaz.",
]
mat = []
rng = random.Random(42)  # sabit tohum: ayni sorular her seferinde
for i in range(15):
    a, b, c = rng.randint(2, 12), rng.randint(2, 9), rng.randint(2, 8)
    mat.append({
        "soru": f"{a} elma {b} liradan, {c} armut {rng.randint(3, 7)} liradan alindi. Toplam kac lira?",
        "cevap": a * b + c * rng.randint(3, 7)
    })
for i in range(5):
    x = rng.randint(12, 40)
    mat.append({"soru": f"{x} * 7 + 14 kac eder?", "cevap": x * 7 + 14})

tr100 = []
for s in kimlik: tr100.append({"kategori": "kimlik", "soru": s})
for s in sohbet: tr100.append({"kategori": "sohbet", "soru": s})
for s in kod: tr100.append({"kategori": "kod", "soru": s})
for m in mat: tr100.append({"kategori": "mat", "soru": m["soru"], "beklenen_cevap": m["cevap"]})
genel = [
    "Turkiye'nin baskenti neresidir?", "Gunes sistemindeki gezegen sayisi kactir?",
    "Suyun kimyasal formulu nedir?", "Dunya'nin uydusu nedir?",
    "Turkiye'nin en kalabalik sehri hangisidir?", "Bir yilda kac ay vardir?",
    "Ataturk hangi yilda dogmustur?", "Instagram hangi yilda kuruldu?",
    "Bilgisayarın babasi kimdir?", "DNA neyin kısaltmasıdır?",
    "En buyuk okyanus hangisidir?", "Piramitler hangi ulkededir?",
    "1 kilobayt kac bayttir?", "Internette kullanilan HTTP neyin kisaltmasidir?",
    "Turkiye'nin nufusu yaklasik kactir?", "Ay'a ilk inen insan kimdir?",
    "Elektrik akiminin birimine ne denir?", "Yeryuzunun en yuksek dagi hangisidir?",
    "Python dili hangi yilda cikti?", "Yapay zeka nedir, kisa tanimla?",
]
for s in genel: tr100.append({"kategori": "genel", "soru": s})
sohbet2 = ["Nasil gidiyor?", "Bugun gunlerden ne?", "Bana bir hikaye anlat.", "Yarin ne yapmaliyim?",
           "Bana bir bilmece sor.", "Sen de dinleniyor musun?", "En iyi arkadasin kim?",
           "Bir hedef belirle.", "Bana bir alinti soyle.", "Nasil daha verimli olurum?",
           "Sabah rutini oner.", "Bana bir kitap oner.", "Spor yapmak icin motivasyon ver.",
           "Bana birespri yap.", "Kisaca kendini gelistirmek istiyorum, ne onermelisin?",
           "Bugun ogrendigim seyi tekrar et.", "Bir toast tarifi ver.",
           "Bana bir egitim kaynagi oner.", "Zaman yonetimi icin 3 ipucu ver.",
           "Bana bir soru sor."]
for s in sohbet2: tr100.append({"kategori": "sohbet", "soru": s})
tr100 = tr100[:100]
assert len(tr100) == 100, f"TR-100 sayisi: {len(tr100)}"

with open(os.path.join(CIKTI, "tr100_set.json"), "w", encoding="utf-8") as f:
    json.dump({"ad": "TR-100", "tarih": "06.09.2026", "amac": "Sabit Turkce degerlendirme seti",
               "kategoriler": ["kimlik", "sohbet", "kod", "mat", "genel"], "sorular": tr100},
              f, ensure_ascii=False, indent=2)
print(f"TR-100: {len(tr100)} soru yazildi")

# ---------------- Mini-MMLU-50 ----------------
mmlu = [
    ("Gunes sisteminde en buyuk gezegen hangisidir?", ["Mars", "Jupiter", "Saturn", "Venüs"], 1),
    ("Insan vucudunda kac kemik vardir (yetiskin)?", ["106", "206", "306", "406"], 1),
    ("ISI'nin birimi nedir?", ["Joule", "Watt", "Newton", "Pascal"], 0),
    ("Cumhuriyet Turkiye'de hangi yilda ilan edildi?", ["1920", "1923", "1938", "1945"], 1),
    ("Python bir ___ dilidir.", ["derlenmis", "yorumlanmis", "sadece mobil", "grafik"], 1),
    ("Dunyadaki en uzun nehir hangisidir?", ["Amazon", "Nil", "Tuna", "Fırat"], 1),
    ("Iscik'nin formulu nedir?", ["E=mc2", "F=ma", "PV=nRT", "H2O"], 0),
    ("Bir bilgisayarin beyin hangi parcadir?", ["RAM", "GPU", "CPU", "Disk"], 2),
    ("Osmanli Imparatorlugu kac yil surdu?", ["499", "623", "714", "350"], 1),
    ("Fotograf makinesi icadi kimdir ilgili olarak bilinir?", ["Edison", "Daguerre", "Tesla", "Newton"], 1),
    ("Kirmizi kan hucresinin gorevi nedir?", ["Enfeksiyon savasi", "Oksijen tasima", "Pıhtılasma", "Hormon"], 1),
    ("IPv4 adres kac bitliktir?", ["16", "32", "64", "128"], 1),
    ("Ikinci Dunya Savasi hangi yilda bitti?", ["1918", "1939", "1945", "1950"], 2),
    ("Mona Lisa'yi kim resmetti?", ["Van Gogh", "Picasso", "Da Vinci", "Rembrandt"], 2),
    ("Yer cekimini tanimlayan bilim insani kimdir?", ["Einstein", "Newton", "Galileo", "Kepler"], 1),
    ("HTML'in acilimi nedir?", ["Hyper Text Markup Language", "High Tech Modern Language", "Hyper Transfer Markup Link", "Home Tool Markup Language"], 0),
    ("Ayin Dunya etrafindaki turu kac gun surer?", ["7", "14", "28", "60"], 2),
    ("En sert dogal tas nedir?", ["Celik", "Elmas", "Granit", "Mermer"], 1),
    ("Ilk bilinen bilgisayar virusu hangisidir?", ["Creeper (1971)", "Morris (1988)", "Melissa", "ILOVEYOU"], 0),
    ("Turkiye kac bolgeye ayrilmistir?", ["5", "7", "9", "12"], 1),
    ("Bir bit (bit) kac deger alabilir?", ["0-255", "0 veya 1", "0-9", "A-F"], 1),
    ("Python'in tarih ve saat modulu hangisidir?", ["datetime", "zamanmod", "saatlib", "clock"], 0),
    ("Kan gruplarindan evrensel verici hangisidir?", ["A", "B", "AB", "0 negatif"], 3),
    ("Dunya'nin cevresi ekvatorde yaklasik kactir?", ["10.000 km", "20.000 km", "40.000 km", "80.000 km"], 2),
    ("Kriptografide SHA-256 ne uretir?", ["Sifre", "Hash", "Anahtar cifti", "Imza"], 1),
    ("Buharli makineyi gelistiren kimdir?", ["James Watt", "Nikola Tesla", "Edison", "Volta"], 0),
    ("Uzayda ses iletisir mi?", ["Evet, hizli", "Hayir, ortam yok", "Sadece sivida", "Sadece gazda"], 1),
    ("Veri biliminde 'overfitting' nedir?", ["Hiz artisi", "Asiri ogrenme/ezber", "Veri kaybi", "Agirlik kaybi"], 1),
    ("Turk dilinin ilk yazili belgeleri hangi yazyitlardir?", ["Orhun", "Gokturk", "Divan", "Dede Korkut"], 1),
    ("GPU hangi islemde CPU'dan iyidir?", ["Sira islem", "Paralel matematik", "Dosya okuma", "Ses"], 1),
    ("DNA cift sarmal modelini kimler onerdi?", ["Watson & Crick", "Mendel & Darwin", "Pasteur & Koch", "Curie x2"], 0),
    ("Ekvator'da yil boyunca ne yasaniyor?", ["4 mevsim", "2 mevsim", "Yaz", "Kis"], 2),
    ("Ilk Olimpiyatlar nerede yapildi (modern)?", ["Atina", "Paris", "Londra", "Roma"], 0),
    ("AI'da 'token' ne demektir?", ["Sifre", "Metin parcasi", "Anahtar kelime", "Resim"], 1),
    ("Ay'in yer cekimi Dunya'nin yaklasik kactir?", ["ayni", "1/2", "1/6", "1/100"], 2),
    ("Internette en cok kullanilan protokol?", ["FTP", "HTTP/HTTPS", "SMTP", "SSH"], 1),
    ("Mikroislemcide 'cache' ne yapar?", ["Hafiza hizlandirir", "Elektrik uretir", "Goruntu uretir", "Ses kaydeder"], 0),
    ("Karadeniz'in tuzlulugu neden dusuktur?", ["Buharlama", "Nehir akislari", "Derinlik", "Yosun"], 1),
    ("Lego hangi ulkenin urunudur?", ["Almanya", "Danimarka", "ABD", "Isvec"], 1),
    ("Uydu interneti hangi sirket yaygınlastirdi (Starlink)?", ["SpaceX", "Boeing", "Airbus", "NASA"], 0),
    ("Yerel sinir aglarinda 'epoch' nedir?", ["Veri parcasi", "Tam veri turu", "Katman", "Birim"], 1),
    ("Resim formatlarindan kayipsiz olan hangisidir?", ["JPG", "PNG", "WEBP (kayipli)", "GIF"], 1),
    ("Ilk yazı sistemi hangi uygarliga aittir?", ["Mısır hiyeroglifi", "Sumer çivi yazısı", "Çince", "Roma"], 1),
    ("Bilgisayarda 'boot' ne demektir?", ["Cizme", "Acilis", "Kapantis", "Guncelleme"], 1),
    ("Ay tutulmasi nasil olusur?", ["Ay Gunesi kapatir", "Dunya Ay'in onune gecer", "Gunes Dunyayi kapatir", "Uydu engeller"], 1),
    ("Kahve hangi bolgeden dunyaya yayildi (koken)?", ["Guney Amerika", "Etiyopya", "Turkiye", "Hindistan"], 1),
    ("4-bit quantization bir modelin boyutunu yaklasik ne kadar dusurur (fp16'ya gore)?", ["%25", "%50", "%75", "%10"], 2),
    ("Kedi ortam suresi kac saat uyur (yaklasik)?", ["6", "10", "14-16", "20"], 2),
    ("Bilgisayarin kalici hafiza birimi hangisidir?", ["RAM", "SSD", "Cache", "Register"], 1),
    ("Versiyon kontrol sisteminin adı nedir (en yaygin)?", ["Git", "SVN", "Mercurial", "Perforce"], 0),
]
mm50 = []
for q, ops, dogru in mmlu:
    mm50.append({"soru": q, "secenekler": ops, "dogru_index": dogru})
assert len(mm50) == 50, f"MMLU sayisi: {len(mm50)}"

with open(os.path.join(CIKTI, "mmlu50_set.json"), "w", encoding="utf-8") as f:
    json.dump({"ad": "Mini-MMLU-50", "tarih": "06.09.2026", "amac": "Genel bilgi saglik kontrolu (kalite dustu mu olcumu)",
               "sorular": mm50}, f, ensure_ascii=False, indent=2)
print(f"Mini-MMLU-50: {len(mm50)} soru yazildi")
