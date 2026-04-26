"""
添削・コーチング機能の動作確認スクリプト
使い方: python test_correction.py
"""
import os, sys, json, re

# .env を読み込む
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

from openai import OpenAI

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# ── テスト用ユーザー発言（わざとミスを含む） ──
TEST_MESSAGES = [
    "I go to shopping yesterday with my friend.",   # 文法ミス複数
    "I am very boring in this class.",              # vocabulary ミス
    "She don't like cats.",                         # 文法ミス
    "I have a travel to Tokyo last week.",          # Japlish
    "It is very nice weather today.",               # 自然だが改善余地あり
]

SYSTEM_PROMPT_MINI = """You are Emma, a warm English conversation partner with an American accent.

━━━ SILENT CORRECTION POLICY ━━━
After writing your conversational reply (2-4 sentences), append this EXACT JSON block:
<correction>
{
  "has_mistake": true or false,
  "original": "the exact phrase that needs improvement",
  "corrected": "the most natural native-speaker version",
  "explanation": "日本語で説明",
  "mistake_type": "grammar|vocabulary|preposition|collocation|unnatural|word_order|article|other",
  "is_unnatural_only": true or false,
  "advice_ja": "実践アドバイス（日本語、1〜2文）",
  "level_up": "さらに上級の表現（任意）",
  "useful_phrases": [
    {"english": "Natural alternative phrase", "japanese": "日本語訳"},
    {"english": "Another related phrase", "japanese": "日本語訳"},
    {"english": "A third variation", "japanese": "日本語訳"}
  ]
}
</correction>

━━━ COACHING ━━━
Also ALWAYS append after any correction:
<coaching>
{
  "tip_ja": "この文脈で役立つワンポイントアドバイス（日本語、1文）",
  "useful_phrases": [
    {"english": "A phrase the user could use right now", "japanese": "日本語訳"},
    {"english": "Another practical phrase", "japanese": "日本語訳"}
  ]
}
</coaching>"""


def test_message(user_text: str, max_tokens: int = 1200) -> dict:
    completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT_MINI},
            {'role': 'user', 'content': user_text},
        ],
        max_tokens=max_tokens,
        temperature=0.8,
    )

    choice = completion.choices[0]
    full = choice.message.content or ''
    finish_reason = choice.finish_reason
    usage = completion.usage

    correction = None
    coaching = None
    clean = full

    cm = re.search(r'<correction>(.*?)</correction>', full, re.DOTALL)
    if cm:
        try:
            correction = json.loads(cm.group(1).strip())
            clean = full[:cm.start()].strip()
        except json.JSONDecodeError as e:
            correction = f'[JSONパースエラー: {e}]'

    km = re.search(r'<coaching>(.*?)</coaching>', full, re.DOTALL)
    if km:
        try:
            coaching = json.loads(km.group(1).strip())
        except json.JSONDecodeError as e:
            coaching = f'[JSONパースエラー: {e}]'

    return {
        'user': user_text,
        'finish_reason': finish_reason,
        'tokens_used': usage.completion_tokens,
        'clean_response': clean,
        'correction_found': correction is not None,
        'coaching_found': coaching is not None,
        'correction': correction,
        'coaching': coaching,
        'raw_tail': full[-300:],  # 末尾300文字（切れていないか確認用）
    }


def main():
    print('=' * 60)
    print('添削・コーチング機能 動作確認テスト')
    print('=' * 60)

    ok_count = 0
    for i, msg in enumerate(TEST_MESSAGES, 1):
        print(f'\n【テスト {i}/{len(TEST_MESSAGES)}】')
        print(f'  ユーザー発言: "{msg}"')

        result = test_message(msg)

        status_fin = '✅' if result['finish_reason'] == 'stop' else '⚠️ 途中切れ'
        status_cor = '✅ あり' if result['correction_found'] else '❌ なし'
        status_coa = '✅ あり' if result['coaching_found'] else '❌ なし'

        print(f'  finish_reason : {result["finish_reason"]} {status_fin}')
        print(f'  使用トークン数: {result["tokens_used"]}')
        print(f'  添削ブロック  : {status_cor}')
        print(f'  コーチング    : {status_coa}')

        if result['correction_found'] and isinstance(result['correction'], dict):
            c = result['correction']
            print(f'  └ has_mistake : {c.get("has_mistake")}')
            print(f'  └ original    : {c.get("original")}')
            print(f'  └ corrected   : {c.get("corrected")}')

        if result['finish_reason'] == 'length':
            print(f'  ⚠️  末尾(切れ箇所): ...{result["raw_tail"]}')

        if result['correction_found'] and result['coaching_found']:
            ok_count += 1

    print('\n' + '=' * 60)
    print(f'結果: {ok_count}/{len(TEST_MESSAGES)} 件で両ブロック取得成功')
    if ok_count == len(TEST_MESSAGES):
        print('🎉 すべて正常！添削・コーチングは正常に動作しています。')
    else:
        print('⚠️  一部失敗。サーバーを再起動してから再テストしてください。')
    print('=' * 60)


if __name__ == '__main__':
    main()
