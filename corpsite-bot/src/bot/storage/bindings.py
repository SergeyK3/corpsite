# MVP in-memory bindings: telegram_user_id -> user_id
# В проде замените на БД/Redis или backend-binding.
BINDINGS: dict[int, int] = {}
