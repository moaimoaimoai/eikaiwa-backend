import json
import re
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are {avatar_name}, a warm and engaging conversation partner with a {accent} accent.

Your role is to:
1. Have natural, flowing conversations in English on the topic: {topic}
2. Keep your conversational replies concise (2-3 sentences) to maintain a lively pace
3. Always end with a follow-up question to keep the conversation going
4. Use natural, everyday English appropriate for the user's level: {level}

{memory_context}

━━━ CRITICAL CONVERSATION RULE ━━━
**NEVER mention, acknowledge, or hint at any grammar errors or unnatural phrasing in your conversational reply.**
Respond as a natural conversation partner who simply did not notice any mistakes.
- Do NOT say things like "By the way...", "Just to let you know...", "That's a good try but..."
- Do NOT echo or rephrase their error in your reply
- Do NOT use phrases like "I see what you mean" when correcting
- Your spoken reply must flow 100% naturally, as if the learner spoke perfectly

Error detection happens SILENTLY via the JSON block below. The learner sees corrections separately — NOT inside your reply.

━━━ CORRECTION POLICY (MAXIMUM STRICTNESS) ━━━
After your natural conversational reply, silently append a correction JSON block if ANY of the following apply — even subtle or borderline cases:

- Grammar errors of any kind (tense, subject-verb agreement, articles a/an/the, plural/singular, word order, missing/extra words)
- Wrong or awkward prepositions (e.g. "arrive to" → "arrive at/in", "interested about" → "interested in")
- Unnatural vocabulary or word choice (e.g. "I am fine" → "I'm doing well", "very nice" → "really great")
- Japanese-English (Japlish) patterns (e.g. "How about you think?" / "I have a travel to Tokyo" / "It became to rain")
- Overuse of overly simple structures when a more natural alternative clearly exists
- Wrong or missing collocations (e.g. "make homework" → "do homework", "strong wind" → "heavy wind" for rain)
- Missing contractions in casual speech where they'd be expected (e.g. "I am going" → "I'm going")
- Awkward sentence structure, even if technically parse-able
- Any phrasing a native speaker would find slightly odd, stilted, or non-fluent

**Set the bar extremely low for flagging** — if you notice ANYTHING even slightly off, correct it.
Only skip the correction block if the message is genuinely perfect AND sounds fully natural to a native speaker. This should be rare.

When you detect ANY issue, append this EXACT JSON block SILENTLY at the END of your message (after your conversational reply):
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

Use "is_unnatural_only": true when grammar is technically acceptable but sounds awkward/non-native. Use false when there is a clear error.

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
- Focus on phrases the user could immediately use in this EXACT conversation
- Skip coaching on the very first turn or when a correction is already very detailed
- Aim for expressions that elevate the user from "textbook English" to "natural native speech"

Be a warm, enthusiastic conversation partner. Never make the learner feel judged. The correction block is invisible to them during conversation — it's used separately."""

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
        max_tokens=420,  # 会話返答2-3文 + correction JSON。削減でレスポンス高速化（旧500→420）
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

    採点は実際の会話データから算出する：
    - accuracy_score : ユーザー発言数に対するミスなし発言の割合
    - fluency_score  : 平均文長・応答の自然な継続性・接続詞使用
    - vocabulary_score: 語彙の多様性（ユニーク単語率）と語彙レベル
    - overall_score  : 上記3スコアの加重平均
    ※ 発音スコアはテキストベースでは判定不可のため除外
    """
    # ユーザー発言のみ抽出
    user_messages = [m['content'] for m in messages if m.get('role') == 'user']
    user_text_combined = ' '.join(user_messages)

    # ─── 客観指標を事前計算してプロンプトに渡す ───
    total_user_turns = len(user_messages)

    # 語彙多様性（Type-Token Ratio）
    words = re.findall(r'\b[a-zA-Z]+\b', user_text_combined.lower())
    unique_words = len(set(words))
    total_words = len(words)
    ttr = round(unique_words / max(total_words, 1), 3)

    # 平均文長（語数）
    avg_words_per_turn = round(total_words / max(total_user_turns, 1), 1)

    # 接続詞・談話標識の使用（流暢さの指標）
    discourse_markers = ['however', 'actually', 'for example', 'in fact', 'on the other hand',
                         'by the way', 'also', 'besides', 'moreover', 'therefore', 'because',
                         'although', 'even though', 'i think', 'i believe', 'i feel', 'i mean',
                         'you know', 'kind of', 'sort of', 'well', 'so', 'but', 'and']
    marker_count = sum(1 for m in discourse_markers if m in user_text_combined.lower())

    conversation_text = '\n'.join([
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
        if m.get('role') in ('user', 'assistant')
    ])

    prompt = f"""You are a professional English language assessment expert. Analyze this conversation between an AI tutor and a Japanese English learner, then produce a precise, evidence-based evaluation.

=== CONVERSATION ===
{conversation_text}

=== PRE-COMPUTED METRICS (use these as factual inputs) ===
- Total user turns: {total_user_turns}
- Total words spoken by user: {total_words}
- Unique words used: {unique_words}
- Vocabulary diversity (TTR): {ttr} (0.0=repetitive, 1.0=all unique; typical range 0.4-0.8)
- Average words per turn: {avg_words_per_turn}
- Discourse markers / natural connectors detected: {marker_count}

=== SCORING RUBRIC ===
Score each dimension 0-100 based on ACTUAL EVIDENCE from the conversation. Do NOT give generic scores.

