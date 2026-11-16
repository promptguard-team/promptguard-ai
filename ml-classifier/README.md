# Detekcja Prompt Injection (`xlm-roberta-base`)

Model klasyfikacji binarnej służący do wykrywania ataków typu **Prompt Injection** w zapytaniach użytkowników (obsługuje język polski oraz angielski). Wytrenowany model jest hostowany na Hugging Face:

🔗 **[mkvpczyk/prompt-injection-xlm-roberta](https://huggingface.co/mkvpczyk/prompt-injection-xlm-roberta)**

## Klasy wyjściowe (Etykiety)

* **`LABEL_0` (`0`)** – **SAFE**: bezpieczny, standardowy prompt użytkownika.
* **`LABEL_1` (`1`)** – **ATTACK**: wykryta próba manipulacji lub przejęcia kontroli nad modelem (prompt injection).

## Struktura katalogu `training/`

* `1_data_cleaning.ipynb` – czyszczenie i przygotowanie zbioru danych.
* `2_model_training.ipynb` – trening modelu `xlm-roberta-base` oraz ewaluacja.
* `example_inference.py` – gotowy przykład użycia pobranego modelu w Pythonie.

## Wymagania i uruchomienie przykładu

Wagi modelu (ok. 1,1 GB) pobierają się automatycznie z Hugging Face przy pierwszym uruchomieniu:

```bash
pip install transformers torch
python training/example_inference.py
```

## Wskazówki integracyjne (Backend)

1. **Obcinanie tekstu:** Model był trenowany na sekwencjach do **256 tokenów**. Przy każdym wywołaniu należy przekazywać parametry `truncation=True` oraz `max_length=256`.
2. **Zasoby serwera:** Do działania w trybie inferencji model potrzebuje ok. **1,5–2 GB wolnej pamięci RAM** (lub VRAM w przypadku GPU).
