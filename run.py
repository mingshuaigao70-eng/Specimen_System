import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    if debug:
        app.run(host='0.0.0.0', port=8443, debug=True, threaded=True, ssl_context='adhoc')
    else:
        # 生产模式：建议使用 waitress 或 gunicorn
        # pip install waitress && waitress-serve --port=8443 run:app
        app.run(host='127.0.0.1', port=8443, debug=False, threaded=True) 