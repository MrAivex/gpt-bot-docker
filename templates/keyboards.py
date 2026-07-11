# keyboards.py
from config.subscriptions import AVAILABLE_SUBSCRIPTIONS
from ai.providers import MODELS, DEFAULT_MODEL


class Keyboards:
    @staticmethod
    def menu_button_edit_msg():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{"type": "callback", "text": "📌 Меню", "payload": "show_main_menu_edit"}]]
            }
        }]
    
    @staticmethod
    def menu_button_new_msg():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{"type": "callback", "text": "📌 Меню", "payload": "show_main_menu_new"}]]
            }
        }]

    @staticmethod
    def main_menu():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {"type": "callback", "text": "🤖 Выбрать модель", "payload": "select_model"},
                        {"type": "callback", "text": "⚙️ Настройки", "payload": "settings"}],
                    [
                        {"type": "callback", "text": "🔧 Помощь", "payload": "support"},
                        {"type": "callback", "text": "🧩 Баланс", "payload": "my_queries"}],
                    [
                        {"type": "callback", "text": "🎁 Бесплатные пазлы 🧩", "payload": "free_puzzle"}]
                ]
            }
        }]
    
    @staticmethod
    def free_puzzle():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {"type": "callback", "text": "👥 Пригласить друга", "payload": "show_referal_link"}],
                    [
                        {"type": "callback", "text": "🎁 Подписаться на канал", "payload": "subscribe_channel"}],
                    [
                        {"type": "callback", "text": "📌 Меню", "payload": "show_main_menu_edit"}]
                ]
            }
        }]
    
    @staticmethod
    def settings():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {"type": "callback", "text": "⭐ Тарифы", "payload": "see_subscriptions"},
                        {"type": "callback", "text": "⭐ Мой тариф", "payload": "subscription_status"}],
                    [
                        {"type": "callback", "text": "📋 О боте", "payload": "about_bot"},
                        {"type": "callback", "text": "📌 Назад в меню", "payload": "show_main_menu_edit"}],
                    [
                        {"type": "callback", "text": "🧹 Удалить историю ИИ", "payload": "clear_ai_history"}],
                    [
                        {"type": "callback", "text": "❌ Удалить способ оплаты", "payload": "delete_pay_token"}]
                ]
            }
        }]
    
    @staticmethod
    def settings_button_new_msg():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{"type": "callback", "text": "⚙️ Назад в настройки", "payload": "show_main_menu_new"}]]
            }
        }]
    
    def settings_button_edit_msg():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{"type": "callback", "text": "⚙️ Назад в настройки", "payload": "show_main_menu_edit"}]]
            }
        }]

    @staticmethod
    def subscription_list():
        # динамическая клавиатура из доступных тарифов
        buttons_rows = []
        for sub_id, info in AVAILABLE_SUBSCRIPTIONS.items():
            buttons_rows.append([
                {"type": "callback", "text": f"{info.name}, {info.price} руб", "payload": f"buy_{sub_id}"}
            ])
        buttons_rows.append([{"type": "callback", "text": "📌 Меню", "payload": "show_main_menu_edit"}])
        return [{"type": "inline_keyboard", "payload": {"buttons": buttons_rows}}]
    
    @staticmethod
    def payment_keyboard(pay_url):
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "callback", "text": "Назад к подпискам", "payload": "see_subscriptions"}],
                    [{"type": "link", "text": "💳 Оплатить", "url": pay_url}]
                ]
            }
        }]
    
    @staticmethod
    def limit_exceeded():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{"type": "callback", "text": "Подписки", "payload": "see_subscriptions"}]]
            }
        }]
    
    @staticmethod
    def back_to_sub_list():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "callback", "text": "Назад к подпискам", "payload": "see_subscriptions"}]
                ]
            }
        }]
    
    @staticmethod
    def menu_and_sub_list_edit():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "callback", "text": "К подпискам", "payload": "see_subscriptions"}],
                    [{"type": "callback", "text": "📌 Меню", "payload": "show_main_menu_edit"}]
                ]
            }
        }]
    
    @staticmethod
    def models_menu(current_model: str = None):
        """
        Возвращает клавиатуру со списком моделей.
        Первой идёт DEFAULT_MODEL, затем остальные.
        current_model — модель, которая сейчас выбрана (будет отмечена ✅).
        """
        if current_model is None:
            current_model = DEFAULT_MODEL

        # Сортируем: сначала дефолтная, потом остальные по алфавиту
        model_ids = [DEFAULT_MODEL] + sorted([m for m in MODELS if m != DEFAULT_MODEL])
        buttons = []

        for model_id in model_ids:
            cfg = MODELS.get(model_id, {})
            model_name = cfg.get("kwargs", {}).get("model", model_id)  # можно заменить на читаемое имя
            cost = cfg.get("kwargs", {}).get("cost_per_request", 1)
            marker = "✅ " if model_id == current_model else ""
            buttons.append([
                {
                    "type": "callback",
                    "text": f"{marker}{model_name} — {cost}🧩 за запрос",
                    "payload": f"select_model_{model_id}"
                }
            ])
        buttons.append([{"type": "callback", "text": "📌 Меню", "payload": "show_main_menu_edit"}])

        return [{
            "type": "inline_keyboard",
            "payload": {"buttons": buttons}
        }]
    
    @staticmethod
    def check_subscription():
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "callback", "text": "✅ Проверить подписку", "payload": "check_subscription"}],
                    [{"type": "callback", "text": "📌 Меню", "payload": "show_main_menu_edit"}]
                ]
            }
        }]