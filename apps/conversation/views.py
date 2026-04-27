import base64
import io
import random
from datetime import datetime
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from .models import ConversationSession, ConversationMessage
from .serializers import ConversationSessionSerializer, ConversationMessageSerializer
from .openai_service import chat_with_ai, generate_conversation_summary, transcribe_audio, transcribe_audio_ja, text_to_speech, update_user_memory, japanese_to_english
from apps.mistakes.models import Mistake
from apps.accounts.models import UserMemory
from apps.phrases.models import SavedPhrase

# 1セッションあたりのユーザー発言上限（フロントエンドの MAX_TURNS と合わせる）
MAX_TURNS_PER_SESSION = 10

# ── 内部テーマ辞書（トピック別・多様性確保用）──
# daily_topic_label が指定されていない通常会話でも毎回違う話題から始まるようにするための内部ヒント集。
# キーは conversation topic。(opening_question_seed, conversation_hint) のタプルリスト。
# ユーザーには表示されない。
INTERNAL_TOPICS = {
    'free': [
        # ── 思い出・人生 ──
        ("a childhood memory that still makes you smile or laugh", "childhood memories"),
        ("something on your bucket list and what is stopping you from doing it", "bucket list"),
        ("a moment in your life that completely changed your direction", "life-changing moments"),
        ("the best piece of advice you have ever received and who gave it", "life advice"),
        ("what success looks like to you — and whether that has changed over time", "definition of success"),
        ("if you could give your younger self one piece of advice, what would it be?", "advice to self"),
        ("something you believed strongly as a kid but now see differently", "changed beliefs"),
        ("a decision you almost did not make that turned out to be one of the best", "good decisions"),
        ("the most unexpected thing you have ever learned about yourself", "self-discovery"),
        ("a turning point you almost missed — and what reminded you to take it", "turning points"),
        # ── 想像・仮定 ──
        ("your hidden talent that most people do not know about", "hidden talents"),
        ("if you could have dinner with anyone — living or from history — who would it be?", "dinner with anyone"),
        ("a superpower you would choose and how you would use it in everyday life", "superpowers"),
        ("if you could instantly speak any language fluently, which one and why?", "language dreams"),
        ("what you would do if you won the lottery tomorrow — first 24 hours", "lottery dreams"),
        ("if you could swap lives with someone for a week, who and why?", "life swap"),
        ("the era in history you would most want to visit — and the danger you would face", "time travel"),
        ("if you could redesign one thing about modern society, what would it be?", "redesigning society"),
        ("if money and time were no limit, what project would you start tomorrow?", "dream project"),
        ("what animal best represents your personality and why?", "spirit animal"),
        # ── 価値観・感情 ──
        ("what you would do with one completely free day — no responsibilities at all", "perfect free day"),
        ("something that always makes you laugh, no matter how many times you see it", "things that make you laugh"),
        ("what happiness looks like in your day-to-day life — the small things", "everyday happiness"),
        ("the strangest or funniest thing that has happened to you recently", "funny moments"),
        ("what you tend to think about when you cannot sleep at night", "late night thoughts"),
        ("your life's soundtrack — the songs that define different chapters", "personal soundtrack"),
        ("something you think is hugely overrated — and something underrated", "over and underrated"),
        ("how you would describe your current life chapter if it were a movie title", "life chapter"),
        ("the best compliment you have ever given someone — and their reaction", "giving compliments"),
        ("a food or experience you were convinced you would hate but ended up loving", "surprised by enjoyment"),
        # ── 日常の発見 ──
        ("if you could live anywhere in the world for one year, where and why?", "dream place to live"),
        ("what you think future generations will look back on us and find bizarre", "future perspective"),
        ("a skill or knowledge area you wish you had started learning earlier", "skills to start earlier"),
        ("the most useful app or tool in your life right now — and one you deleted", "digital tools"),
        ("how you would describe your personality to someone who has never met you", "describing yourself"),
        ("what small thing in daily life you are genuinely grateful for", "small gratitude"),
        ("your most used phrase or expression and where it came from", "favourite phrases"),
        ("something you can do that you suspect most people around you cannot", "unique abilities"),
        ("the movie or show you keep recommending but nobody watches", "underrated recommendations"),
        ("what a perfect Sunday morning looks like for you, in detail", "perfect Sunday"),
    ],
    'daily_life': [
        # ── 朝・夜のルーティン ──
        ("your morning routine and the one thing that can make or break your whole day", "morning habits"),
        ("how you usually unwind in the evening after a long day", "evening routine"),
        ("what you usually have for breakfast — and whether it actually starts your day well", "breakfast habits"),
        ("sleep habits — night owl, early bird, or fighting nature every day?", "sleep habits"),
        ("the ritual that marks the end of your workday or school day", "end-of-day ritual"),
        ("how the seasons affect your daily mood and energy levels", "seasons and mood"),
        # ── 食・料理 ──
        ("your go-to comfort food and the story behind why you love it", "comfort food"),
        ("your coffee or tea ritual — and what would happen if you had to give it up", "coffee and tea"),
        ("how you approach grocery shopping and cooking at home", "home cooking"),
        ("a local restaurant or café you would always recommend to visitors", "local favorites"),
        ("your relationship with cooking — is it joy, duty, or something you outsource?", "cooking relationship"),
        ("the most satisfying meal you have cooked for yourself recently", "home cooking wins"),
        # ── デジタル・スマホ ──
        ("your relationship with your smartphone — could you survive a weekend without it?", "digital habits"),
        ("your most used app and what it says about your priorities", "top app"),
        ("how you feel about technology overall — does it serve you or rule you?", "tech relationship"),
        ("how often you check the news and how it affects your mood", "news habits"),
        # ── 家・空間 ──
        ("what your home or room says about your personality", "home and space"),
        ("your approach to keeping your space tidy — minimalist, organized chaos, or total mess?", "tidying up"),
        ("what your desk or workspace looks like right now and what it says about you", "workspace"),
        ("the most useful life skill you learned from a family member at home", "home skills"),
        # ── 街・移動 ──
        ("the most annoying and the best things about your daily commute", "commuting life"),
        ("your neighborhood — the hidden spots and what makes it feel like home", "local life"),
        ("your shopping style — do you browse for hours or go straight for what you need?", "shopping habits"),
        ("how you feel about your neighborhood and whether you would ever move", "neighborhood feelings"),
        # ── 週末・時間の使い方 ──
        ("your weekend routine — do you recharge alone or fill it with social plans?", "weekend life"),
        ("how you handle an unexpectedly free afternoon — what do you do first?", "free time"),
        ("the errands you secretly enjoy and the ones you keep putting off forever", "errands"),
        ("your strategy for remembering things — lists, apps, notes, or pure willpower?", "memory strategies"),
        # ── ストレス・メンタル ──
        ("how you handle stress in the middle of a busy day", "daily stress"),
        ("a pet peeve about daily life that drives you genuinely crazy", "daily pet peeves"),
        ("the small daily pleasures that reliably make life feel good", "small pleasures"),
        ("the part of your day you look forward to the most", "daily highlight"),
        # ── お金・生活 ──
        ("your approach to managing money day-to-day — careful planner or go-with-the-flow?", "money management"),
        ("the most satisfying purchase you have made recently — and why it was worth it", "good purchases"),
        ("a habit you have been trying to build for months with limited success", "habit building"),
        ("your approach to making new friends as an adult — harder than it sounds?", "adult friendships"),
        # ── 季節・暮らし ──
        ("your feelings about winter — cozy hibernation season or something to survive?", "winter feelings"),
        ("how you deal with being stuck indoors on a rainy day", "rainy day routine"),
        ("the last thing you repaired instead of throwing away — and whether it worked", "repair culture"),
        ("your approach to planning the week ahead — Sunday evening ritual or total chaos?", "weekly planning"),
    ],
    'travel': [
        # ── 旅の思い出 ──
        ("a trip or destination that surprised you in a way you did not expect", "travel surprises"),
        ("the most delicious food you have ever discovered while traveling", "food on the road"),
        ("a travel disaster or misadventure that became a funny story later", "travel mishaps"),
        ("a place you have been to that you would love to go back to someday", "places to revisit"),
        ("the strangest or most unexpected experience you have had while traveling", "weird travel moments"),
        ("a destination that felt surprisingly like home even though it was far away", "home away from home"),
        ("your most memorable conversation with a stranger you met while traveling", "stranger encounters"),
        ("a historical site or landmark you visited that genuinely moved you", "moving landmarks"),
        # ── 旅のスタイル ──
        ("your dream travel destination and what draws you there", "dream destinations"),
        ("how you prefer to travel — solo, with friends, with family — and why", "travel style"),
        ("your packing style — carry-on only minimalist or prepared for every scenario?", "packing habits"),
        ("your favorite type of accommodation — hotel, Airbnb, hostel, or camping?", "accommodation style"),
        ("how you research and plan a trip — detailed itinerary or completely go with the flow?", "travel planning"),
        ("your budget approach to travel — splurge on experiences or save wherever possible?", "travel budget"),
        ("seasonal travel preferences — summer beach, autumn leaves, winter escape, or spring blossoms?", "seasonal travel"),
        ("whether you prefer to explore one place deeply or hit many places quickly", "travel depth vs breadth"),
        # ── 文化・人 ──
        ("a cultural difference you noticed while traveling that genuinely surprised you", "cultural surprises"),
        ("the biggest cultural mistake you made while abroad and what you learned", "cultural mistakes"),
        ("the best way to connect with locals when you are traveling somewhere new", "connecting with locals"),
        ("how Japan looks through the eyes of foreign visitors — things they seem to love", "japan through foreign eyes"),
        # ── 国内・海外 ──
        ("the hidden gem in your own city or region that visitors almost always miss", "local gems"),
        ("if you could live in a foreign country for one year, where and why?", "living abroad"),
        ("your dream road trip — route, companions, and the ultimate playlist", "road trip dreams"),
        ("the travel documentary, book, or video that made you desperate to visit somewhere", "travel inspiration"),
        # ── 旅の実用 ──
        ("how traveling changes the way you see your everyday life when you come home", "travel perspective"),
        ("how you stay healthy and stick to routines while traveling — or do you abandon them?", "travel routines"),
        ("your experience with language barriers while traveling and how you got through", "language barriers"),
        ("the travel app or trick that completely changed how you explore new places", "travel hacks"),
        ("your experience with public transport abroad — confusion, adventure, or both?", "transport abroad"),
        ("what you always bring back from a trip as a souvenir — and what you wish you had bought", "travel souvenirs"),
        # ── 空想 ──
        ("if you could time travel to visit any era and place in history, where would you go?", "time travel destinations"),
        ("a tourist spot that was far more impressive than the hype — or a total letdown", "tourist spot reality"),
        ("the food from another country you now cook at home because you miss it", "bringing food home"),
        ("what a perfect day in your favorite city in the world looks like", "perfect city day"),
        ("the city you have visited that surprised you most with its atmosphere and vibe", "surprising cities"),
        ("the souvenir you regret not buying and still think about occasionally", "souvenir regrets"),
        ("how you capture memories while traveling — photos, journals, or just being present?", "capturing travel memories"),
        ("your experience with traveling on a tight budget and what you discovered", "budget travel"),
        ("the longest journey you have ever taken and how you kept yourself going", "long journeys"),
        ("if you could go on any trip starting tomorrow, what would it look like?", "spontaneous trip"),
    ],
    'business': [
        # ── 仕事の現実 ──
        ("what you enjoy most and least about your current work or field of study", "work reality"),
        ("your ideal work environment — open office, quiet corner, remote, or hybrid?", "ideal workspace"),
        ("how you manage your energy and focus during a long workday", "work productivity"),
        ("your experience with remote or hybrid work — what genuinely works and what does not", "remote work"),
        ("your strategy for handling tight deadlines and high-pressure moments", "deadline management"),
        ("how workplace culture affects your motivation and daily performance", "workplace culture"),
        ("the most valuable lesson a failure or mistake at work taught you", "learning from work failure"),
        ("how you handle a colleague or work situation that genuinely frustrates you", "workplace frustration"),
        # ── キャリア・成長 ──
        ("a professional challenge you faced that turned into an unexpected opportunity", "professional growth"),
        ("the mentors or role models who have shaped how you work and think", "career mentors"),
        ("a career path you seriously considered but did not take — any regrets?", "career paths"),
        ("the moment you realized what kind of work actually suits your personality", "career self-discovery"),
        ("your experience with job hunting, internships, or changing roles", "job hunting"),
        ("the professional skill that surprised you by being more important than expected", "surprising skills"),
        ("what you wish schools taught more about professional and working life", "missing education"),
        ("how you approach learning a completely new skill at work or for your career", "learning at work"),
        # ── コミュニケーション ──
        ("how you prepare for an important presentation, meeting, or difficult conversation", "presentation prep"),
        ("your approach to networking — do you enjoy it or find it genuinely exhausting?", "networking"),
        ("your communication style at work — email, chat, calls, or face-to-face?", "workplace communication"),
        ("how you handle giving and receiving feedback — easy or unexpectedly hard?", "feedback culture"),
        ("the work conversation you had that you found unexpectedly inspiring", "inspiring conversations"),
        # ── AI・未来 ──
        ("how AI and automation are already changing your work or field right now", "AI and work"),
        ("what you think the office and workplace will look like in 2035", "future of work"),
        ("your experience with or thoughts about side projects and freelance work", "side projects"),
        # ── リーダーシップ・組織 ──
        ("what leadership means to you and the qualities you most admire in a leader", "leadership"),
        ("the best team you have ever been part of and what made it work so well", "great teams"),
        ("what the perfect manager looks like to you — and how close your reality is", "ideal manager"),
        ("how you organize your tasks and priorities — apps, paper, or mental juggling?", "task management"),
        ("your morning work ritual before the real work of the day begins", "morning work ritual"),
        # ── ビジネス・お金 ──
        ("a company or leader you genuinely admire and what sets them apart", "business inspiration"),
        ("a business idea you have had but never acted on — what stopped you?", "entrepreneur dreams"),
        ("your relationship with money — saver, spender, investor, or undecided?", "money relationship"),
        ("business travel — the surprisingly good and surprisingly bad parts", "business travel"),
        ("work-life balance — how you actually achieve it versus how it is supposed to look", "work-life balance"),
        ("what you would say in your ideal job interview if you could be completely honest", "honest job interview"),
        ("how you stay updated on news, trends, and changes in your field", "staying current"),
        ("the biggest challenge facing your industry or field right now", "industry challenges"),
        ("your experience with performance reviews — useful, stressful, or both?", "performance reviews"),
        ("what you would change about the way businesses are typically run", "business improvement"),
    ],
    'school': [
        # ── 高校以前の思い出 ──
        ("your favorite subject in school and what made it genuinely exciting", "favorite subject"),
        ("the teacher who had the biggest impact on you and what made them memorable", "memorable teacher"),
        ("your school lunch memories — kyushoku, bento boxes, or cafeteria chaos?", "school lunch"),
        ("the club or after-school activity that most defined your school years", "club activities"),
        ("the most stressful exam you ever faced and how you got through it", "exam stress"),
        ("a school rule or tradition that felt strange but you now understand — or still find absurd", "school rules"),
        ("your best memory from a school trip or class excursion", "school trips"),
        ("the most embarrassing thing that ever happened to you at school", "school embarrassments"),
        ("school festivals, sports days, or cultural events that still stand out", "school events"),
        ("the teacher who made you dread a class and what that taught you about learning", "difficult teachers"),
        ("the subject you never expected to use in real life but turned out surprisingly useful", "unexpectedly useful subjects"),
        ("if you could go back to school for one day, what would you pay attention to?", "school nostalgia"),
        # ── 勉強・習慣 ──
        ("how you used to study — cramming the night before or steady and organized?", "study habits"),
        ("a subject you struggled with and how you eventually dealt with it", "difficult subjects"),
        ("the friendship that started at school and what made it last — or not", "school friendships"),
        ("what you wish had been different about your education", "education regrets"),
        ("the subject you wish your school had offered but never did", "missing subjects"),
        ("how your school experience shaped the way you learn and work today", "school impact"),
        # ── 大学生活 ──
        ("your university campus — what you love about it and what drives you crazy", "campus life"),
        ("how you chose your university major and whether you would make the same choice today", "choosing a major"),
        ("the seminar, lab, or research group you joined — how you chose it and what you found", "seminar and lab"),
        ("pulling an all-nighter before an assignment deadline — worth it or a disaster?", "all-nighters"),
        ("your part-time job during school and the most memorable thing it taught you", "student part-time work"),
        ("joining a university club or circle — how you chose and what happened next", "university clubs"),
        ("the professor who stood out most at university and why they were unforgettable", "university professors"),
        ("living alone for the first time — the freedom and the unexpected challenges", "living alone"),
        ("making friends at university — harder or easier than you expected?", "university friendships"),
        ("your university cafeteria — underrated hidden gem or place you needed to escape?", "university cafeteria"),
        ("the assignment or report you procrastinated on until the absolute last minute", "procrastination"),
        ("studying abroad or thinking about it — what draws you to the idea?", "study abroad interest"),
        ("the moment university felt completely different from high school — what changed?", "university vs high school"),
        ("how internships changed the way you think about your future career", "internships"),
        ("the course you signed up for expecting nothing but ended up being genuinely fascinating", "surprising university courses"),
        ("how you manage time between classes, clubs, part-time work, and a social life", "student time management"),
        ("entrance exams — the experience of preparing, the stress, and the relief of finishing", "entrance exams"),
        ("what graduation means to you and the mix of excitement and uncertainty it brings", "graduation feelings"),
        ("your advice to someone just starting their first year at university", "university advice"),
        ("the student council, campus event, or university project that you got involved in", "student activities"),
    ],
    'hobby': [
        # ── メイン趣味 ──
        ("your current main hobby and the moment you first got seriously into it", "main hobby"),
        ("a hobby you tried, loved briefly, then completely abandoned — and honestly, why", "abandoned hobbies"),
        ("a creative skill you would love to master if time and money were absolutely no issue", "dream creative skill"),
        ("the hobby you would pursue full-time if money were not a concern", "dream hobby"),
        ("a hobby that costs way too much money but you cannot seem to stop doing", "expensive hobbies"),
        ("hobbies you do best alone versus ones you really prefer sharing with other people", "solo vs social hobbies"),
        ("something you collect or used to collect and what the appeal was at the time", "collecting"),
        ("a seasonal hobby or activity you genuinely look forward to every single year", "seasonal hobbies"),
        ("the hobby that has taught you the most patience of anything in your life", "patience through hobbies"),
        ("a hobby you share with someone special and how it changed the relationship", "shared hobbies"),
        # ── エンタメ ──
        ("your relationship with video games — casual player, dedicated gamer, or non-player?", "gaming"),
        ("a movie, drama, or anime that stayed with you long after you finished it", "memorable stories"),
        ("a book, manga, or podcast that genuinely changed the way you think", "mind-changing media"),
        ("a YouTube channel or creator you have watched so much it feels like you know them", "favourite creators"),
        ("your relationship with anime — casual watcher, devoted fan, or curious outsider?", "anime relationship"),
        ("the concert, live event, or performance that was absolutely unforgettable", "live events"),
        ("board games, card games, or party games — do you love them or hate the losing part?", "tabletop games"),
        ("the movie or show you found by complete accident and could not stop watching", "accidental discoveries"),
        # ── 音楽 ──
        ("the music you listen to when you need energy versus when you want to truly relax", "music for moods"),
        ("how you discover new music — algorithms, recommendations, or old-fashioned browsing?", "discovering music"),
        ("the concert or live performance you want to attend before anything else", "concert bucket list"),
        # ── 創作・スキル ──
        ("cooking or baking experiments — your proudest creation and your most spectacular disaster", "cooking adventures"),
        ("photography — do you love capturing moments or prefer to just be fully present?", "photography"),
        ("a DIY or craft project you are genuinely proud of or secretly want to try", "DIY projects"),
        ("the craft or creative skill you do just for yourself, never really to show anyone", "private creativity"),
        ("your favorite way to be creative when you are short on time and energy", "quick creativity"),
        ("do you prefer making and creating things, or experiencing things others have made?", "making vs experiencing"),
        ("your history with reading — lifelong bookworm or someone who discovered it later in life?", "reading history"),
        # ── アウトドア・健康 ──
        ("your fitness routine — do you love it, dread it, or still trying to actually build one?", "fitness life"),
        ("hiking, cycling, or any outdoor activity you genuinely enjoy or have always wanted to try", "outdoor activities"),
        ("plants and gardening — confirmed green thumb or a graveyard of good intentions?", "gardening"),
        ("yoga, meditation, or mindfulness — something you genuinely swear by or are just curious about?", "mindfulness"),
        # ── 飲み物・食 ──
        ("your relationship with coffee, tea, or another drink you have developed a genuine appreciation for", "drink culture"),
        ("the sport you have never tried but secretly think you might actually be good at", "untried sports"),
        # ── SNS・情報 ──
        ("how social media has changed the way you pursue, share, or talk about your hobbies", "social media and hobbies"),
        ("your strategy for finding the next great book, movie, show, or album to enjoy", "finding new media"),
        ("the most useful thing a hobby has taught you that applies to everyday life", "hobby life lessons"),
        ("what you wish more people understood or appreciated about your favourite hobby", "hobby advocacy"),
        ("the event, festival, or competition in your hobby world you would love to attend someday", "hobby events"),
        ("a creative project that exists only in your head right now — what is it?", "dream creative project"),
    ],
}


