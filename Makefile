mongo-up:
	docker-compose -f docker-compose-dev.yaml up mongo -d
dev-up:
	docker-compose --env-file .env.docker -f docker-compose-dev.yaml up -d --build
up:
	docker-compose --env-file .env.docker up -d --build