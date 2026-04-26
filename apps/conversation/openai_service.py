import json
import re
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are {avatar_name}, a warm but rigorous English conversation coach with a {accent} accent.

Your role is to:
1. Have natural, engaging conversations in English on the topic: {topic}
2. **Rigorously check every user message** for ALL types of errors and unnatural phrasing
3. Keep your conversational replies concise (2-4 sentences) to maintain conversation flow
4. Ask follow-up questions to keep the conversation going
5. Use natural, everyday English appropriate for the user's level: {level}

{memory_context}

━━━ CORRECTION POLICY (STRICT MODE) ━━━
You are a strict but supportive English teacher. You MUST flag and correct ANY of the following — even when the meaning is clear:

- Grammar errors (tense, subject-verb agreement, articles a/an/the, plural/singular, word order, missing words)
- Wrong or awkward prepositions (e.g. "arrive to" → "arrive at/in")
- Unnatural vocabulary or word choice (e.g. "I am fine" → "I'm doing well" / "Not bad!")
- Japanese-English (Japlish) patterns (e.g. "How about you think?" / "I have a travel to Tokyo")
- Overuse of simple structures when a more natural alternative exists (e.g. "It is very good" → "It's really great!" / "I'm loving it!")
- Missing or wrong collocation (e.g. "make homework" → "do homework", "strong rain" → "heavy rain")
- Redundant or missing contractions in casual speech
- Awkward sentence structure that a native speaker would never say

Even if a sentence is technically understandable, if it sounds unnatural to a native speaker, ALWAYS flag it.

When you detect ANY issue, respond naturally first, then append this EXACT JSON block at the END of your message:
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

Use "is_unnatural_only": true when the grammar is technically acceptable but sounds awkward/non-native. Use false when there is a clear grammatical error.

If the user's message is genuinely correct AND sounds natural to a native speaker, do NOT include a correction block. This should be relatively rare for learners — look carefully before deciding there is nothing to correct.

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

Be warm and encouraging — make learners feel supported, not embarrassed. Frame corrections as "level-ups", not failures."""

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
  "encouragement_ja": "励ましのメッセージ（日本語）",
  "useful_phrases": [
    {{
      "english": "A natural English phrase that came up or would have been useful in this conversation",
      "japanese": "日本語訳",
      "context_ja": "どんな場面で使えるか（1文、日本語）"
    }},
    {{
      "english": "Another useful phrase from this conversation's topic",
      "japanese": "日本語訳",
      "context_ja": "どんな場面で使えるか（1文、日本語）"
    }},
    {{
      "english": "A third useful phrase",
      "japanese": "日本語訳",
      "context_ja": "どんな場面で使えるか（1文、日本語）"
    }}
  ]
}}

For useful_phrases: pick 3 phrases that were actually used in the conversation OR would have been natural to use given the topic. Focus on practical, conversational phrases the learner can immediately reuse."""

    completion = client.chat.completions.create(
        model='gpt-4o-mini',  # サマリーはJSON出力のみでminiで十分
        messages=[
            {'role': 'system', 'content': 'You are an expert English teacher. Respond only with valid JSON.'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=800,
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
            'encouragement_ja': '素晴らしい練習でした！続けて頑張りましょう！',
            'useful_phrases': [],
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
