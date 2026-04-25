import aiohttp
from logger_config import logger

class MaxBot:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://platform-api.max.ru" 

    async def send_message(self, chat_id, text, reply_markup=None):
        url = f"{self.base_url}/messages?chat_id={chat_id}"
        payload = {
            "text": text,
            "format": "markdown"
            }
        if reply_markup:
            payload["attachments"] = reply_markup
            
        headers = {"Authorization": self.token, "Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status in [200, 201]:
                        data = await resp.json()
                        # Пытаемся найти ID везде, где он может быть
                        msg_id = (
                            data.get('id') or 
                            data.get('message_id') or 
                            (data.get('message') and data.get('message').get('id')) or
                            (data.get('message') and data.get('message').get('body', {}).get('mid'))
                        )
                        
                        if msg_id:
                            logger.info(f"Заглушка отправлена, получен ID: {msg_id}")
                        else:
                            # Это поможет нам увидеть реальную структуру, если ID не найден
                            logger.error(f"ВНИМАНИЕ: ID не найден в ответе API: {data}")
                            
                        return msg_id
                    else:
                        logger.error(f"Ошибка API при отправке заглушки: {await resp.text()}")
                        return None
        except Exception as e:
            logger.error(f"Критическая ошибка в send_message: {e}")
            return None

    async def edit_message(self, chat_id, message_id, new_text):
        # Путь остается таким же (через параметры запроса)
        url = f"{self.base_url}/messages?chat_id={chat_id}&message_id={message_id}"
        
        # НОВАЯ СТРУКТУРА: убираем вложенность "message"
        # Большинство методов PUT в MAX API работают с прямой структурой тела сообщения
        payload = {
            "text": new_text,
            "format": "markdown" # или "html", если вы используете его
        }
        
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Используем PUT для редактирования
                async with session.put(url, json=payload, headers=headers) as resp:
                    res_text = await resp.text()
                    if resp.status in [200, 201, 204]:
                        logger.info(f"Сообщение {message_id} успешно изменено.")
                        return True
                    else:
                        # Если здесь в логах будет ошибка 400, значит API требует объект body
                        logger.warning(f"Ошибка правки ({resp.status}): {res_text}")
                        
                        # Запасной вариант, если плоская структура не подошла (некоторые версии API MAX)
                        fallback_payload = {"body": {"text": new_text}}
                        async with session.put(url, json=fallback_payload, headers=headers) as resp2:
                            if resp2.status in [200, 201, 204]:
                                return True
                        
                        return False
        except Exception as e:
            logger.error(f"Критическая ошибка при PUT-запросе: {e}")
            return False