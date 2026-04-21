import json
import re
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are {avatar_name}, a friendly and encouraging English conversation partner with a {accent} accent.

Your role is to:
1. Have natural, engaging conversations in English on the topic: {topic}
2. Gently correct grammar or vocabulary mistakes when they occur
3. Keep responses concise (2-4 sentences) to maintain conversation flow
4. Ask follow-up questions to keep the conversation going
5. Use natural, everyday English appropriate for the user's level: {level}

{memory_context}

When the user makes a grammar or vocabulary mistake, ALWAYS:
- First respond naturally to what they said
- Then at the END of your message, add a correction section in this EXACT JSON format:
<correction>
{{
  "has_mistake": true,
  "original": "the user's incorrect phrase",
  "corrected": "the correct version",
  "explanation": "Brief explanation in Japanese: [explanation]",
  "mistake_type": "grammar|vocabulary|pronunciation|other",
  "advice_ja": "この表現をより自然・流暢に言うための一言アドバイス（日本語、1文）",
  "useful_phrases": [
    {{"english": "A natural alternative or related useful phrase", "japanese": "日本語訳"}},
    {{"english": "Another related useful phrase", "japanese": "日本語訳"}}
  ]
}}
</correction>

If there are NO mistakes, do NOT include a correction section at all.

Be warm, encouraging, and make the conversation feel natural and fun! Reference what you know about the user naturally when relevant."""

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


def get_system_prompt(avatar_name: str, accent: str, topic: str, level: str, memory_context: str = '') -> str:
    topic_contexts = {
        'free': 'any topic the user wants to discuss',
        'daily_life': 'daily life, routines, and everyday activities',
        'travel': 'travel experiences, destinations, and cultural differences',
        'business': 'business, work, and professional topics',
        'culture': 'culture, traditions, food, and lifestyle',
        'hobby': 'hobbies, interests, sports, and entertainment',
    }
    topic_context = topic_contexts.get(topic, 'any topic')
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


def chat_with_ai(messages: list, avatar_name: str, accent: str, topic: str, level: str, memory_context: str = '') -> dict:
    """
    Send conversation to OpenAI and get response with grammar correction.
    Returns dict with 'response', 'correction' (or None), 'clean_response'
    """
    system_prompt = get_system_prompt(avatar_name, accent, topic, level, memory_context)

    openai_messages = [{'role': 'system', 'content': system_prompt}]
    openai_messages.extend(messages)

    completion = client.chat.completions.create(
        model='gpt-4o',
        messages=openai_messages,
        max_tokens=500,
        temperature=0.8,
    )

    full_response = completion.choices[0].message.content

    # Parse correction if present
    correction = None
    clean_response = full_response

    correction_match = re.search(r'<correction>(.*?)</correction>', full_response, re.DOTALL)
    if correction_match:
        try:
            correction_json = correction_match.group(1).strip()
            correction = json.loads(correction_json)
            # Remove the correction block from the visible response
            clean_response = full_response[:correction_match.start()].strip()
        except (json.JSONDecodeError, KeyError):
            pass

    return {
        'response': full_response,
        'clean_response': clean_response,
        'correction': correction,
    }


def generate_conversation_summary(messages: list) -> dict:
    """Generate a summary and feedback for the completed conversation."""
    conversation_text = '\n'.join([
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
        if m.get('role') in ('user', 'assistant')
    ])

    prompt = f"""Analyze this English conversation and provide feedback in JSON format:

{conversation_text}

Respond with this JSON structure:
{{
  "summary_ja": "会話の簡単な要約（日本語、2-3文）",
  "strong_points_ja": ["良かった点1", "良かった点2"],
  "improvement_areas_ja": ["改善点1", "改善点2"],
  "overall_score": 75,
  "fluency_score": 70,
  "accuracy_score": 80,
  "vocabulary_score": 75,
  "encouragement_ja": "励ましのメッセージ（日本語）"
}}"""

    completion = client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {'role': 'system', 'content': 'You are an expert English teacher. Respond only with valid JSON.'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=600,
        temperature=0.3,
        response_format={'type': 'json_object'},
    )

    try:
        return json.loads(completion.choices[0].message.content)
    except Exception:
        return {
            'summary_ja': '会話が完了しました。',
            'strong_points_ja': ['よく頑張りました！'],
            'improvement_areas_ja': ['継続して練習しましょう'],
            'overall_score': 70,
            'fluency_score': 70,
            'accuracy_score': 70,
            'vocabulary_score': 70,
            'encouragement_ja': '素晴らしい練習でした！続けて頑張りましょう！'
        }


def transcribe_audio(audio_file) -> str:
    """Transcribe audio using OpenAI Whisper."""
    transcript = client.audio.transcriptions.create(
        model='whisper-1',
        file=audio_file,
        language='en',
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
