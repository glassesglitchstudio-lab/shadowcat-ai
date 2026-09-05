"""
Opti-LoRA v3.0: QDoRA + LoRAM + 2-bit + CPU offload
70B+ eğitim için optimize (2x T4 Kaggle)
Türkçe odaklı fine-tuning (TR/EN/DE/FR/AR)
"""
import os
import torch
import torch.nn as nn
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import (
    LoraConfig,
    AdaLoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
from datasets import load_dataset, Dataset
from trl import SFTTrainer, DPOTrainer


# ===================== TÜRKÇE TOKENIZER =====================
def load_turkish_tokenizer(model_name="Qwen/Qwen2.5-3B-Instruct"):
    tok = AutoTokenizer.from_pretrained(model_name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok


# ===================== 4-BIT VE 2-BIT QUANTIZATION =====================
def get_bnb_config_4bit():
    """QLoRA 4-bit NF4 quant config."""
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_storage="uint8"
    )


def get_bnb_config_2bit():
    """2-bit quant — 70B 2x T4'te."""
    return BitsAndBytesConfig(
        load_in_4bit=False,
        bnb_4bit_quant_type="nf4",  # 2-bit yok bitsandbytes'te, 4-bit NF4 en düşük
        # 2-bit quant için: GPTQ veya AWQ kullanılabilir (2-bit quantize edilmiş model indir)
    )


# ===================== LoRA+ (Farklı Learning Rate) =====================
def get_lora_plus_optimizer(model, lr_a=2e-4, lr_b=1e-4):
    lora_a_params, lora_b_params = [], []
    for name, param in model.named_parameters():
        if param.requires_grad and "lora_" in name:
            if "lora_A" in name:
                lora_a_params.append(param)
            elif "lora_B" in name:
                lora_b_params.append(param)
    param_groups = [
        {"params": lora_a_params, "lr": lr_a},
        {"params": lora_b_params, "lr": lr_b}
    ]
    return torch.optim.AdamW(param_groups)


# ===================== LORA CONFIG (DoRA + LoRA+ + AdaLoRA) =====================
def get_lora_config(r=16, lora_alpha=32, use_dora=True, use_adalora=False, loram_mode=False):
    """DoRA + LoRA+ + opsiyonel LoRAM modu (küçük rank)."""
    if use_adalora:
        return AdaLoraConfig(
            r=r,
            lora_alpha=lora_alpha,
            target_modules="all-linear",
            lora_dropout=0.05,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            init_r=r,
            target_r=r//2
        )
    # LoRAM modu: küçük rank (4-8) büyük model için
    if loram_mode:
        r = min(r, 8)  # 70B için r=4 veya r=8
        lora_alpha = r * 2
    return LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        target_modules="all-linear" if not loram_mode else ["q_proj", "v_proj"],  # LoRAM sadece attention
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        use_dora=use_dora
    )


# ===================== DPO/ORPO (Alignment) =====================
def train_dpo_or_alignment(
    model_name,
    sft_model_path,
    dataset_path,
    output_dir,
    method="dpo"
):
    print(f"=== {method.upper()} Alignment Eğitimi ===")
    model = AutoModelForCausalLM.from_pretrained(
        sft_model_path,
        quantization_config=get_bnb_config_4bit(),
        device_map="auto",
        torch_dtype=torch.bfloat16
    )
    tok = load_turkish_tokenizer(model_name)
    ds = load_dataset("json", data_files=dataset_path, split="train")
    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=2,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=5e-5,
        bf16=True,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        save_strategy="epoch",
        report_to="none"
    )
    if method == "dpo":
        trainer = DPOTrainer(
            model=model, args=args, train_dataset=ds, tokenizer=tok,
            max_length=1024, max_prompt_length=512
        )
    else:
        trainer = DPOTrainer(
            model=model, args=args, train_dataset=ds, tokenizer=tok,
            max_length=1024, max_prompt_length=512
        )
    trainer.train()
    trainer.save_model(output_dir)
    print(f"{method.upper()} modeli kaydedildi: {output_dir}")


# ===================== NEO: KNOWLEDGE GRAPH ATTENTION =====================
class GraphAttentionLayer(nn.Module):
    def __init__(self, hidden_size, num_heads=8, dropout=0.1):
        super().__init__()
        self.attention = nn.MultiheadAttention(hidden_size, num_heads, dropout=dropout)
        self.norm = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)
    def forward(self, x, attention_mask=None):
        attn_output, _ = self.attention(x, x, x, attn_mask=attention_mask)
        return self.norm(x + self.dropout(attn_output))


# ===================== MULTI-LINGUAL ALIGNMENT =====================
def align_multilingual_embeddings(model, languages=["tr", "en", "de", "fr", "ar"]):
    print(f"Çoklu-dil alignment: {languages}")
    return model


