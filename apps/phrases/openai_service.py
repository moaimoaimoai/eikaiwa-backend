"""
AIウォームアップフレーズ生成サービス
ユーザーのレベル・興味・過去のミスを考慮して毎回異なるフレーズを生成する
"""
import json
import hashlib
from openai import OpenAI

client = OpenAI()


def generate_warmup_phrases(
    level: str,
    memory_context: str = '',
    excluded_hashes: list[str] | None = None,
    count: int = 10,
) -> list[dict]:
    """
    OpenAI GPT-4o-miniを使ってウォームアップフレーズを動的生成する。

    Args:
        level: 'beginner' | 'intermediate' | 'advanced'
        memory_context: ユーザーの記憶コンテキスト（会話履歴・興味など）
        excluded_hashes: 直近で表示したフレーズのハッシュリスト（重複防止）
        count: 生成するフレーズ数

    Returns:
        List of phrase dicts with keys: english, japanese, pronunciation_hint,
        example_context, category_label, hash
    """
    excluded_hashes = excluded_hashes or []

    level_desc = {
        'beginner': '中学〜高校レベル。短い文で日常会話に使える表現',
        'intermediate': '日常会話から少し踏み込んだ自然な表現',
        'advanced': 'ネイティブが使うイディオム・ビジネス表現・微妙なニュアンス',
    }.get(level, '日常会話')

    user_context_block = ''
    if memory_context:
        user_context_block = f'\n\nユーザー情報:\n{memory_context}'

    system_prompt = f"""あなたは英会話学習コンテンツのエキスパートです。
以下の条件で英語フレーズを {count} 個生成してください。

レベル: {level_desc}
条件:
- 毎回テーマ（日常・旅行・感情表現・ビジネス・ユーモアなど）をランダムに選んで多様性を出す
- 実際の会話で使いやすい自然な表現にする
- 過去に表示したフレーズと異なる新鮮な表現にする{user_context_block}

必ずJSON配列で返してください。他の文字は含めないこと。
各要素のフォーマット:
{{
  "english": "英語フレーズ",
  "japanese": "日本語訳",
  "pronunciation_hint": "発音のポイント（カタカナ・リズム・注意点など）",
  "example_context": "どんな場面で使うかの説明（日本語・1文）",
  "category_label": "カテゴリ（例: 日常会話・感情表現・ビジネスなど）"
}}"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'{count}個のフレーズを生成してください。'},
        ],
        response_format={'type': 'json_object'},
        temperature=1.0,  # 多様性のため高め
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    # JSONオブジェクトの場合、配列を取り出す
    if isinstance(data, dict):
        phrases = data.get('phrases', data.get('items', list(data.values())[0] if data else []))
    else:
        phrases = data

    # ハッシュを付与し、除外リストにないものだけ返す
    result = []
    for p in phrases:
        h = hashlib.md5(p.get('english', '').lower().strip().encode()).hexdigest()[:12]
        if h not in excluded_hashes:
            p['hash'] = h
            result.append(p)

    return result[:count]


def generate_ai_words(
    level: str,
    memory_context: str = '',
    excluded_hashes: list[str] | None = None,
    count: int = 10,
) -> list[dict]:
    """
    OpenAI GPT-4o-miniを使ってAI単語カードを動的生成する。

    Args:
        level: 'beginner' | 'intermediate' | 'advanced'
        memory_context: ユーザーの記憶コンテキスト
        excluded_hashes: 直近で表示した単語のハッシュリスト（重複防止）
        count: 生成する単語数

    Returns:
        List of word dicts with keys: word, reading, definition_ja, part_of_speech,
        example_sentence, example_sentence_ja, memory_hook, hash
    """
    excluded_hashes = excluded_hashes or []

    level_desc = {
        'beginner': '中学〜高校レベルの基本単語・頻出表現',
        'intermediate': '日常会話でよく使う中級単語・コロケーション',
        'advanced': 'ネイティブが使う上級語彙・ニュアンスが重要な単語',
    }.get(level, '日常会話')

    user_context_block = ''
    if memory_context:
        user_context_block = f'\n\nユーザー情報:\n{memory_context}'

    system_prompt = f"""あなたは英語語彙学習コンテンツのエキスパートです。
以下の条件で英単語・表現を {count} 個生成してください。

レベル: {level_desc}
条件:
- 毎回テーマ（ビジネス・感情・自然・テクノロジー・日常など）をランダムに選んで多様性を出す
- 実際の会話・文章で使いやすい自然な単語にする
- 過去に表示した単語と異なる新鮮な語彙にする{user_context_block}

必ずJSON配列で返してください。他の文字は含めないこと。
各要素のフォーマット:
{{
  "word": "英単語または短い表現",
  "reading": "カタカナ読み（例: グレイトフル）",
  "definition_ja": "日本語の意味・定義（簡潔に）",
  "part_of_speech": "品詞（例: 名詞・動詞・形容詞・副詞・熟語）",
  "example_sentence": "自然な英語の例文（1文）",
  "example_sentence_ja": "例文の日本語訳",
  "memory_hook": "覚え方のコツまたは語源メモ（1〜2文、日本語）"
}}"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'{count}個の単語を生成してください。'},
        ],
        response_format={'type': 'json_object'},
        temperature=1.0,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    if isinstance(data, dict):
        words = data.get('words', data.get('items', list(data.values())[0] if data else []))
    else:
        words = data

    result = []
    for w in words:
        h = hashlib.md5(w.get('word', '').lower().strip().encode()).hexdigest()[:12]
        if h not in excluded_hashes:
            w['hash'] = h
            result.append(w)

    return result[:count]
