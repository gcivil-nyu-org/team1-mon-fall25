"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# import os
# import json
# import subprocess
# from pathlib import Path
# import logging
# from django.core.files.storage import default_storage

# # Simple logger
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("wsgi_debug")

# # Log before loading EB env vars
# logger.info(
#     "BEFORE EB ENV LOAD, DEFAULT_FILE_STORAGE=%s",
#     os.environ.get("DEFAULT_FILE_STORAGE"),
# )
# logger.info("default_storage._wrapped=%r", default_storage._wrapped)


# # --- Force-load EB environment vars before Django settings ---
# eb_env_path = Path("/opt/elasticbeanstalk/bin/get-config")

# if eb_env_path.exists():
#     try:
#         output = subprocess.check_output(
#             ["/opt/elasticbeanstalk/bin/get-config", "environment"]
#         )
#         env_data = json.loads(output.decode().strip())
#         for k, v in env_data.items():
#             os.environ.setdefault(k, v)
#     except Exception as e:
#         print(f"Failed to load EB environment variables: {e}")


# # --- Set storage backend early ---
# ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

# if ENVIRONMENT in ["production", "development"]:
#     os.environ.setdefault(
#         "DEFAULT_FILE_STORAGE", "storages.backends.s3boto3.S3Boto3Storage"
#     )
#     os.environ.setdefault(
#         "AWS_STORAGE_BUCKET_NAME", os.getenv("AWS_MEDIA_BUCKET_NAME")
#     )
#     os.environ.setdefault("AWS_QUERYSTRING_AUTH", "True")
# else:
#     os.environ.setdefault(
#         "DEFAULT_FILE_STORAGE", "django.core.files.storage.FileSystemStorage"
#     )
#     os.environ.setdefault("MEDIA_URL", "/media/")


# # --- Clear any cached storage backend ---
# from django.core.files import storage as storage_module  # noqa: E402

# try:
#     storage_module.storages._storages.clear()
# except AttributeError:
#     storage_module.storages._storages = {}


# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# logger.info(
#     "AFTER EB ENV LOAD, DEFAULT_FILE_STORAGE=%s",
#     os.environ.get("DEFAULT_FILE_STORAGE")
# )
# logger.info("default_storage._wrapped=%r", default_storage._wrapped)

# from django.core.wsgi import get_wsgi_application  # noqa: E402

# application = get_wsgi_application()
