"""Test savollari. Har bir matn (uz, en, ru) tartibida.

Har bir savolga 10 tagacha variant qo'shish mumkin — "o" ro'yxatiga yangi
(uz, en, ru) juftligini qo'shishning o'zi yetarli. Variantlar tartibini
keyinchalik O'ZGARTIRMANG: javoblar variant indeksi bo'yicha saqlanadi.
"""

QUESTIONS = [
    {
        "q": ("Hobbilaringiz qaysilar?", "What are your hobbies?", "Какие у вас хобби?"),
        "o": [
            ("Kitob o'qish", "Reading", "Чтение"),
            ("Sport", "Sports", "Спорт"),
            ("Musiqa", "Music", "Музыка"),
            ("Kino va seriallar", "Movies & series", "Кино и сериалы"),
            ("Video o'yinlar", "Video games", "Видеоигры"),
            ("Sayohat", "Travel", "Путешествия"),
            ("Rasm chizish va san'at", "Drawing & art", "Рисование и искусство"),
            ("Pazandachilik", "Cooking", "Кулинария"),
        ],
    },
    {
        "q": ("Qaysi sport turlari sizga yoqadi?", "Which sports do you like?", "Какие виды спорта вам нравятся?"),
        "o": [
            ("Futbol", "Football", "Футбол"),
            ("Yugurish", "Running", "Бег"),
            ("Suzish", "Swimming", "Плавание"),
            ("Sport zali", "Gym", "Тренажёрный зал"),
            ("Yakkakurash", "Martial arts", "Единоборства"),
            ("Velosiped", "Cycling", "Велоспорт"),
            ("Shaxmat", "Chess", "Шахматы"),
            ("Tennis", "Tennis", "Теннис"),
        ],
    },
    {
        "q": ("Qanday musiqa tinglaysiz?", "What music do you listen to?", "Какую музыку вы слушаете?"),
        "o": [
            ("Pop", "Pop", "Поп"),
            ("Rap / Hip-hop", "Rap / Hip-hop", "Рэп / Хип-хоп"),
            ("Rok", "Rock", "Рок"),
            ("Klassik musiqa", "Classical", "Классика"),
            ("Milliy va xalq musiqasi", "Traditional & folk", "Народная и национальная"),
            ("Elektron musiqa", "Electronic", "Электронная"),
            ("Jazz", "Jazz", "Джаз"),
            ("Lo-fi / Chill", "Lo-fi / Chill", "Lo-fi / Чилл"),
        ],
    },
    {
        "q": (
            "Bo'sh vaqtingizni qanday o'tkazishni yoqtirasiz?",
            "How do you like to spend your free time?",
            "Как вы любите проводить свободное время?",
        ),
        "o": [
            ("Uyda dam olish", "Relaxing at home", "Отдых дома"),
            ("Do'stlar bilan uchrashish", "Meeting friends", "Встречи с друзьями"),
            ("Tabiatga chiqish", "Going out into nature", "Прогулки на природе"),
            ("Yangi narsa o'rganish", "Learning something new", "Изучение нового"),
            ("Sport bilan shug'ullanish", "Doing sports", "Занятия спортом"),
            ("Ijod bilan shug'ullanish", "Being creative", "Творчество"),
            ("Sayohat qilish", "Travelling", "Путешествия"),
            ("Loyiha ustida ishlash", "Working on projects", "Работа над проектами"),
        ],
    },
    {
        "q": ("Qaysi xususiyatlar sizga xos?", "Which traits describe you?", "Какие качества вам свойственны?"),
        "o": [
            ("Muloqotchan", "Sociable", "Общительный"),
            ("Xotirjam", "Calm", "Спокойный"),
            ("Hazilkash", "Funny", "С чувством юмора"),
            ("Tashabbuskor", "Proactive", "Инициативный"),
            ("Sabrli", "Patient", "Терпеливый"),
            ("Mas'uliyatli", "Responsible", "Ответственный"),
            ("Jiddiy", "Serious", "Серьёзный"),
            ("Ijodkor", "Creative", "Творческий"),
        ],
    },
    {
        "q": (
            "Do'stlikda nimani eng muhim deb bilasiz?",
            "What matters most to you in friendship?",
            "Что для вас важнее всего в дружбе?",
        ),
        "o": [
            ("Sodiqlik", "Loyalty", "Верность"),
            ("Halollik", "Honesty", "Честность"),
            ("Hazil tuyg'usi", "Sense of humor", "Чувство юмора"),
            ("O'zaro qo'llab-quvvatlash", "Mutual support", "Поддержка"),
            ("Umumiy qiziqishlar", "Shared interests", "Общие интересы"),
            ("Ochiq muloqot", "Open communication", "Открытое общение"),
            ("Birga vaqt o'tkazish", "Spending time together", "Совместное время"),
            ("Shaxsiy makonga hurmat", "Respect for personal space", "Уважение личных границ"),
        ],
    },
    {
        "q": ("Hayotdagi maqsadlaringiz?", "What are your life goals?", "Ваши жизненные цели?"),
        "o": [
            ("Kasbiy muvaffaqiyat", "Career success", "Карьерный успех"),
            ("Oila", "Family", "Семья"),
            ("Bilim olish", "Education & knowledge", "Образование и знания"),
            ("Moliyaviy mustaqillik", "Financial independence", "Финансовая независимость"),
            ("Sog'lom hayot", "Healthy lifestyle", "Здоровый образ жизни"),
            ("Dunyo bo'ylab sayohat", "Travelling the world", "Путешествия по миру"),
            ("Ijod va o'zini ifodalash", "Creativity & self-expression", "Творчество и самовыражение"),
            ("Boshqalarga yordam berish", "Helping others", "Помощь другим"),
        ],
    },
    {
        "q": ("Qaysi sohalar qiziqtiradi?", "Which fields interest you?", "Какие сферы вас интересуют?"),
        "o": [
            ("Dasturlash", "Programming", "Программирование"),
            ("Sun'iy intellekt", "Artificial intelligence", "Искусственный интеллект"),
            ("Biznes va tadbirkorlik", "Business", "Бизнес"),
            ("Tibbiyot", "Medicine", "Медицина"),
            ("Tillar", "Languages", "Языки"),
            ("Tarix va madaniyat", "History & culture", "История и культура"),
            ("Dizayn", "Design", "Дизайн"),
            ("Psixologiya", "Psychology", "Психология"),
        ],
    },
    {
        "q": (
            "Ovqat va turmush tarzida nimalar yoqadi?",
            "What do you enjoy in food and lifestyle?",
            "Что вам нравится в еде и образе жизни?",
        ),
        "o": [
            ("Milliy taomlar", "National cuisine", "Национальная кухня"),
            ("Fast-food", "Fast food", "Фастфуд"),
            ("Sog'lom ovqatlanish", "Healthy eating", "Здоровое питание"),
            ("Shirinliklar", "Sweets & desserts", "Сладости и десерты"),
            ("Qahva va kafelar", "Coffee & cafés", "Кофе и кафе"),
            ("Choyxona suhbatlari", "Tea-house conversations", "Посиделки в чайхане"),
            ("Uyda pishirish", "Home cooking", "Домашняя готовка"),
            ("Yangi taomlarni sinash", "Trying new dishes", "Пробовать новые блюда"),
        ],
    },
    {
        "q": ("Muloqot uslubingiz qanday?", "What is your communication style?", "Каков ваш стиль общения?"),
        "o": [
            ("Ko'p gaplashaman", "I talk a lot", "Я много говорю"),
            ("Ko'proq tinglayman", "I mostly listen", "Я больше слушаю"),
            ("Chuqur suhbatlarni yoqtiraman", "I like deep conversations", "Люблю глубокие разговоры"),
            ("Hazil-mutoyibani yoqtiraman", "I like jokes and banter", "Люблю шутки"),
            ("Kichik guruhlarni afzal ko'raman", "I prefer small groups", "Предпочитаю небольшие компании"),
            ("Katta kompaniyalarni yoqtiraman", "I enjoy big crowds", "Люблю большие компании"),
            ("Yozishmani afzal ko'raman", "I prefer texting", "Предпочитаю переписку"),
            ("Jonli uchrashuvni afzal ko'raman", "I prefer meeting in person", "Предпочитаю живые встречи"),
        ],
    },
]
