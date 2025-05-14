module.exports = {
  apps: [
    {
      name: 'cvimprover-api-prod',
      script: '/var/www/html/venv/bin/gunicorn',
      args: 'cvimprover.wsgi:application --bind 0.0.0.0:8000 --workers 3',
      interpreter: 'none', // Use 'none' since you're running a binary script directly
      cwd: '/var/www/html/app/api',
      env: {
        NODE_ENV: 'production',
        DJANGO_SETTINGS_MODULE: 'cvimprover.settings',
        PYTHONPATH: '/var/www/html/app/api'
      }
    },
    {
      name: 'CeleryWorker',
      script: '/var/www/html/venv/bin/celery',
      args: '-A cvimprover worker --loglevel=info --concurrency=5 -P eventlet',
      cwd: '/var/www/html/app/api', // Ensure this matches your actual Django app dir (case-sensitive)
      interpreter: 'none', // You're using the virtualenv's celery binary, so 'none' works here too
      env: {
        DJANGO_SETTINGS_MODULE: 'cvimprover.settings',
        PYTHONPATH: '/var/www/html/app/api'
      }
    },
    {
      name: 'CeleryBeat',
      script: '/var/www/html/venv/bin/celery',
      args: '-A cvimprover beat --loglevel=info',
      cwd: '/var/www/html/app/api',
      interpreter: 'none',
      env: {
        DJANGO_SETTINGS_MODULE: 'cvimprover.settings',
        PYTHONPATH: '/var/www/html/app/api'
      }
    }
  ]
};
