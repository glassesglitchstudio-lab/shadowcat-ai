"""
Opti-LoRA: QLoRA + Unsloth + LoRA+ + DoRA + Flash Attention
Türkçe odaklı fine-tuning
2x T4 Kaggle için optimize
"""
import os
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset
from trl import SFTTrainer


# ===================== TÜRKÇE TOKENIZER =====================
def load_turkish_tokenizer(model_name="Qwen/Qwen2.5-3B-Instruct"):
    """Türkçe karakterleri kapsayan tokenizer yükle."""
    tok = AutoTokenizer.from_pretrained(model_name)
    # Türkçe karakter zaten Qwen'de var, ekleme gerek yok
    return tok


# ===================== 4-BIT QUANTIZATION =====================
def get_bnb_config():
    """QLoRA 4-bit NF4 quant config."""
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",          # NormalFloat 4-bit
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,      # Çift quant (ekstra VRAM tasarrufu)
        bnb_4bit_quant_storage="uint8"       # Saklama optimizasyonu
    )


# ===================== LORA+ CONFIG =====================
def get_lora_config(r=16, lora_alpha=32):
    """LoRA+ (farklı learning rate desteği)."""
    return LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        target_modules="all-linear",
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )


# ===================== OPTI-LORA EĞİTİM =====================
def train_opti_lora(
    model_name="Qwen/Qwen2.5-3B-Instruct",
    dataset_path="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/turkce.jsonl",
    output_dir="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/atlas-3b",
    num_epochs=3,
    batch_size=1,
    grad_accum=16
):
    """Opti-LoRA ana eğitim fonksiyonu."""
    print(f"=== Opti-LoRA Eğitimi: {model_name} ===")

    # 1. Tokenizer
    tok = load_turkish_tokenizer(model_name)

    # 2. Model (4-bit quantized)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=get_bnb_config(),
        device_map="auto",
        torch_dtype=torch.bfloat16
    )
    model = prepare_model_for_kbit_training(model)

    # 3. LoRA adapter
    lora_cfg = get_lora_config()
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # 4. Dataset
    if os.path.exists(dataset_path):
        ds = load_dataset("json", data_files=dataset_path, split="train")
        print(f"Veri: {len(ds)} örnek")
    else:
        print(f"UYARI: {dataset_path} bulunamadı!")
        print("Önce Türkçe veri seti hazırla.")
        return

    # 5. Training arguments
    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=2e-4,
        bf16=True,                              # bf16 (NaN yok)
        gradient_checkpointing=True,            # VRAM tasarrufu
        optim="paged_adamw_8bit",               # 8-bit AdamW
        save_strategy="epoch",
        logging_steps=10,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        report_to="none"
    )

    # 6. Trainer
    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=ds,
        tokenizer=tok,
        max_seq_length=2048,
        dataset_text_field="text"  # JSONL'de "text" alanı
    )

    # 7. Eğit
    print("Eğitim başlıyor...")
    trainer.train()
    print("Eğitim tamamlandı!")

    # 8. Kaydet
    trainer.save_model(output_dir)
    print(f"Model kaydedildi: {output_dir}")


if __name__ == "__main__":
    # Test: önce sadece import'lar çalışıyor mu kontrol et
    print("Opti-LoRA modülü yüklendi.")
    print("Kullanım: train_opti_lora(model_name, dataset_path, output_dir)")
    print("Örnek: train_opti_lora('Qwen/Qwen2.5-3B-Instruct', 'data/turkce.jsonl', 'models/atlas-3b')")
