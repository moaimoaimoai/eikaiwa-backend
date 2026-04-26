import json
import re
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are {avatar_name}, a warm and friendly English conversation partner with a {accent} accent.

Your role is to:
1. Have natural, engaging conversations in English on the topic: {topic}
2. Keep your conversational replies concise (2-4 sentences) to maintain conversation flow
3. Ask follow-up questions to keep the conversation going
4. Use natural, everyday English appropriate for the user's level: {level}

{memory_context}

━━━ TWO-PART RESPONSE RULES (STRICTLY FOLLOW BOTH) ━━━

PART 1 — YOUR CONVERSATIONAL REPLY:
Write a natural, friendly reply to the CONTENT of what the user said.
**ABSOLUTELY DO NOT mention grammar errors, mistakes, corrections, or suggestions in this reply.**
Respond exactly as a native speaker would respond to another native speaker — ignore how they said it.

PART 2 — CORRECTION BLOCK (MANDATORY after your reply):
You MUST rigorously check every user message for ALL of the following:
- Grammar errors (tense, subject-verb agreement, articles a/an/the, plural/singular, word order, missing words)
- Wrong or awkward prepositions (e.g. "arrive to" → "arrive at/in")
- Unnatural vocabulary or word choice
- Japanese-English (Japlish) patterns (e.g. "I have a travel to Tokyo")
- Wrong collocations (e.g. "make homework" → "do homework")
- Awkward sentence structure a native speaker would never use

If you detect ANY issue (even minor), you MUST append this EXACT JSON block at the END of your message:
<correction>
{{
  "has_mistake": true,
  "original": "the exact phrase or sentence the user wrote that needs improvement",
  "corrected": "the most natural native-speaker version",
  "explanation": "日本語で具体的に説明（何が間違い/不自然で、なぜそうなるか）",
  "mistake_type": "grammar|vocabulary|preposition|collocation|unnatural|word_order|article|other",
  "is_unnatural_only": true or false,
  "advice_ja": "この表現をネイティブらしくするための実践アドバイス（日本語、1〜2文）",
  "level_up": "さらに上級のネイティブ表現（任意。より洗練された言い方があれば提示）",
  "useful_phrases": [
    {{"english": "A natural alternative phrase directly related to what the user tried to say", "japanese": "日本語訳"}},
    {{"english": "Another highly practical related phrase", "japanese": "日本語訳"}},
    {{"english": "A third natural variation or extension", "japanese": "日本語訳"}}
  ]
}}
</correction>

Use "is_unnatural_only": true when grammar is technically acceptable but sounds unnatural. Use false for clear errors.
Only omit the correction block when the user's message is completely correct AND sounds natural to a native speaker.

━━━ COACHING ━━━
Every 2-3 exchanges, when the conversation naturally allows it, add a coaching block AFTER any correction:
<coaching>
{{
  "tip_ja": "この文脈で役立つワンポイントアドバイス（日本語、1文）",
  "useful_phrases": [
    {{"english": "A natural phrase the user could use right now in this conversation", "japanese": "日本語訳"}},
    {{"english": "Another highly practical phrase for this context", "japanese": "日本語訳"}}
  ]
}}
</coaching>

Coaching guidelines:
- Focus on phrases the user could immediately deploy in this EXACT conversation
- Skip coaching on the very first turn or when a correction is already detailed
- Aim for expressions that elevate the user from "textbook English" to "natural native speech"

Be warm and encouraging — make learners feel like confident speakers."""

MEMORY_UPDATE_PROMPT = """Based on this conversation, extract any NEW personal information about the user.
Return a JSON object with ONLY fields that have new/updated information (leave out unchanged fields):

{{
  "interests": "comma-separated list of hobbies/interests mentioned",
  "occupation": "job or field of work if mentioned",
  "personal_facts": "brief notes on personal details (family, location, etc.)",
  "common_mistakes": "brief description of recurring grammar/vocabulary errors"
}}

Conversation:
{conversation}

Current memory:
{current_memory}

