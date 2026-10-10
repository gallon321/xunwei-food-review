"""Compatibility entry point: python app.py or flask --app app commands."""
from xunwei import create_app
from xunwei.db import get_db, init_db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=False, host="127.0.0.1", port=5000)
