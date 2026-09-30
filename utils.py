import re


def clean_text(text: str) -> str:
    """Очистка текста от HTML-тегов, ссылок, смайлов, хэштегов и лишних пробелов.

    @param text: исходный текст
    @return: очищенный текст
    """
    if not isinstance(text, str):
        return ""

    # 1. Убираем ссылки (http, https, www)
    text = re.sub(r'http\S+|www\.\S+', ' ', text)

    # 2. Убираем HTML-теги
    text = re.sub(r'<.*?>', ' ', text)

    # 3. Убираем эмодзи (комплексный паттерн Unicode)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)

    # 4. Убираем хэштеги
    text = re.sub(r'#\S+', ' ', text)

    # 5. Убираем простые текстовые смайлики (например, :), :D, ;-))
    text = re.sub(r'[:;=8][\-~]?[)D\(Pp]', ' ', text)

    # 6. Убираем множественные пробелы и обрезаем края
    text = re.sub(r'\s+', ' ', text).strip()

    return text