class SessionListView(generics.ListAPIView):
    serializer_class = ConversationSessionSerializer

    def get_queryset(self):
        return ConversationSession.objects.filter(user=self.request.user)


@api_view(['POST'])
def start_session(request):
    """Start a new conversation session."""
    user = request.user

    # ── 使用量制限チェック ──
    user.reset_monthly_if_needed()
    if not user.can_start_session():
        return Response({
            'error': 'monthly_limit_reached',
            'message': '今月の会話上限に達しました。プレミアムプランにアップグレードするか、来月をお待ちください。',
            'monthly_used': user.monthly_sessions_used,
            'monthly_limit': user.monthly_limit,
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    topic = request.data.get('topic', 'free')
    avatar_name = request.data.get('avatar_name', 'Emma')
    avatar_accent = request.data.get('avatar_accent', 'American')
    # 今日のトピック（任意）
    daily_topic_label = request.data.get('daily_topic_label', '')
    daily_topic_hint  = request.data.get('daily_topic_hint', '')

    # Close any existing active sessions
    ConversationSession.objects.filter(
        user=user, is_active=True
    ).update(is_active=False, ended_at=timezone.now())

    session = ConversationSession.objects.create(
        user=user,
        topic=topic,
        avatar_name=avatar_name,
        avatar_accent=avatar_accent,
    )

    # ── ユーザー記憶を取得 ──
    memory, _ = UserMemory.objects.get_or_create(user=user)
    memory_context = memory.to_context_string()

    # Generate opening message from AI
    if daily_topic_label:
        # デイリートピック指定あり: シナリオに引き込む開幕メッセージを生成
        opening_prompt = (
            f'Please start the conversation by setting up the following specific scenario: "{daily_topic_label}". '
            f'Hint for the scenario: {daily_topic_hint}. '
            f'Immediately place the user IN the situation with a natural, immersive opening line '
            f'(e.g. pretend you are a hotel receptionist, a barista, a colleague, etc. as appropriate). '
            f'Keep it to 2-3 sentences and end with a question that naturally continues the scenario.'
        )
    else:
        # 内部テーマをランダム選択して会話の多様性を確保（ユーザーには表示されない）
        # 選択トピックに合ったカテゴリから選ぶ。対応なければ 'free' にフォールバック
        topic_pool = INTERNAL_TOPICS.get(topic, INTERNAL_TOPICS['free'])
        internal_seed, internal_hint = random.choice(topic_pool)
        opening_prompt = (
            f'Please start our conversation with a warm, natural greeting and ONE engaging opening question about '
            f'{internal_seed}. '
            f'Be conversational and friendly — like chatting with a curious friend, not a formal interview. '
            f'Keep it to 2-3 sentences max.'
        )

    opening_messages = [{'role': 'user', 'content': opening_prompt}]

    result = chat_with_ai(
        opening_messages,
        avatar_name=avatar_name,
        accent=avatar_accent,
        topic=topic,
        level=user.level,
        memory_context=memory_context,
        daily_topic_label=daily_topic_label,
        daily_topic_hint=daily_topic_hint,
    )

    # Save AI opening message
    ai_message = ConversationMessage.objects.create(
        session=session,
        role='assistant',
        content=result['clean_response'],
    )
    session.message_count = 1
    session.save()

    # 使用量カウントアップ
    user.monthly_sessions_used += 1
    user.save(update_fields=['monthly_sessions_used'])

    return Response({
        'session_id': session.id,
        'message': ConversationMessageSerializer(ai_message).data,
        'monthly_used': user.monthly_sessions_used,
        'monthly_limit': user.monthly_limit,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def send_message(request, session_id):
    """Send a message and get AI response."""
    try:
        session = ConversationSession.objects.get(id=session_id, user=request.user)
    except ConversationSession.DoesNotExist:
        return Response({'error': 'Session not found.'}, status=404)

    user_content = request.data.get('content', '').strip()
    if not user_content:
        return Response({'error': 'Message content is required.'}, status=400)

    # ── セッション内10ターン上限チェック（サーバーサイド強制） ──
    user_turns = session.messages.filter(role='user').count()
    if user_turns >= MAX_TURNS_PER_SESSION:
        return Response({
            'error': 'session_turn_limit_reached',
            'message': f'1セッションの発言上限（{MAX_TURNS_PER_SESSION}回）に達しました。新しいセッションを開始してください。',
            'turns_used': user_turns,
            'turns_limit': MAX_TURNS_PER_SESSION,
        }, status=status.HTTP_400_BAD_REQUEST)

    # Save user message
    user_message = ConversationMessage.objects.create(
        session=session,
        role='user',
        content=user_content,
    )

    # Build message history for OpenAI
    history = []
    for msg in session.messages.all():
        history.append({'role': msg.role, 'content': msg.content})

    # ── ユーザー記憶を取得 ──
    memory, _ = UserMemory.objects.get_or_create(user=request.user)
    memory_context = memory.to_context_string()

    # Get AI response
    result = chat_with_ai(
        history,
        avatar_name=session.avatar_name,
        accent=session.avatar_accent,
        topic=session.topic,
        level=request.user.level,
        memory_context=memory_context,
    )

    # Handle correction
    correction = result.get('correction')
    has_mistake = False

    if correction and correction.get('has_mistake'):
        has_mistake = True
        user_message.has_mistake = True
        user_message.corrected_content = correction.get('corrected', '')
        user_message.save()

        # Save to mistakes collection
        Mistake.objects.create(
            user=request.user,
            session=session,
            original_text=correction.get('original', user_content),
            corrected_text=correction.get('corrected', ''),
            explanation=correction.get('explanation', ''),
            advice_ja=correction.get('advice_ja', ''),
            level_up=correction.get('level_up', ''),
            useful_phrases=correction.get('useful_phrases', []),
            mistake_type=correction.get('mistake_type', 'grammar'),
            is_unnatural_only=bool(correction.get('is_unnatural_only', False)),
            context=user_content,
        )
        session.mistake_count += 1

    # Save AI response
    ai_message = ConversationMessage.objects.create(
        session=session,
        role='assistant',
        content=result['clean_response'],
    )

    # Update session stats
    session.message_count += 2
    session.save()

    # Generate TTS audio if requested
    audio_data = None
    if request.data.get('include_audio', False):
        try:
            voice_map = {'American': 'nova', 'British': 'onyx', 'Australian': 'shimmer'}
            voice = voice_map.get(session.avatar_accent, 'nova')
            audio_bytes = text_to_speech(result['clean_response'], voice=voice)
            audio_data = base64.b64encode(audio_bytes).decode('utf-8')
        except Exception:
            pass

    coaching = result.get('coaching')

    # coaching の便利フレーズをフレーズ帳に自動保存
    try:
        if coaching and coaching.get('useful_phrases'):
            for p in coaching['useful_phrases']:
                english = p.get('english', '').strip()
                if english and not SavedPhrase.objects.filter(user=request.user, english__iexact=english).exists():
                    SavedPhrase.objects.create(
                        user=request.user,
                        session=session,
                        english=english,
                        japanese=p.get('japanese', ''),
                        context_ja=coaching.get('tip_ja', ''),
                        source='coaching',
                        session_topic=session.topic,
                    )
    except Exception:
        pass  # フレーズ保存の失敗が会話レスポンス全体を壊さないようにする

    return Response({
        'user_message': ConversationMessageSerializer(user_message).data,
        'ai_message': ConversationMessageSerializer(ai_message).data,
        'correction': correction if has_mistake else None,
        'coaching': coaching,
        'audio_base64': audio_data,
    })


@api_view(['POST'])
def end_session(request, session_id):
    """End a session and generate summary."""
    try:
        session = ConversationSession.objects.get(id=session_id, user=request.user)
    except ConversationSession.DoesNotExist:
        return Response({'error': 'Session not found.'}, status=404)

    # Calculate duration
    duration = int((timezone.now() - session.created_at).total_seconds() / 60)
    session.duration_minutes = max(1, duration)
    session.is_active = False
    session.ended_at = timezone.now()
    session.save()

    # Update user stats
    user = request.user
    user.total_conversations += 1
    user.total_minutes += session.duration_minutes

    # Update streak
    today = timezone.now().date()
    if user.last_active_date:
        days_diff = (today - user.last_active_date).days
        if days_diff == 1:
            user.streak_days += 1
        elif days_diff > 1:
            user.streak_days = 1
    else:
        user.streak_days = 1
    user.last_active_date = today
    user.save()

    # Generate summary
    messages = [
        {'role': msg.role, 'content': msg.content}
        for msg in session.messages.all()
    ]
    # ミスデータを渡して客観的採点を可能にする
    mistake_qs = Mistake.objects.filter(session=session)
    mistake_data = [
        {
            'mistake_type': m.mistake_type,
            'is_unnatural_only': m.is_unnatural_only,
        }
        for m in mistake_qs
    ]
    summary = generate_conversation_summary(messages, mistake_data)

    # ── ユーザー記憶を非同期的に更新（失敗しても無視） ──
    try:
        memory, _ = UserMemory.objects.get_or_create(user=user)
        updates = update_user_memory(messages, memory)
        if updates:
            for field, value in updates.items():
                if value and hasattr(memory, field):
                    setattr(memory, field, value)
            # トピックを記録
            topics = list(memory.topics_discussed) if memory.topics_discussed else []
            topic_label = session.topic
            if topic_label not in topics:
                topics.append(topic_label)
            memory.topics_discussed = topics[-20:]  # 最新20件のみ保持
            memory.session_count += 1
            memory.save()
    except Exception:
        pass

    # ── サマリーの便利フレーズをフレーズ帳に自動保存 ──
    try:
        if summary.get('useful_phrases'):
            for p in summary['useful_phrases']:
                english = p.get('english', '').strip()
                if english and not SavedPhrase.objects.filter(user=user, english__iexact=english).exists():
                    SavedPhrase.objects.create(
                        user=user,
                        session=session,
                        english=english,
                        japanese=p.get('japanese', ''),
                        context_ja=p.get('context_ja', ''),
                        source='summary',
                        session_topic=session.topic,
                    )
    except Exception:
        pass

    return Response({
        'session': ConversationSessionSerializer(session).data,
        'summary': summary,
    })


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def transcribe_audio_view(request):
    """Transcribe audio file using Whisper. language param: 'en' (default) or 'ja'."""
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return Response({'error': 'Audio file is required.'}, status=400)

    language = request.data.get('language', 'en')

    try:
        audio_io = io.BytesIO(audio_file.read())
        audio_io.name = audio_file.name or 'recording.m4a'
        if language == 'ja':
            text = transcribe_audio_ja(audio_io)
        else:
            text = transcribe_audio(audio_io)
        return Response({'text': text})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def translate_japanese_to_english(request):
    """日本語テキストを英語に翻訳してアドバイスを返す。"""
    japanese_text = request.data.get('text', '').strip()
    if not japanese_text:
        return Response({'error': 'テキストを入力してください。'}, status=400)
    try:
        result = japanese_to_english(japanese_text)
        return Response(result)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def synthesize_speech(request):
    """Convert text to speech."""
    text = request.data.get('text', '')
    voice = request.data.get('voice', 'nova')

    if not text:
        return Response({'error': 'Text is required.'}, status=400)

    try:
        audio_bytes = text_to_speech(text, voice=voice)
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        return Response({'audio_base64': audio_base64, 'format': 'mp3'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def session_detail(request, session_id):
    try:
        session = ConversationSession.objects.get(id=session_id, user=request.user)
        return Response(ConversationSessionSerializer(session).data)
    except ConversationSession.DoesNotExist:
        return Response({'error': 'Not found.'}, status=404)
