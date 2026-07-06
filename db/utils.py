from config.logger import logger

class DBUtils:
    def __init__(self, pool):
        self.pool = pool

    async def _insert(self, table: str, **kwargs): # Универсально добавляет строку
        if not kwargs:
            return

        columns = list(kwargs.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        
        query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, *kwargs.values())
                logger.info(f"Запись успешно добавлена в таблицу {table}")
        except Exception as e:
            logger.error(f"Ошибка при добавлении в {table}: {e}")

    async def _update(self, table: str, record_id: int, id_col: str, **kwargs): # Универсально обновляет строки
        if not kwargs: return
        
        set_parts = [f"{key} = ${i+2}" for i, key in enumerate(kwargs.keys())]
        query = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {id_col} = $1"
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, record_id, *kwargs.values())
        except Exception as e:
            logger.error(f"Ошибка при обновлении {record_id}: {e}")

    async def _update_many(self, table: str, filters: dict, **updates):
        if not updates: return

        sql_functions = ['CURRENT_TIMESTAMP', 'NULL']
        set_parts = []
        values = []
        arg_idx = 1
        
        for key, val in updates.items():
            if isinstance(val, str) and val.upper() in sql_functions:
                set_parts.append(f"{key} = {val.upper()}")
            else:
                set_parts.append(f"{key} = ${arg_idx}")
                values.append(val)
                arg_idx += 1

        filter_parts = []
        for key, val in filters.items():
            if isinstance(val, dict): # Для сложных условий типа {'op': '<', 'val': ...}
                op = val.get('op', '=')
                v = val.get('val')
                if isinstance(v, str) and v.upper() in sql_functions:
                    filter_parts.append(f"{key} {op} {v.upper()}")
                else:
                    filter_parts.append(f"{key} {op} ${arg_idx}")
                    values.append(v)
                    arg_idx += 1
            else:
                filter_parts.append(f"{key} = ${arg_idx}")
                values.append(val)
                arg_idx += 1

        query = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {' AND '.join(filter_parts)}"

        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *values)
        except Exception as e:
            logger.error(f"Ошибка при массовом обновлении таблицы {table}: {e}")

    async def _get(self, table: str, record_id: int, id_col: str): # Универсально возвращает строку по условию
        query = f"SELECT * FROM {table} WHERE {id_col} = $1"

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, record_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка при получении для {record_id}: {e}")

    async def _fetch(self, table: str, columns: list = None, filters: dict = None, order_by: str = None, limit: int = None):
        cols_str = ", ".join(columns) if columns else "*"
        query = f"SELECT {cols_str} FROM {table}"
        params = []

        if filters:
            where_parts = []
            param_index = 1
            for key, value in filters.items():
                if value == "IS NOT NULL":
                    where_parts.append(f"{key} IS NOT NULL")
                elif value == "IS NULL":
                    where_parts.append(f"{key} IS NULL")
                
                elif isinstance(value, dict) and 'op' in value:
                    op = value['op']
                    where_parts.append(f"{key} {op} ${param_index}")
                    params.append(value['val'])
                    param_index += 1
                
                else:
                    where_parts.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1
            
            query += " WHERE " + " AND ".join(where_parts)

        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Ошибка динамического fetch в {table}: {e}")
            return []

    async def _count(self, table: str, filters: dict = None):
        query = f"SELECT COUNT(*) FROM {table}"
        params = []
        
        if filters:
            where_parts = []
            param_index = 1
            for key, value in filters.items():
                if value == "IS NOT NULL":
                    where_parts.append(f"{key} IS NOT NULL")
                elif value == "IS NULL":
                    where_parts.append(f"{key} IS NULL")
                else:
                    where_parts.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1
            
            query += " WHERE " + " AND ".join(where_parts)

        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval(query, *params) or 0
        except Exception as e:
            logger.error(f"Ошибка динамического подсчета в {table}: {e}")
            return 0
        
    async def _delete_many(self, table: str, filters: dict):
        if not filters: return False

        filter_parts = []
        values = []
        arg_idx = 1

        for key, val in filters.items():
            if isinstance(val, dict):
                op = val.get('op', '=')
                v = val.get('val')
                if isinstance(v, str) and ('NOW()' in v.upper() or 'INTERVAL' in v.upper()):
                    filter_parts.append(f"{key} {op} {v}")
                else:
                    filter_parts.append(f"{key} {op} ${arg_idx}")
                    values.append(v)
                    arg_idx += 1
            else:
                filter_parts.append(f"{key} = ${arg_idx}")
                values.append(val)
                arg_idx += 1

        query = f"DELETE FROM {table} WHERE {' AND '.join(filter_parts)}"
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, *values)
                return result
        except Exception as e:
            logger.error(f"Ошибка при массовом удалении в {table}: {e}")
            return False
        
    async def _bulk_update_limits(self, table: str, status_col: str, limit_col: str, config: dict):
        if not config:
            return

        case_parts = []
        for sub_type, settings in config.items():
            requests = settings.requests
            case_parts.append(f"WHEN {status_col} = '{sub_type}' THEN {requests}")

        case_sql = " ".join(case_parts)
        
        query = f"""
            UPDATE {table} 
            SET used_queries = 0,
                {limit_col} = CASE {case_sql} ELSE {limit_col} END,
                last_active = CURRENT_TIMESTAMP
            WHERE {status_col} != 'inactive'
        """

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query)
                logger.info(f"Массовое обновление {limit_col} в таблице {table} завершено.")
        except Exception as e:
            logger.error(f"Ошибка при bulk_update_limits в {table}: {e}")