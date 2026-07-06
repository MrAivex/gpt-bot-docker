import logging
import sys

def setup_logger():
    logger = logging.getLogger("gpt_bot")
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Лог в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Лог в файл (чтобы видеть, почему падал туннель ночью)
    file_handler = logging.FileHandler("bot_errors.log")
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()