from django.core.management.base import BaseCommand
from apps.phrases.models import Category, Phrase, Word


CATEGORIES = [
    {'name': 'Greetings', 'name_ja': '挨拶・日常会話', 'icon': '👋', 'order': 1},
    {'name': 'Shopping', 'name_ja': 'ショッピング', 'icon': '🛍️', 'order': 2},
    {'name': 'Restaurant', 'name_ja': 'レストラン', 'icon': '🍽️', 'order': 3},
    {'name': 'Travel', 'name_ja': '旅行・移動', 'icon': '✈️', 'order': 4},
    {'name': 'Business', 'name_ja': 'ビジネス', 'icon': '💼', 'order': 5},
    {'name': 'Small Talk', 'name_ja': '雑談', 'icon': '💬', 'order': 6},
]

PHRASES = [
    # Greetings - Beginner
    {'category': 'Greetings', 'english': "How's it going?", 'japanese': '調子はどうですか？',
     'pronunciation_hint': 'ハウズ イット ゴーイング', 'example_context': 'Casual greeting between friends',
     'level': 'beginner'},
    {'category': 'Greetings', 'english': "Long time no see!", 'japanese': 'お久しぶりですね！',
     'pronunciation_hint': 'ロング タイム ノー スィー', 'example_context': 'When meeting someone after a while',
     'level': 'beginner'},
    {'category': 'Greetings', 'english': "What have you been up to?", 'japanese': '最近どうしてましたか？',
     'pronunciation_hint': 'ワット ハヴ ユー ビーン アップ トゥー', 'example_context': 'After not seeing someone for a while',
     'level': 'beginner'},
    {'category': 'Greetings', 'english': "Nice to meet you!", 'japanese': 'はじめまして！',
     'pronunciation_hint': 'ナイス トゥー ミーチュー', 'example_context': 'First meeting',
     'level': 'beginner'},
    {'category': 'Greetings', 'english': "Take care!", 'japanese': 'お気をつけて！',
     'pronunciation_hint': 'テイク ケア', 'example_context': 'Saying goodbye',
     'level': 'beginner'},
    # Small Talk - Beginner
    {'category': 'Small Talk', 'english': "That sounds great!", 'japanese': 'それは素晴らしいですね！',
     'pronunciation_hint': 'ザット サウンズ グレイト', 'example_context': 'Reacting positively to news',
     'level': 'beginner'},
    {'category': 'Small Talk', 'english': "I totally agree.", 'japanese': '完全に同意します。',
     'pronunciation_hint': 'アイ トータリー アグリー', 'example_context': 'Agreeing with someone',
     'level': 'beginner'},
    {'category': 'Small Talk', 'english': "That's interesting!", 'japanese': 'それは面白いですね！',
     'pronunciation_hint': 'ザッツ インタレスティング', 'example_context': 'Showing interest in what someone says',
     'level': 'beginner'},
    {'category': 'Small Talk', 'english': "I'm not sure about that.", 'japanese': 'それについては確信がありません。',
     'pronunciation_hint': 'アイム ノット シュア アバウト ザット', 'example_context': 'Expressing uncertainty',
     'level': 'beginner'},
    {'category': 'Small Talk', 'english': "Can you say that again?", 'japanese': 'もう一度言っていただけますか？',
     'pronunciation_hint': 'キャン ユー セイ ザット アゲイン', 'example_context': 'Asking for repetition',
     'level': 'beginner'},
    # Restaurant - Beginner
    {'category': 'Restaurant', 'english': "I'd like to order, please.", 'japanese': '注文したいのですが。',
     'pronunciation_hint': 'アイド ライク トゥー オーダー プリーズ', 'example_context': 'Getting waiter attention',
     'level': 'beginner'},
    {'category': 'Restaurant', 'english': "Could I see the menu?", 'japanese': 'メニューを見せていただけますか？',
     'pronunciation_hint': 'クッダイ スィー ザ メニュー', 'example_context': 'Asking for menu',
     'level': 'beginner'},
    # Shopping - Beginner
    {'category': 'Shopping', 'english': "How much does this cost?", 'japanese': 'これはいくらですか？',
     'pronunciation_hint': 'ハウ マッチ ダズ ディス コスト', 'example_context': 'Asking for price',
     'level': 'beginner'},
    {'category': 'Shopping', 'english': "Do you have this in a different size?", 'japanese': '別のサイズはありますか？',
     'pronunciation_hint': 'ドゥ ユー ハヴ ディス イン ア ディファレント サイズ', 'example_context': 'Shopping for clothes',
     'level': 'beginner'},
    # Business - Intermediate
    {'category': 'Business', 'english': "Let me get back to you on that.", 'japanese': 'それについては後ほどお返事します。',
     'pronunciation_hint': 'レット ミー ゲット バック トゥー ユー オン ザット', 'example_context': 'Deferring a decision',
     'level': 'intermediate'},
    {'category': 'Business', 'english': "Could you elaborate on that?", 'japanese': 'もう少し詳しく説明していただけますか？',
     'pronunciation_hint': 'クッジュー エラボレイト オン ザット', 'example_context': 'Asking for more details',
     'level': 'intermediate'},
    {'category': 'Business', 'english': "I appreciate your patience.", 'japanese': 'ご辛抱いただきありがとうございます。',
     'pronunciation_hint': 'アイ アプリーシエイト ユア ペイシェンス', 'example_context': 'Business communication',
     'level': 'intermediate'},
    # Travel - Intermediate
    {'category': 'Travel', 'english': "Could you recommend a good restaurant nearby?", 'japanese': '近くに良いレストランを教えていただけますか？',
     'pronunciation_hint': 'クッジュー レコメンド ア グッド レストラン ニアバイ', 'example_context': 'Asking for recommendations',
     'level': 'intermediate'},
    {'category': 'Travel', 'english': "How long does it take to get there?", 'japanese': 'そこに着くまでどのくらいかかりますか？',
     'pronunciation_hint': 'ハウ ロング ダズ イット テイク トゥー ゲット ゼア', 'example_context': 'Asking about travel time',
     'level': 'intermediate'},
    {'category': 'Travel', 'english': "Is this seat taken?", 'japanese': 'この席は空いていますか？',
     'pronunciation_hint': 'イズ ディス スィート テイクン', 'example_context': 'On public transport',
     'level': 'beginner'},
]

