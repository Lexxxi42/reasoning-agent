import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from tools import calculate_total_spending, convert_currency, get_obligations

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError(
        "GROQ_API_KEY не найден."
    )

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    groq_api_key=api_key,
)

tools = [calculate_total_spending, get_obligations, convert_currency]


def _build_system_prompt() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
        Ты — AI-ассистент платформы «Умный реестр подписок». Сегодня: {today}.

        Правило выбора действия:
            Если вопрос про общий расход, итог или сумму всех обязательств, сначала получи список подходящих обязательств, затем рассчитай общую сумму.
            Если вопрос про конкретную подписку, категорию или статус, получи только записи, подходящие под фильтры.
            Если нужно перевести одну сумму в другую валюту, выполни только конвертацию этой суммы.

        Правила ответа:
            Не выдумывай данные.
            Если данных нет, скажи об этом прямо.
            Если конвертация вернула ошибку, сообщи об ошибке.
            Если использовался запасной курс, предупреди об этом.
            Отвечай кратко и ясно.
            В конце кратко укажи, на каких данных основан ответ.
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
    print(f"\n{'='*70}\n👤 Вопрос: {question}\n{'='*70}")

    final_answer = None
    for step in agent.stream(
        {"messages": [HumanMessage(content=question)]},
        stream_mode="values",
    ):
        last_message = step["messages"][-1]

        tool_calls = getattr(last_message, "tool_calls", None)
        if tool_calls:
            for call in tool_calls:
                print(f"\n🧠 Thought: нужно вызвать инструмент, чтобы ответить точно.")
                print(f"🔧 Action: {call['name']}({call['args']})")
        elif last_message.type == "tool":
            print(f"👁️  Observation: {last_message.content}")
        elif last_message.type == "ai" and last_message.content:
            print(f"\n✅ Final Answer: {last_message.content}")
            final_answer = last_message.content

    print(f"{'='*70}\n")
    return final_answer or ""


if __name__ == "__main__":
    run_and_log("Сколько я потрачу в ближайшие 30 дней? Покажи итог в рублях.")
