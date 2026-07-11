import aiohttp
from config.logger import logger

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
                        
                        if not msg_id:
                            logger.error(f"ВНИМАНИЕ: ID не найден в ответе API: {data}")   
                            
                        return msg_id
                    else:
                        logger.error(f"Ошибка API при отправке заглушки: {await resp.text()}")
                        return None
        except Exception as e:
            logger.error(f"Критическая ошибка в send_message: {e}")
            return None

    async def edit_message(self, chat_id, message_id, new_text, reply_markup=None):
        # Путь остается таким же (через параметры запроса)
        url = f"{self.base_url}/messages?chat_id={chat_id}&message_id={message_id}"
        
        # НОВАЯ СТРУКТУРА: убираем вложенность "message"
        # Большинство методов PUT в MAX API работают с прямой структурой тела сообщения
        payload = {
            "text": new_text,
            "format": "markdown"
        }

        if reply_markup:
            payload["attachments"] = reply_markup
        
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
                        return True
                    else:
                        # Если здесь в логах будет ошибка 400, значит API требует объект body
                        logger.warning(f"Ошибка правки ({resp.status}): {res_text}")
                        
                        # Запасной вариант, если плоская структура не подошла (некоторые версии API MAX)
                        fallback_payload = {"body": {"text": new_text}}
                        if reply_markup:
                            fallback_payload["body"]["attachments"] = reply_markup
                        async with session.put(url, json=fallback_payload, headers=headers) as resp2:
                            if resp2.status in [200, 201, 204]:
                                return True
                        
                        return False
        except Exception as e:
            logger.error(f"Критическая ошибка при PUT-запросе: {e}")
            return False
        
    async def send_photo(self, chat_id: int, image_url: str, caption: str = None):
        url = f"{self.base_url}/messages?chat_id={chat_id}"
        
        attachment = {
            "type": "image",
            "payload": {"url": image_url}
        }
        
        payload = {
            "attachments": [attachment],
            "format": "markdown"
        }
        if caption:
            payload["text"] = caption
        
        headers = {"Authorization": self.token, "Content-Type": "application/json"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status in [200, 201]:
                        data = await resp.json()
                        msg_id = (
                            data.get('id') or 
                            data.get('message_id') or 
                            (data.get('message') or {}).get('id') or
                            (data.get('message', {}).get('body', {}) or {}).get('mid')
                        )
                        return msg_id
                    else:
                        logger.error(f"Ошибка при отправке фото: {await resp.text()}")
                        return None
        except Exception as e:
            logger.error(f"Ошибка send_photo: {e}")
            return None
        
    async def send_document(self, chat_id: int, file_content: str, caption: str = None):
        """
        Отправляет изображение через base64 (тип 'image').
        file_content – base64-строка без префикса data:image/...;base64,
        caption – подпись (опционально)
        """
        url = f"{self.base_url}/messages?chat_id={chat_id}"
        attachment = {
            "type": "image",
            "payload": {
                "content": file_content
            }
        }
        payload = {
            "attachments": [attachment],
            "format": "markdown"
        }
        if caption:
            payload["text"] = caption

        headers = {"Authorization": self.token, "Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status in [200, 201]:
                        data = await resp.json()
                        return data.get('id') or data.get('message_id')
                    else:
                        logger.error(f"Ошибка send_document: {await resp.text()}")
                        return None
        except Exception as e:
            logger.error(f"Ошибка send_document: {e}")
            return None
        

    async def check_channel_subscription(self, user_id: int, channel_id: int) -> bool:
        """
        Проверяет, подписан ли пользователь на канал.
        channel_id – ID канала (обычно отрицательный).
        Возвращает True, если подписан.
        """
        url = f"{self.base_url}/channels/{channel_id}/members/{user_id}"
        headers = {"Authorization": self.token}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Предполагаем, что в ответе есть поле status или member
                        return data.get("status") == "member" or data.get("member") is not None
                    else:
                        logger.warning(f"Ошибка проверки подписки: {resp.status} {await resp.text()}")
                        return False
        except Exception as e:
            logger.error(f"Ошибка check_channel_subscription: {e}")
            return False