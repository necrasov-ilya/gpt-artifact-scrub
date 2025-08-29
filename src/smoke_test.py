from normalize import normalize_text

def main():
    raw = "Пример — текста с «ёлочками», ‘кавычками’ и • маркерами.\u00A0\n\t— Пункт 1\n– Пункт 2\n- Пункт 3"
    cleaned, stats = normalize_text(raw)
    print("CLEANED:\n", cleaned)
    print("STATS:", stats)

if __name__ == "__main__":
    main()