WORDS = [
    # Beginner
    {'word': 'Nevertheless', 'definition': 'In spite of that; notwithstanding', 'definition_ja': 'それにもかかわらず',
     'part_of_speech': 'adverb', 'example_sentence': "It was raining; nevertheless, we went for a walk.",
     'example_sentence_ja': '雨が降っていた。それにもかかわらず、私たちは散歩に出かけた。', 'level': 'intermediate'},
    {'word': 'Elaborate', 'definition': 'To explain something in more detail', 'definition_ja': '詳しく説明する',
     'part_of_speech': 'verb', 'example_sentence': "Could you elaborate on your point?",
     'example_sentence_ja': 'あなたの意見をもう少し詳しく説明していただけますか？', 'level': 'intermediate'},
    {'word': 'Furthermore', 'definition': 'In addition; moreover', 'definition_ja': 'さらに；その上',
     'part_of_speech': 'adverb', 'example_sentence': "Furthermore, we need to consider the budget.",
     'example_sentence_ja': 'さらに、予算も考慮する必要があります。', 'level': 'intermediate'},
    {'word': 'Acknowledge', 'definition': 'To recognize or admit the existence of something', 'definition_ja': '認める；承認する',
     'part_of_speech': 'verb', 'example_sentence': "I acknowledge your concern.",
     'example_sentence_ja': 'あなたの懸念を認めます。', 'level': 'intermediate'},
    {'word': 'Occasionally', 'definition': 'Sometimes but not regularly', 'definition_ja': '時々；折に触れて',
     'part_of_speech': 'adverb', 'example_sentence': "I occasionally work from home.",
     'example_sentence_ja': '私は時々在宅勤務をします。', 'level': 'beginner'},
    {'word': 'Enthusiastic', 'definition': 'Having or showing intense excitement and interest', 'definition_ja': '熱心な；熱狂的な',
     'part_of_speech': 'adjective', 'example_sentence': "She is enthusiastic about learning English.",
     'example_sentence_ja': '彼女は英語学習に熱心です。', 'level': 'intermediate'},
    {'word': 'Perspective', 'definition': 'A particular attitude or way of thinking about something', 'definition_ja': '視点；観点',
     'part_of_speech': 'noun', 'example_sentence': "Try to see things from a different perspective.",
     'example_sentence_ja': '物事を違う視点から見てみましょう。', 'level': 'intermediate'},
    {'word': 'Consequently', 'definition': 'As a result; therefore', 'definition_ja': 'その結果；したがって',
     'part_of_speech': 'adverb', 'example_sentence': "He didn't study; consequently, he failed the exam.",
     'example_sentence_ja': '彼は勉強しなかった。その結果、試験に落ちた。', 'level': 'intermediate'},
    {'word': 'Ambitious', 'definition': 'Having a strong desire for success', 'definition_ja': '野心的な；意欲的な',
     'part_of_speech': 'adjective', 'example_sentence': "She is ambitious and works very hard.",
     'example_sentence_ja': '彼女は野心的でとても一生懸命働く。', 'level': 'beginner'},
    {'word': 'Collaborate', 'definition': 'To work with others to achieve something', 'definition_ja': '協力する；共同作業する',
     'part_of_speech': 'verb', 'example_sentence': "We collaborated on the project.",
     'example_sentence_ja': '私たちはプロジェクトで協力した。', 'level': 'intermediate'},
    {'word': 'Inevitable', 'definition': 'Certain to happen and unable to be avoided', 'definition_ja': '避けられない；必然的な',
     'part_of_speech': 'adjective', 'example_sentence': "Change is inevitable.",
     'example_sentence_ja': '変化は避けられない。', 'level': 'advanced'},
    {'word': 'Spontaneous', 'definition': 'Happening naturally without planning', 'definition_ja': '自発的な；即興の',
     'part_of_speech': 'adjective', 'example_sentence': "Let's do something spontaneous tonight!",
     'example_sentence_ja': '今夜は何か気まぐれにやってみよう！', 'level': 'advanced'},
]


class Command(BaseCommand):
    help = 'Seed initial phrases and words data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding categories...')
        category_map = {}
        for cat_data in CATEGORIES:
            cat, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            category_map[cat.name] = cat
            if created:
                self.stdout.write(f'  Created category: {cat.name}')

        self.stdout.write('Seeding phrases...')
        for phrase_data in PHRASES:
            category = category_map[phrase_data.pop('category')]
            phrase, created = Phrase.objects.get_or_create(
                english=phrase_data['english'],
                defaults={**phrase_data, 'category': category}
            )
            if created:
                self.stdout.write(f'  Created phrase: {phrase.english}')

        self.stdout.write('Seeding words...')
        for word_data in WORDS:
            word, created = Word.objects.get_or_create(
                word=word_data['word'],
                defaults=word_data
            )
            if created:
                self.stdout.write(f'  Created word: {word.word}')

        self.stdout.write(self.style.SUCCESS('✅ Seed data created successfully!'))