Return only JSON. If nothing new was learned, return {{}}.
"""


def get_system_prompt(
    avatar_name: str,
    accent: str,
    topic: str,
    level: str,
    memory_context: str = '',
    daily_topic_label: str = '',
    daily_topic_hint: str = '',
) -> str:
    topic_contexts = {
        'free': 'any topic the user wants to discuss',
        'daily_life': 'daily life, routines, and everyday activities',
        'travel': 'travel experiences, destinations, and cultural differences',
        'business': 'business, work, and professional topics',
        'culture': 'culture, traditions, food, and lifestyle',
        'hobby': 'hobbies, interests, sports, and entertainment',
    }
    topic_context = topic_contexts.get(topic, 'any topic')

    # デイリートピックがある場合はより具体的な文脈を付加する
    if daily_topic_label:
        hint_str = f" ({daily_topic_hint})" if daily_topic_hint else ""
        topic_context = (
            f'the specific scenario: **{daily_topic_label}**{hint_str}. '
            f'Stay focused on this scenario throughout the conversation. '
            f'Start with a situation-appropriate greeting and dive into the scenario naturally.'
        )

    memory_section = f"\n## What you remember about this user:\n{memory_context}" if memory_context else ""
    return SYSTEM_PROMPT.format(
        avatar_name=avatar_name,
        accent=accent,
        topic=topic_context,
        level=level,
        memory_context=memory_section,
    )


def update_user_memory(conversation_messages: list, current_memory) -> dict:
    """会話からユーザーの新しい情報を抽出してメモリを更新する"""
    conversation_text = '\n'.join([
        f"{m['role'].upper()}: {m['content']}"
        for m in conversation_messages
        if m.get('role') == 'user'
    ])
    current = {
        'interests': current_memory.interests,
        'occupation': current_memory.occupation,
        'personal_facts': current_memory.personal_facts,
        'common_mistakes': current_memory.common_mistakes,
    }
    prompt = MEMORY_UPDATE_PROMPT.format(
        conversation=conversation_text,
        current_memory=str(current)
    )
    try:
        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You are a memory extraction assistant. Return only valid JSON.'},
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=300,
            temperature=0.1,
            response_format={'type': 'json_object'},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception:
        return {}


def chat_with_ai(messages: list, avatar_name: str, accent: str, topic: str, level: str, memory_context: str = '', daily_topic_label: str = '', daily_topic_hint: str = '') -> dict:
    """
    Send conversation to OpenAI and get response with grammar correction.
    Returns dict with 'response', 'correction' (or None), 'clean_response'
    """
    system_prompt = get_system_prompt(avatar_name, accent, topic, level, memory_context, daily_topic_label, daily_topic_hint)

    openai_messages = [{'role': 'system', 'content': system_prompt}]
    openai_messages.extend(messages)

    completion = client.chat.completions.create(
        model='gpt-4o-mini',  # コスト・速度優先（gpt-4o比: ~15倍安価、~2倍高速）
        messages=openai_messages,
        max_tokens=500,
        temperature=0.8,
    )

    full_response = completion.choices[0].message.content

    # Parse correction if present
    correction = None
    coaching = None
    clean_response = full_response

    correction_match = re.search(r'<correction>(.*?)</correction>', full_response, re.DOTALL)
    if correction_match:
        try:
            correction_json = correction_match.group(1).strip()
            correction = json.loads(correction_json)
            clean_response = full_response[:correction_match.start()].strip()
        except (json.JSONDecodeError, KeyError):
            pass

    # Parse coaching block (may appear even without a correction)
    coaching_match = re.search(r'<coaching>(.*?)</coaching>', full_response, re.DOTALL)
    if coaching_match:
        try:
            coaching_json = coaching_match.group(1).strip()
            coaching = json.loads(coaching_json)
            # Remove coaching block from visible response
            before_coaching = clean_response[:coaching_match.start()] if correction_match and coaching_match.start() > correction_match.start() else full_response[:coaching_match.start()]
            clean_response = before_coaching.strip()
        except (json.JSONDecodeError, KeyError):
            pass

    return {
        'response': full_response,
        'clean_response': clean_response,
        'correction': correction,
        'coaching': coaching,
    }


def generate_conversation_summary(messages: list, mistake_data: list = None) -> dict:
    """
    Generate a summary and feedback for the completed conversation.
    Scores are computed objectively in Python from concrete metrics.
    AI is only asked to generate qualitative text (summary, feedback, phrases).
    """
    mistake_data = mistake_data or []

    # ── 客観指標の計算（Python で確定的に算出） ──
    user_messages = [m for m in messages if m.get('role') == 'user']
    user_turns = max(len(user_messages), 1)

    # ミス集計
    errors_found = len(mistake_data)
    grammar_errors = sum(1 for m in mistake_data if not m.get('is_unnatural_only', False))
    unnatural_only = errors_found - grammar_errors
    error_rate = errors_found / user_turns  # float

    # 語彙分析
    all_words = []
    for m in user_messages:
        words = re.findall(r"[a-zA-Z']+", m.get('content', '').lower())
        all_words.extend(words)
    total_words = len(all_words)
    unique_words = len(set(all_words))
    avg_words = total_words / user_turns  # float
    # Type-Token Ratio（語彙の多様性）
    ttr = unique_words / max(total_words, 1)

    # ── スコア計算 ──
    # 正確さ: ミス率に基づく (0件→95, 0.5件/turn→70, 1件/turn→45以下)
    accuracy_score = max(45, min(98, int(95 - error_rate * 50)))

    # 語彙: TTR × 発話量の複合指標
    vocabulary_score = max(50, min(95, int(ttr * 60 + min(avg_words, 20) * 1.5 + 30)))

    # 流暢さ: 平均語数に基づく（10語/turn=中級目安）
    fluency_score = max(50, min(95, int(50 + avg_words * 2.5)))

    # 総合: 重み付き平均
    overall_score = max(45, min(98, int(accuracy_score * 0.35 + vocabulary_score * 0.30 + fluency_score * 0.35)))

    # ── 採点根拠（必ず数値型で格納） ──
    score_reasoning = {
        'errors_found': int(errors_found),
        'error_rate_per_turn': round(float(error_rate), 2),
        'accuracy_basis': (
            f"文法ミス {grammar_errors}件・不自然表現 {unnatural_only}件"
            f"（合計 {errors_found}件 / {user_turns}ターン、{error_rate:.1f}件/ターン）"
        ),
        'vocabulary_basis': (
            f"使用語彙 {unique_words}種 / {total_words}語"
            f"（多様性 {ttr:.0%}）、平均 {avg_words:.1f}語/ターン"
        ),
        'fluency_basis': (
            f"平均発話量 {avg_words:.1f}語/ターン"
            f"（目安：10語以上=流暢、15語以上=上級）"
        ),
        'pronunciation_note': (
            "※発音スコアは音声認識の精度に基づく推定値です。"
            "実際の発音評価にはコーチによるレッスンをご検討ください。"
        ),
    }

    # ── AI には定性テキストのみ生成させる ──
    conversation_text = '\n'.join([
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
        if m.get('role') in ('user', 'assistant')
    ])

    prompt = f"""You are an expert English teacher for Japanese learners. Analyze this conversation.

