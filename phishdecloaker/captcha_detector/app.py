import traceback

from flask import Flask, jsonify

from api_db import db
from api_main import main


def handle_exception(e: Exception):
    print(traceback.print_exc())
    return jsonify(message=str(e)), 400


app = Flask(__name__)
app.register_blueprint(main)
app.register_blueprint(db, url_prefix="/database")
app.register_error_handler(Exception, handle_exception)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
