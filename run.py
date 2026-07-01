import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    if debug:
        app.run(host='0.0.0.0', port=8443, debug=True, threaded=True, ssl_context='adhoc')
    else:
        raise RuntimeError(
            'Production mode must run via a WSGI server. '
            'Use "waitress-serve --listen=127.0.0.1:8443 wsgi:app" or an equivalent gunicorn command.'
        )