{conversation_text}

Learner stats for context (already scored separately — do NOT output scores):
- Turns: {user_turns}
- Errors: {errors_found} ({grammar_errors} grammar, {unnatural_only} unnatural)
- Error rate: {error_rate:.1f}/turn
- Avg words/turn: {avg_words:.1f}
- Vocabulary diversity: {ttr:.0%}

Provide qualitative feedback in this JSON (Japanese text only, no score fields):
{{
  "summary_ja": "会話の要約（日本語、2-3文）",
  "strong_points_ja": ["具体的な良かった点1", "具体的な良かった点2"],
  "improvement_areas_ja": ["具体的な改善点1（実例を含む）", "具体的な改善点2（実例を含む）"],
  "encouragement_ja": "前向きな励ましのメッセージ（日本語、1-2文）",
  "useful_phrases": [
    {{
      "english": "A phrase actually used or naturally applicable in this conversation",
      "japanese": "日本語訳",
      "context_ja": "どんな場面で使えるか（1文）"
    }},
    {{
      "english": "Another practical phrase for this conversation topic",
      "japanese": "日本語訳",
      "context_ja": "どんな場面で使えるか（1文）"
    }},
    {{
      "english": "A third useful phrase",
      "japanese": "日本語訳",
      "context_ja": "どんな場面で使えるか（1文）"
    }}
  ]
}}"""

    try:
        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You are an expert English teacher for Japanese learners. Respond only with valid JSON.'},
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=800,
            temperature=0.3,
            response_format={'type': 'json_object'},
        )
        ai_result = json.loads(completion.choices[0].message.content)
    except Exception:
        ai_result = {
            'summary_ja': '会話が完了しました。',
            'strong_points_ja': ['よく頑張りました！継続は力です。'],
            'improvement_areas_ja': ['より長い文で表現する練習をしましょう。'],
            'encouragement_ja': '素晴らしい練習でした！続けて頑張りましょう！',
            'useful_phrases': [],
        }

    # 客観スコア + 採点根拠を上書きマージ（AI が変更できないよう最後に代入）
    return {
        **ai_result,
        'overall_score': overall_score,
        'fluency_score': fluency_score,
        'accuracy_score': accuracy_score,
        'vocabulary_score': vocabulary_score,
        'score_reasoning': score_reasoning,
    }


def transcribe_audio(audio_file) -> str:
    """Transcribe audio using OpenAI Whisper.
    prompt パラメータで「そのままの音声を文字起こしする」よう誘導し、
    Whisper が自動補正・改善するのを防ぐ。
    """
    transcript = client.audio.transcriptions.create(
        model='whisper-1',
        file=audio_file,
        language='en',
        prompt=(
            "Transcribe verbatim exactly what is spoken, including any grammatical errors, "
            "unnatural phrasing, or non-native expressions. Do not correct or improve the speech. "
            "This is an English learner practicing conversation."
        ),
    )
    return transcript.text


def text_to_speech(text: str, voice: str = 'nova') -> bytes:
    """Convert text to speech using OpenAI TTS."""
    response = client.audio.speech.create(
        model='tts-1',
        voice=voice,
        input=text,
        response_format='mp3',
    )
    return response.content


def japanese_to_english(japanese_text: str) -> dict:
    """日本語テキストを英語に翻訳し、発音ヒントや代替表現を返す。"""
    prompt = f"""A Japanese English learner wants to say the following in English: "{japanese_text}"

Provide a natural English translation with helpful learning support in this JSON format:
{{
  "english": "The most natural English phrase",
  "pronunciation_hint": "カタカナまたは日本語でのの発音ガイド（例: ハウ キャン アイ ヘルプ ユー？）",
  "alternatives": [
    {{"english": "A slightly different natural phrasing", "note": "どんな場面で使えるか（日本語、短く）"}},
    {{"english": "Another variant if applicable", "note": "どんな場面で使えるか（日本語、短く）"}}
  ],
  "context_note": "この表現をいつ・どんな場面で使うかの一言メモ（日本語）"
}}

Keep the English natural and appropriate for conversation. Return only valid JSON."""

    try:
        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You are a helpful English teacher for Japanese speakers. Return only valid JSON.'},
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=350,
            temperature=0.3,
            response_format={'type': 'json_object'},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception:
        return {
            'english': '',
            'pronunciation_hint': '',
            'alternatives': [],
            'context_note': ''
        }


def transcribe_audio_ja(audio_file) -> str:
    """日本語音声をWhisperで文字起こしする。"""
    transcript = client.audio.transcriptions.create(
        model='whisper-1',
        file=audio_file,
        language='ja',
    )
    return transcript.text
