from agent import run_and_log

def run_agent() -> None:
    print("🤖 Агент запущен. Введите вопрос (или 'exit' для выхода):")
    while True:
        user_input = input("\n👤 Вы: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "выход"):
            print("👋 Пока!")
            break

        try:
            run_and_log(user_input)
        except Exception as exc:  # агент не должен ронять весь CLI
            print(f"❌ Произошла ошибка: {exc}")


if __name__ == "__main__":
    run_agent()
