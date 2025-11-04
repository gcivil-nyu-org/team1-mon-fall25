"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import json
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# --- Load Elastic Beanstalk environment variables manually if not already present ---
try:
    eb_env_path = Path(
        "/opt/elasticbeanstalk/deploy/configuration/containerconfiguration"
    )
    if eb_env_path.exists():
        with open(eb_env_path) as f:
            data = json.load(f)
        env_vars = data.get("container", {}).get("environment", {})

        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = value
except Exception as e:
    print(f"Warning: could not preload EB environment vars: {e}")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
