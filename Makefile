.PHONY: setup test lint lxc deploy clean

# Variables
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff
CONTAINER_ID = 1083
DEPLOY_USER = root
DEPLOY_HOST = 192.168.1.83

# Setup virtual environment and install dependencies
setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install pytest ruff pure25519

# Run tests
test:
	$(PYTEST)

# Run linter
lint:
	$(RUFF) check .

# Create LXC container on Proxmox
lxc:
	sudo bash deploy/lxc_setup.sh

# Deploy to LXC container
deploy:
	@echo "Deploying to $(DEPLOY_HOST)..."
	@mkdir -p server/boards
	rsync -avz --exclude 'boards/*' --exclude '$(VENV)' --exclude '.git' \
		. $(DEPLOY_USER)@$(DEPLOY_HOST):/opt/spring83/
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "chmod +x /opt/spring83/deploy/cron/cleanup.sh"
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "cp /opt/spring83/server/service/spring83.service /etc/systemd/system/"
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "cp /opt/spring83/deploy/Caddyfile /etc/caddy/Caddyfile"
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "systemctl daemon-reload"
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "systemctl enable spring83.service"
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "systemctl restart spring83.service"
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "systemctl reload caddy"
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "echo '0 0 * * * /opt/spring83/deploy/cron/cleanup.sh' | crontab -"
	@echo "Deployment complete!"

# Clean up generated files
clean:
	rm -rf $(VENV) __pycache__ .pytest_cache
	find . -name "*.pyc" -delete