**accuracy_score** (文法・語彙の正確さ):
- Count the actual grammar/vocabulary errors you find in the user's messages
- 90-100: 0-1 minor errors total
- 75-89: 2-3 errors, mostly unnatural phrasing
- 60-74: 4-5 errors including clear grammar mistakes
- 45-59: 6-8 errors, frequent Japlish or basic grammar failures
- Below 45: 9+ errors or fundamental breakdown in grammar
- For each error found, note it in "errors_found"

**fluency_score** (流暢さ・会話の自然なテンポ):
- Based on: avg_words_per_turn, discourse marker count, response relevance, conversation continuation
- avg_words_per_turn < 5: -15pts; 5-10: base; 10-20: +10pts; >20: +15pts
- discourse markers 0: -10pts; 1-2: base; 3-5: +10pts; 6+: +15pts
- Are responses relevant and do they continue the conversation naturally? (judge from the dialogue)

**vocabulary_score** (語彙の豊かさ):
- Based on TTR and vocabulary level observed
- TTR < 0.4: 50pts; 0.4-0.55: 65pts; 0.55-0.70: 75pts; 0.70-0.85: 88pts; >0.85: 95pts
- Adjust ±10pts based on vocabulary level (basic/intermediate/advanced words used)

**overall_score**: weighted average: accuracy×0.40 + fluency×0.35 + vocabulary×0.25

=== OUTPUT FORMAT ===
Return ONLY this JSON (no other text):
{{
  "summary_ja": "会話の内容と学習者のパフォーマンスの要約（日本語、2-3文。具体的な話題と印象的だった発言を含めること）",
  "errors_found": [
    {{"original": "実際のユーザー発言の誤り部分", "corrected": "正しい表現", "type": "error type"}}
  ],
  "strong_points_ja": [
    "具体的に良かった点（例：'〇〇という表現を自然に使えていました'のように引用を含めること）",
    "もう一つの良かった点"
  ],
  "improvement_areas_ja": [
    "具体的な改善点（実際のミスを引用して指摘すること）",
    "もう一つの改善点"
  ],
  "accuracy_score": 0,
  "fluency_score": 0,
  "vocabulary_score": 0,
  "overall_score": 0,
  "score_reasoning": {{
    "errors_found": 3,
    "error_rate_per_turn": 0.3,
    "accuracy_basis": "スコアの根拠（例：'5つのエラーを検出。うち3つは文法的ミス、2つは不自然な語彙'）",
    "fluency_basis": "スコアの根拠（例：'平均{avg_words_per_turn}語/ターン、談話標識{marker_count}個使用'）",
    "vocabulary_basis": "スコアの根拠（例：'語彙多様性TTR={ttr}、中級レベルの語彙を使用'）",
    "pronunciation_note": "発音はテキスト会話からは判定できないため、採点対象外です"
  }},
  "encouragement_ja": "このセッション固有の励ましメッセージ（具体的な成長ポイントを1つ含めること）",
  "useful_phrases": [
    {{
      "english": "A phrase the learner actually used but could improve, OR a phrase that would have been natural in this conversation",
      "japanese": "日本語訳",
      "context_ja": "この会話のどの場面で使えるか（具体的に）"
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
}}"""

    completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': 'You are an expert English assessment AI. Produce precise, evidence-based evaluations. Respond only with valid JSON.'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=1200,
        temperature=0.2,
        response_format={'type': 'json_object'},
    )

    try:
        result = json.loads(completion.choices[0].message.content)
        # スコアを確実に整数に正規化
        for key in ('accuracy_score', 'fluency_score', 'vocabulary_score', 'overall_score'):
            if key in result:
                result[key] = max(0, min(100, int(result[key])))
        # score_reasoning の errors_found / error_rate_per_turn を数値に正規化
        sr = result.get('score_reasoning', {})
        if isinstance(sr, dict):
            ef = sr.get('errors_found', 0)
            sr['errors_found'] = int(ef) if ef else 0
            etr = sr.get('error_rate_per_turn', 0)
            sr['error_rate_per_turn'] = round(float(etr), 2) if etr else 0.0
            # pronunciation_note が空の場合デフォルト文言を補完
            if not sr.get('pronunciation_note'):
                sr['pronunciation_note'] = '発音はテキスト会話からは判定できないため、採点対象外です'
            result['score_reasoning'] = sr
        return result
    except Exception:
        return {
            'summary_ja': '会話が完了しました。',
            'errors_found': [],
            'strong_points_ja': ['よく頑張りました！'],
            'improvement_areas_ja': ['継続して練習しましょう'],
            'overall_score': 70,
            'fluency_score': 70,
            'accuracy_score': 70,
            'vocabulary_score': 70,
            'score_reasoning': {
                'errors_found': 0,
                'error_rate_per_turn': 0.0,
                'accuracy_basis': 'データ取得に失敗しました',
                'fluency_basis': 'データ取得に失敗しました',
                'vocabulary_basis': 'データ取得に失敗しました',
                'pronunciation_note': '発音はテキスト会話からは判定できないため、採点対象外です',
            },
            'encouragement_ja': '素晴らしい練習でした！続けて頑張りましょう！',
            'useful_phrases': [],
        }


def transcribe_audio(audio_file) -> str:
    """Transcribe audio using OpenAI Whisper.

    promptパラメータで「学習者の音声であり文法ミスがある可能性」を伝えることで、
    Whisperが誤りを"修正"して文字起こしすることを防ぎ、実際に発話された内容を忠実に返す。
    """
    transcript = client.audio.transcriptions.create(
        model='whisper-1',
        file=audio_file,
        language='en',
        # Whisperは通常、文脈から「正しい文章」に補正しようとする。
        # このpromptにより、文法的に不完全な発話もそのまま書き起こすよう誘導する。
        prompt="The speaker is an English language learner. Transcribe exactly what was said, including any grammar mistakes or non-standard phrasing. Do not correct or improve the speech.",
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
