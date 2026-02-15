.PHONY: help run logs restart check test

help:
	@echo "Доступные команды:"
	@echo "  make run     - Запустить воркер локально"
	@echo "  make logs    - Посмотреть логи воркера"
	@echo "  make restart - Перезапустить воркер"
	@echo "  make check   - Проверить статус"
	@echo "  make test    - Отправить тестовое объявление"

run:
	python -m app.workers.moderation_worker

logs:
	docker-compose logs -f worker

restart:
	docker-compose restart worker

check:
	docker-compose ps worker
	docker-compose logs --tail=5 worker

test:
	curl -X POST http://localhost:8003/async_predict \
		-H "Content-Type: application/json" \
		-d "{\"item_id\": 1}"