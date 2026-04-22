# FlightHub 2027 ✈️

[English](#english) | [עברית](#hebrew) | [Русский](#russian)

---

<a name="english"></a>
## English

**Advanced Flight Monitoring & Search Dashboard**

FlightHub is a premium, mobile-first web application designed to help travelers find and monitor the best flight deals. It features a modern "Airline Dashboard" aesthetic with glassmorphism and real-time updates.

### Key Features
- **Smart Search:** Flexible filters for stops, layover duration, and dates.
- **Real-time Progress:** Live updates via Server-Sent Events (SSE).
- **Price Monitoring:** Automated background checks with Telegram notifications.
- **Search History:** Persistent storage of your previous searches.
- **Currency Conversion:** Real-time ILS to USD conversion.
- **Mobile First:** Optimized for mobile devices with a bottom navigation bar.

### Tech Stack
- **Backend:** FastAPI (Python)
- **Database:** SQLite
- **Automation:** Telegram Bot API
- **Frontend:** Vanilla JS, CSS (Premium Dark Theme)

### Setup
1. Install dependencies:
   ```bash
   uv sync
   ```
2. Configure `.env`:
   ```env
   APP_PASSWORD=your_password
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_id
   ```
3. Run the app:
   ```bash
   uv run uvicorn app:app --host 0.0.0.0 --port 8000
   ```

---

<a name="hebrew"></a>
## עברית

**דאשבורד מתקדם לחיפוש וניטור טיסות**

FlightHub היא אפליקציית ווב מתקדמת, מותאמת לנייד, שנועדה לעזור למטיילים למצוא ולנטר את עסקאות הטיסה הטובות ביותר. האפליקציה כוללת עיצוב "Airline Dashboard" מודרני עם אפקטים של זכוכית ועדכונים בזמן אמת.

### תכונות עיקריות
- **חיפוש חכם:** פילטרים גמישים לעצירות, משך עצירת ביניים ותאריכים.
- **התקדמות בזמן אמת:** עדכונים חיים דרך Server-Sent Events (SSE).
- **ניטור מחירים:** בדיקות רקע אוטומטיות עם התראות בטלגרם.
- **היסטוריית חיפושים:** אחסון קבוע של החיפושים הקודמים שלך.
- **המרת מטבע:** המרה בזמן אמת מ-ILS ל-USD.
- **מותאם לנייד:** אופטימיזציה למכשירים ניידים עם סרגל ניווט תחתון.

### טכנולוגיות
- **Backend:** FastAPI (Python)
- **מסד נתונים:** SQLite
- **אוטומציה:** Telegram Bot API
- **Frontend:** Vanilla JS, CSS (עיצוב פרימיום כהה)

---

<a name="russian"></a>
## Русский

**Продвинутая панель мониторинга и поиска авиабилетов**

FlightHub — это премиальное веб-приложение, ориентированное на мобильные устройства, разработанное для поиска и мониторинга лучших предложений по перелетам. Оно выполнено в современном стиле "Airline Dashboard" с использованием эффектов матового стекла и обновлений в реальном времени.

### Основные функции
- **Умный поиск:** Гибкие фильтры по количеству пересадок, длительности стыковок и датам.
- **Прогресс в реальном времени:** Живые обновления через Server-Sent Events (SSE).
- **Мониторинг цен:** Автоматические фоновые проверки с уведомлениями в Telegram.
- **История поисков:** Постоянное хранение ваших предыдущих запросов.
- **Конвертация валют:** Пересчет из шекелей (ILS) в доллары (USD) в реальном времени.
- **Мобильный интерфейс:** Оптимизация для смартфонов с нижней панелью навигации.

### Технологии
- **Backend:** FastAPI (Python)
- **База данных:** SQLite
- **Автоматизация:** Telegram Bot API
- **Frontend:** Vanilla JS, CSS (Премиальная темная тема)
