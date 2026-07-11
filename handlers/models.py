# handlers/models.py

class Update:
    def __init__(self, data: dict):
        self.raw = data
        update_type = data.get('update_type') or data.get('type')
        self.type = update_type

        self.message_id = None
        
        if update_type == 'bot_started':
            self.user_id = int(data.get('user', {}).get('user_id', 0))
            self.chat_id = int(data.get('chat_id', 0))
        elif update_type == 'message_created':
            msg = data.get('message', {})
            self.user_id = int(msg.get('sender', {}).get('user_id', 0))
            self.chat_id = int(msg.get('recipient', {}).get('chat_id') or msg.get('chat_id', 0))
            self.message_id = msg.get('body', {}).get('mid')
        elif update_type == 'message_callback':
            cb = data.get('callback', {})
            self.user_id = int(cb.get('user', {}).get('user_id', 0))
            msg = data.get('message', {})
            self.chat_id = int(msg.get('recipient', {}).get('chat_id') or msg.get('chat_id', 0))
            self.message_id = msg.get('body', {}).get('mid')
        else:
            # fallback на старую логику (на всякий случай)
            self.user_id = int(
                data.get('user', {}).get('user_id') or
                data.get('message', {}).get('sender', {}).get('user_id') or
                data.get('callback', {}).get('user', {}).get('user_id') or
                0
            )
            self.chat_id = int(
                data.get('message', {}).get('chat_id') or
                data.get('message', {}).get('recipient', {}).get('chat_id') or 0
            )

        # Остальные поля (text, attachments и т.д.) оставь как были
        msg_obj = data.get('message', {})
        self.text = msg_obj.get('text') or msg_obj.get('body', {}).get('text', '')
        self.attachments = msg_obj.get('attachments') or msg_obj.get('body', {}).get('attachments', [])
        self.callback_payload = data.get('callback', {}).get('payload', '')
        ts_ms = data.get('timestamp') or msg_obj.get('timestamp', 0)
        self.timestamp = ts_ms / 1000 if ts_ms else 0

    @property
    def is_valid(self) -> bool:
        return bool(self.user_id and self.chat_id)

    @property
    def intent(self) -> str:
        return (self.text or self.callback_payload or "").strip().lower()