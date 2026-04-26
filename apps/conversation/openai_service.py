import json
import re
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are {avatar_name}, a warm English conversation partner with a {accent} accent.

Your role: Have natural, engaging conversations on the topic: {topic}
- Keep replies concise (2-4 sentences). Ask one follow-up question to keep dialogue flowing.
- Use natural English appropriate for level: {level}
- **CRITICAL: NEVER mention, reference, or hint at any grammar/vocabulary errors in your conversational reply.** All error feedback is handled exclusively through the silent <correction> block below. Your spoken response must read as a completely natural reaction to the CONTENT of what the user said — as if you didn't notice any mistakes at all.

{memory_context}

━━━ SILENT CORRECTION POLICY (ZERO TOLERANCE) ━━━
After writing your conversational reply, silently audit the user's message for ANY of the following. Flag even minor issues — a near-native speaker would notice them:

✗ Grammar: tense errors, subject-verb agreement, articles (a/an/the), plural/singular, word order, missing words
✗ Prepositions: "arrive to" → "arrive at/in", "interested on" → "interested in"
✗ Unnatural vocabulary: "I am fine" → "I'm doing well", "I want to eat" → "I'd love to try"
✗ Japlish: "How about you think?" / "I have a travel" / "It became cold"
✗ Weak collocations: "make homework" → "do homework", "strong rain" → "heavy rain"
✗ Overly stiff/textbook phrasing when natural alternatives exist
✗ Missing contractions in casual speech ("I am" → "I'm" in casual context)
✗ Any phrasing a native speaker would rephrase without thinking

Default assumption: learner messages almost always contain at least one improvable point. Only skip the correction block when the message is genuinely flawless native-level English.

When you detect ANY issue, append this EXACT JSON block at the END of your message (after your conversational reply):
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

"is_unnatural_only": true → grammar technically OK but sounds non-native. false → clear grammatical error.

━━━ COACHING ━━━
Every 2-3 exchanges, append a coaching block AFTER any correction:
<coaching>
{{
  "tip_ja": "この文脈で役立つワンポイントアドバイス（日本語、1文）",
  "useful_phrases": [
    {{"english": "A natural phrase the user could use right now in this conversation", "japanese": "日本語訳"}},
    {{"english": "Another highly practical phrase for this context", "japanese": "日本語訳"}}
  ]
}}
</coaching>
Skip coaching on the first turn or when a correction is already detailed."""

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
        max_tokens=450,  # 会話返答2-4文 + correctionブロックに十分な量に最適化
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
    """Generate a detailed, evidence-based summary and scoring for the completed conversation.

    採点の根拠を明確にするため、以下の観点で分析する:
    - accuracy_score: 文法・語彙ミスの頻度（ミス数 / 発言数で算出）
    - vocabulary_score: 語彙の多様性・レベル・コロケーションの自然さ
    - fluency_score: 発言の長さ・複雑さ・会話の流れへの貢献度
    - overall_score: 上記3スコアの加重平均
    ※ 発音はテキストから判定不可能なため、スコアから除外して正直に伝える
    """
    user_messages = [m['content'] for m in messages if m.get('role') == 'user']
    turn_count = len(user_messages)

    conversation_text = '\n'.join([
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
        if m.get('role') in ('user', 'assistant')
    ])

    prompt = f"""You are an expert English teacher. Analyze this English conversation and produce detailed, evidence-based feedback.

CONVERSATION:
{conversation_text}

SCORING INSTRUCTIONS (be strict and precise — do not give inflated scores):

**Step 1 — Count errors in ALL user messages:**
Go through every USER line and list each error (grammar, vocabulary, unnatural phrasing, wrong preposition, Japlish, etc.).
Total user turns: {turn_count}

**Step 2 — Calculate scores using these formulas:**

accuracy_score (文法・語彙の正確さ):
- error_rate = total_errors / max(turn_count, 1)
- 0 errors per turn → 95-100
- 0.1-0.3 errors per turn → 80-94
- 0.4-0.6 errors per turn → 65-79
- 0.7-1.0 errors per turn → 50-64
- 1.0+ errors per turn → 35-49

