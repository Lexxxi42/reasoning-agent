import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from tools import calculate_total_spending, convert_currency, get_obligations, resolve_date_range

load_dotenv()

try:
    from langchain_groq import ChatGroq

    api_key = os.getenv("GROQ_API_KEY")

    if api_key:
        llm = ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0,
            groq_api_key=api_key,
        )

        print(f"Using Groq. Model {llm.model}")
    else:
        raise ValueError("GROQ_API_KEY не найден.")

except Exception:
    from langchain_ollama import ChatOllama

    llm = ChatOllama(
        model="llama3.1:8b",
        temperature=0,
    )

    print("Using local. Groq is unusable")

tools = [calculate_total_spending, get_obligations, convert_currency, resolve_date_range]


def _build_system_prompt() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
        Ты — AI-ассистент платформы «Умный реестр подписок». Сегодня: {today}.

        === ВЫБОР ИНСТРУМЕНТА ===
            ЕСЛИ вопрос касается ПЕРИОДА времени ("на этой неделе", "в ближайшие 30 дней",
            "в этом месяце", "в следующем месяце"):
        → СНАЧАЛА вызови resolve_date_range(period=...), чтобы получить start_date/end_date.
        → НИКОГДА не вычисляй даты периода самостоятельно в уме — ты часто ошибаешься
            в определении дня недели и границ месяца. Всегда используй этот инструмент.
        → Значения period: 'this_week', 'next_7_days', 'next_30_days', 'this_month', 'next_month'.

            ЕСЛИ пользователь спрашивает «сколько ВСЕГО потрачено» / «итого» / «общая сумма»
            (в целом или за период):
        → Используй calculate_total_spending() — один вызов, он всё посчитает внутри.
        → Если вопрос про период ("за 30 дней", "на этой неделе"), сначала вызови
            resolve_date_range, затем передай полученные start_date/end_date в
            calculate_total_spending.

            ЕСЛИ пользователь спрашивает о КОНКРЕТНОЙ подписке или фильтрует по категории:
        → Используй get_obligations() с нужными фильтрами (category, status, start_date, end_date)

            ЕСЛИ нужно конвертировать ОТДЕЛЬНУЮ сумму (не считаешь итог):
        → Используй convert_currency()

        === КРИТИЧНЫЕ ПРАВИЛА ===
        • НЕ ВЫЗЫВАЙ convert_currency много раз подряд — используй calculate_total_spending!
        • НЕ ВЫЧИСЛЯЙ границы недели/месяца сам — используй resolve_date_range!
        • Никогда не выдумывай данные — только через инструменты.
        • Если конвертация дала ошибку (поле "error") — честно сообщи об этом.
        • Отвечай кратко и ясно, но приветливо.
    """


agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=_build_system_prompt(),
)


def ask(question: str) -> str:
    """Отправляет вопрос агенту и возвращает финальный текстовый ответ."""
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content


def run_and_log(question: str) -> str:
    """То же, что ask(), но есть видимый трейс"""
    print(f"\n{'='*70}\nВопрос: {question}\n{'='*70}")

    final_answer = None
    for step in agent.stream(
        {"messages": [HumanMessage(content=question)]},
        stream_mode="values",
    ):
        last_message = step["messages"][-1]

        tool_calls = getattr(last_message, "tool_calls", None)
        if tool_calls:
            for call in tool_calls:
                print(f"\nThought: нужно вызвать инструмент, чтобы ответить точно.")
                print(f"Action: {call['name']}({call['args']})")
        elif last_message.type == "tool":
            print(f" Observation: {last_message.content}")
        elif last_message.type == "ai" and last_message.content:
            print(f"\nFinal Answer: {last_message.content}")
            final_answer = last_message.content

    print(f"{'='*70}\n")
    return final_answer or ""


if __name__ == "__main__":
    run_and_log("Сколько я потрачу в ближайшие 30 дней? Покажи итог в рублях.")
