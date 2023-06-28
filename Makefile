APP_NAME=app
PORT=7777

port:
	@echo $(PORT)

run:
	@echo "Running the application in normal mode..."
	python3 -m uvicorn --host 0.0.0.0 --port $(PORT) --workers 1 $(APP_NAME):app

debug:
	@echo "Running the application in debug mode..."
	python3 -m uvicorn --host 0.0.0.0 --port $(PORT) --workers 1 $(APP_NAME):app --reload

start:
	@echo "Starting the application..."
	nohup python3 -m uvicorn --host 0.0.0.0 --port $(PORT) --workers 1 $(APP_NAME):app &

status:
	@echo "Checking the application status..."
	ps -ef | grep uvicorn | grep -v grep | grep $(PORT)

stop:
	@echo "Stopping the application..."
	pkill -f "uvicorn.*$(PORT)"

restart:
	@echo "Restarting the application..."
	make stop; make start

ensure:
	@echo "Ensuring the app is alright..."
	make status || make start

style_check:
	@echo "Checking the code style..."
	python3 -m black --check .
	python3 -m isort --profile=black --check-only .

style:
	@echo "Applying the code style..."
	python3 -m black .
	python3 -m isort --profile=black .