vocabulary_score (語彙の豊富さ・自然さ):
- Count unique meaningful words used by the user
- Assess whether phrasing sounds native or textbook-level
- Penalize heavy repetition and overuse of simple words (good, nice, like, very, etc.)
- 90-100: rich, varied, native-level | 70-89: decent range, some awkwardness | 50-69: limited/repetitive | below 50: very basic

fluency_score (流暢さ・会話への貢献):
- Assess average sentence length and complexity
- Did the user give substantive answers or just one/two-word replies?
- Did they ask questions, share opinions, develop topics?
- 90-100: engaging, developed, near-native flow | 70-89: adequate, mostly responsive | 50-69: short/choppy, needs prompting | below 50: very minimal

overall_score: weighted average — accuracy×0.4 + vocabulary×0.3 + fluency×0.3 (round to integer)

**Step 3 — Output JSON:**
{{
  "summary_ja": "会話の内容と学習者のパフォーマンスの要約（日本語、2-3文）",
  "strong_points_ja": [
    "具体的な良かった点（実際の発言例を引用して説明）",
    "具体的な良かった点2"
  ],
  "improvement_areas_ja": [
    "具体的な改善点（実際のミスを日本語で例示）",
    "具体的な改善点2"
  ],
  "overall_score": <integer 0-100>,
  "fluency_score": <integer 0-100>,
  "accuracy_score": <integer 0-100>,
  "vocabulary_score": <integer 0-100>,
  "score_reasoning": {{
    "errors_found": <integer — total errors counted>,
    "error_rate_per_turn": <float — errors/turns, rounded to 2 decimal places>,
    "accuracy_basis": "文法ミス・不自然表現の具体的な根拠（日本語、1-2文）",
    "vocabulary_basis": "語彙評価の根拠（日本語、1-2文）",
    "fluency_basis": "流暢さ評価の根拠（日本語、1-2文）",
    "pronunciation_note": "発音はテキストベースの分析では評価できないため採点対象外です。"
  }},
  "encouragement_ja": "具体的な次のステップを含む励ましのメッセージ（日本語、2文）",
  "useful_phrases": [
    {{
      "english": "A natural phrase actually used or clearly missed in this conversation",
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

IMPORTANT: Scores must reflect actual performance. A learner making 1 error per turn should NOT score above 65 on accuracy. Avoid score inflation."""

    completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': 'You are an expert English teacher who scores learners fairly and precisely based on evidence. Respond only with valid JSON.'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=1000,
        temperature=0.2,  # 採点の一貫性を高めるため低めに設定
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
            'score_reasoning': {
                'errors_found': 0,
                'error_rate_per_turn': 0.0,
                'accuracy_basis': '分析中にエラーが発生しました。',
                'vocabulary_basis': '分析中にエラーが発生しました。',
                'fluency_basis': '分析中にエラーが発生しました。',
                'pronunciation_note': '発音はテキストベースの分析では評価できないため採点対象外です。',
            },
            'encouragement_ja': '素晴らしい練習でした！続けて頑張りましょう！',
            'useful_phrases': [],
        }


def transcribe_audio(audio_file) -> str:
    """Transcribe audio using OpenAI Whisper.

    promptパラメータで「verbatim（逐語的）な文字起こし」を誘導し、
    Whisperが自動補正・補完するのを最小限に抑える。
    英会話練習アプリなので、学習者の実際の発話をそのまま記録することが重要。
    """
    transcript = client.audio.transcriptions.create(
        model='whisper-1',
        file=audio_file,
        language='en',
        prompt=(
            "Transcribe exactly what the speaker says, word for word. "
            "Do not correct grammar, complete sentences, or add words that were not spoken. "
            "Preserve all hesitations, incomplete phrases, and non-native speech patterns as spoken."
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