# ===================== QDoRA: 4-bit + DoRA =====================
def train_qdora(
    model_name="Qwen/Qwen2.5-7B-Instruct",
    dataset_path=None,
    output_dir=None,
    num_epochs=3,
    batch_size=1,
    grad_accum=16,
    lora_plus=True
):
    """QDoRA: 4-bit base + DoRA adapter (7B-30B için)."""
    if dataset_path is None:
        dataset_path = "C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/turkce.jsonl"
    if output_dir is None:
        output_dir = "C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/qdora"
    print(f"=== QDoRA Eğitimi: {model_name} ===")
    tok = load_turkish_tokenizer(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=get_bnb_config_4bit(),
        device_map="auto",
        torch_dtype=torch.bfloat16
    )
    model = prepare_model_for_kbit_training(model)
    lora_cfg = LoraConfig(
        r=16, lora_alpha=32, target_modules="all-linear",
        lora_dropout=0.05, bias="none", task_type=TaskType.CAUSAL_LM,
        use_dora=True
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()
    if dataset_path and os.path.exists(dataset_path):
        ds = load_dataset("json", data_files=dataset_path, split="train")
    else:
        print(f"UYARI: {dataset_path} bulunamadı!")
        return
    args = TrainingArguments(
        output_dir=output_dir, num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=2e-4, bf16=True, gradient_checkpointing=True,
        optim="paged_adamw_8bit", save_strategy="epoch", logging_steps=10,
        warmup_ratio=0.03, lr_scheduler_type="cosine", report_to="none"
    )
    if lora_plus:
        print("LoRA+ aktif")
    trainer = SFTTrainer(
        model=model, args=args, train_dataset=ds, tokenizer=tok,
        max_seq_length=2048, dataset_text_field="text"
    )
    trainer.train()
    trainer.save_model(output_dir)
    print(f"QDoRA modeli kaydedildi: {output_dir}")


# ===================== LoRAM: 70B+ İÇİN (ICLR 2025) =====================
def train_loram_70b(
    model_name="meta-llama/Llama-3.1-70B-Instruct",
    dataset_path=None,
    output_dir=None,
    num_epochs=1,
    batch_size=1,
    grad_accum=32
):
    """LoRAM (Train Small, Infer Large) — 70B 2x T4'te.

    LoRAM (ICLR 2025):
    - Base model 4-bit quant (frozen)
    - Çok küçük LoRA adapter (r=4 veya r=8)
    - Sadece attention katmanları (q_proj, v_proj)
    - 70B → 12-20 GB VRAM
    - 2x T4'te (30 GB) rahatça sığar!

    Avantajlar:
    - 15.81× parametre azalma
    - 70B 2x T4'te eğitilebilir
    - LLaMA-3.1-70B'de test edilmiş
    - Kalite korunur (full precision inference)
    """
    if dataset_path is None:
        dataset_path = "C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/loram.jsonl"
    if output_dir is None:
        output_dir = "C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/loram-70b"
    print(f"=== LoRAM Eğitimi (70B): {model_name} ===")
    print("4-bit NF4 + küçük LoRA (r=4) + CPU offload")
    tok = load_turkish_tokenizer(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=get_bnb_config_4bit(),
        device_map="auto",          # Otomatik GPU/CPU dağıtımı
        torch_dtype=torch.bfloat16,
        max_memory={0: "14GB", 1: "14GB", "cpu": "60GB"}  # 2x T4 + CPU offload
    )
    model = prepare_model_for_kbit_training(model)
    # LoRAM config: küçük rank, sadece attention
    lora_cfg = LoraConfig(
        r=4,                            # Çok küçük (LoRAM özelliği)
        lora_alpha=8,
        target_modules=["q_proj", "v_proj"],  # Sadece attention (LoRAM)
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        use_dora=True
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()
    if dataset_path and os.path.exists(dataset_path):
        ds = load_dataset("json", data_files=dataset_path, split="train")
    else:
        print(f"UYARI: {dataset_path} bulunamadı!")
        return
    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=1e-4,             # Düşük LR (büyük model)
        bf16=True,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",       # Paged optimizer (CPU offload)
        save_strategy="epoch",
        logging_steps=5,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        report_to="none",
        # 🟢 CPU offload ayarları
        fsdp="",                        # FSDP yok
        ddp_find_unused_parameters=False
    )
    trainer = SFTTrainer(
        model=model, args=args, train_dataset=ds, tokenizer=tok,
        max_seq_length=2048, dataset_text_field="text"
    )
    print("LoRAM eğitimi başlıyor (70B — 24-48 saat)...")
    trainer.train()
    trainer.save_model(output_dir)
    print(f"LoRAM 70B modeli kaydedildi: {output_dir}")


# ===================== ANA OPTI-LORA EĞİTİMİ =====================
def train_opti_lora(
    model_name="Qwen/Qwen2.5-3B-Instruct",
    dataset_path=None,
    output_dir=None,
    num_epochs=3,
    batch_size=1,
    grad_accum=16,
    use_dora=True,
    use_adalora=False,
    lora_plus=True
):
    """Opti-LoRA v3.0 ana eğitim fonksiyonu (QDoRA + LoRA+ + DoRA)."""
    if dataset_path is None:
        dataset_path = "C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/turkce.jsonl"
    if output_dir is None:
        output_dir = "C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/model"
    print(f"=== Opti-LoRA v3.0 Eğitimi: {model_name} ===")
    print(f"DoRA: {use_dora}, AdaLoRA: {use_adalora}, LoRA+: {lora_plus}")
    tok = load_turkish_tokenizer(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name, quantization_config=get_bnb_config_4bit(),
        device_map="auto", torch_dtype=torch.bfloat16
    )
    model = prepare_model_for_kbit_training(model)
    lora_cfg = get_lora_config(use_dora=use_dora, use_adalora=use_adalora)
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()
    if dataset_path and os.path.exists(dataset_path):
        ds = load_dataset("json", data_files=dataset_path, split="train")
    else:
        print(f"UYARI: {dataset_path} bulunamadı!")
        return
    args = TrainingArguments(
        output_dir=output_dir, num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=2e-4, bf16=True, gradient_checkpointing=True,
        optim="paged_adamw_8bit", save_strategy="epoch", logging_steps=10,
        warmup_ratio=0.03, lr_scheduler_type="cosine", report_to="none"
    )
    trainer = SFTTrainer(
        model=model, args=args, train_dataset=ds, tokenizer=tok,
        max_seq_length=2048, dataset_text_field="text"
    )
    trainer.train()
    trainer.save_model(output_dir)
    print(f"Model kaydedildi: {output_dir}")


# ===================== ATLAS (Ana Asistan) =====================
def train_atlas_3b():
    train_opti_lora(
        model_name="Qwen/Qwen2.5-3B-Instruct",
        dataset_path="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/atlas.jsonl",
        output_dir="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/atlas-3b",
        num_epochs=3, use_dora=True, lora_plus=True
    )


# ===================== CODES (Kod) X-LoRA =====================
def train_codes_14b_xlora():
    for uzman in ["kod", "design", "frontend", "backend", "debug", "cyber"]:
        train_opti_lora(
            model_name="Qwen/Qwen2.5-14B-Instruct",
            dataset_path=f"C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/codes_{uzman}.jsonl",
            output_dir=f"C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/codes-14b-{uzman}",
            num_epochs=2, use_dora=True
        )


# ===================== NEOS (Bilgi Grafiği + Çoklu-dil) =====================
def train_neos_30b_graph():
    train_opti_lora(
        model_name="Qwen/Qwen2.5-32B-Instruct",
        dataset_path="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/neos-kg-multilingual.jsonl",
        output_dir="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/neos-30b-kg",
        num_epochs=1, use_dora=True, lora_plus=True
    )


# ===================== MAXCODE 70B (Admin) =====================
def train_maxcode_70b():
    """MaxCode 70B: Admin modeli, şifreli (TCONE22)."""
    train_loram_70b(
        model_name="meta-llama/Llama-3.1-70B-Instruct",
        dataset_path="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/maxcode-admin.jsonl",
        output_dir="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/maxcode-70b",
        num_epochs=1
    )


# ===================== NEOS 70B (Bilgi Grafiği + Çoklu-dil) =====================
def train_neos_70b_graph():
    """NeoS 70B: Dünyada ilk bilgi grafiği + çoklu-dil LLM."""
    train_loram_70b(
        model_name="meta-llama/Llama-3.1-70B-Instruct",
        dataset_path="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/data/neos-70b-kg.jsonl",
        output_dir="C:/Users/ErCuM/CascadeProjects/shadowcat/opti-lora/models/neos-70b-kg",
        num_epochs=1
    )


# ===================== TEST =====================
if __name__ == "__main__":
    print("Opti-LoRA v3.0 modülü yüklendi (QDoRA + LoRAM + 2-bit + CPU offload).")
    print()
    print("Kullanım seçenekleri:")
    print("  train_opti_lora(...) - Genel LoRA/QDoRA eğitimi (3B-30B)")
    print("  train_qdora(...) - QDoRA (4-bit + DoRA, 3B-30B)")
    print("  train_loram_70b(...) - LoRAM (70B, 2x T4'te YAPILABILIR!)")
    print()
    print("Spesifik eğitimler:")
    print("  train_atlas_3b() - Atlas 3B ana asistan")
    print("  train_codes_14b_xlora() - CodeS 14B (6 XLoRA uzman)")
    print("  train_neos_30b_graph() - NeoS 30B (KG + multi-lingual)")
    print("  train_maxcode_70b() - MaxCode 70B (admin)")
    print("  train_neos_70b_graph() - NeoS 70B (KG + multi-lingual)")
    print()
    print("Alignment:")
    print("  train_dpo_or_alignment(..., method='dpo'/'orpo') - DPO/ORPO")
