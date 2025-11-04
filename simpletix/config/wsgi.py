"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import json
import subprocess
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# --- Force-load EB environment vars before Django settings ---
eb_env_path = Path("/opt/elasticbeanstalk/bin/get-config")

if eb_env_path.exists():
    try:
        output = subprocess.check_output(
            ["/opt/elasticbeanstalk/bin/get-config", "environment"]
        )
        env_data = json.loads(output.decode().strip())
        for k, v in env_data.items():
            os.environ.setdefault(k, v)
    except Exception as e:
        print(f"Failed to load EB environment variables: {e}")


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
