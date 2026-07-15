# Умный реестр подписок — AI-агент

ReAct-агент на LangChain/LangGraph, который отвечает на вопросы о личных
подписках и платежах на естественном языке, вызывая инструменты для
получения данных и конвертации валют.

## Как запустить

### Вариант 1 — Docker

```bash
cp .env.example .env # предварительно вписать свой GROQ_API_KEY в .env
docker compose up --build
```

### Вариант 2 — локально

```bash
pip install -r requirements.txt
cp .env.example .env # предварительно вписать свой GROQ_API_KEY в .env
python main.py
```

### Тесты

```bash
pip install -r requirements.txt
pytest test_tools.py -v
```

## Какой LLM выбран и почему

**Groq (`openai/gpt-oss-20b` через Groq API)**.

- Бесплатный, с щедрыми лимитами и достаточно умными ответами.
- Очень низкая задержка инференса, что критично для агентного цикла:
  один вопрос пользователя может потребовать 2-4 последовательных вызова модели.
- Модель `gpt-oss-20b` достаточно хорошо следует инструкциям.
- Архитектура инструментов (`tools.py`) не завязана на конкретного
  провайдера — заменить `ChatGroq` на `ChatOpenAI`/`ChatAnthropic` можно,
  поменяв только конструктор `llm` в `agent.py`.

## Оптимизация и предотвращение зацикливания

На free-tier Groq ограничение 8000 TPM. Чтобы агент не зацикливался на множественных 
вызовах `convert_currency` (по одному на каждую подписку), в `tools.py` добавлен инструмент
**`calculate_total_spending()`** — он:

- Получает список подписок один раз
- Конвертирует каждую в целевую валюту внутри себя
- Возвращает готовый итог + breakdown по валютам

Это снижает количество LLM-циклов до одного вызова.
System prompt явно указывает агенту: «для вопросов "сколько всего" используй 
`calculate_total_spending`, а не цикл по convert_currency».

## Инструменты агента

**1. `calculate_total_spending(target_currency='RUB', category=None, status='active')`**
   - Быстрый способ получить общую сумму расходов в целевой валюте.
   - Внутри вызывает `get_obligations` и `convert_currency`, но агенту не нужно знать
     об этом — он просто получает итог.
   - Используется для вопросов типа "сколько я потрачу всего", "итого в рублях".

**2. `get_obligations(status=None, category=None, start_date=None, end_date=None)`**
   - Возвращает список обязательств (подписок/платежей) с фильтрацией.
   - Используется для детальных вопросов: "какие подписки есть", "какая категория самая дорогая".

**3. `convert_currency(amount, from_currency, to_currency)`**
   - Конвертирует отдельную сумму между валютами через frankfurter.app API.
   - Используется редко (обычно инкапсулирована в `calculate_total_spending`),
<<<<<<< HEAD
     но доступна для специальных случаев.

## Пример ответа на вопрос с логгированием

Using Groq. Model openai/gpt-oss-20b

Агент запущен. Введите вопрос (или 'exit' для выхода):

Вы: Есть ли у меня платежи на этой неделе?

Вопрос: Есть ли у меня платежи на этой неделе?

Thought: нужно вызвать инструмент, чтобы ответить точно.

Action: resolve_date_range({'period': 'this_week'})
 Observation: {"start_date": "2026-07-13", "end_date": "2026-07-19", "today": "2026-07-15"}

Thought: нужно вызвать инструмент, чтобы ответить точно.

Action: get_obligations({'end_date': '2026-07-19', 'start_date': '2026-07-13'})
 Observation: [{"id": "1f4d1d1e-0a6d-4b5f-8d9d-4e7a6f0c1003", "title": "Yandex Plus", "amount": 799, "currency": "RUB", "category": "subscription", "next_payment_date": "2026-07-14", "status": "active"}, {"id": "1f4d1d1e-0a6d-4b5f-8d9d-4e7a6f0c1006", "title": "iCloud+", "amount": 0.99, "currency": "USD", "category": "storage", "next_payment_date": "2026-07-18", "status": "active"}, {"id": "1f4d1d1e-0a6d-4b5f-8d9d-4e7a6f0c1011", "title": "Miro", "amount": 8, "currency": "USD", "category": "productivity", "next_payment_date": "2026-07-15", "status": "paused"}, {"id": "1f4d1d1e-0a6d-4b5f-8d9d-4e7a6f0c1012", "title": "Figma", "amount": 15, "currency": "USD", "category": "design", "next_payment_date": "2026-07-19", "status": "active"}]

Final Answer: Да, у вас есть платежи на этой неделе.

**Три активных платежа**:

| Подписка | Сумма | Валюта | Дата списания |
|----------|-------|--------|---------------|
| Yandex Plus | 799 ₽ | 2026‑07‑14 |
| iCloud+ | 0.99 USD | 2026‑07‑18 |
| Figma | 15 USD | 2026‑07‑19 |

(Подписка Miro находится в статусе «paused» и не будет списана.)

## Мотивационное письмо
### 1

### 2

### 3
До начала сентябра я готова уделять проекту 40 часов в неделю и полностью свободна, далее по 20-30 часов. Ограничений на срок у меня нет.