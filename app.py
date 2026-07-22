from flask import Flask
from config import Config
from routes import chat_bp

app = Flask(__name__)
app.config.from_object(Config)

# Registramos el blueprint que contiene todas las rutas y lógica del chat
app.register_blueprint(chat_bp)

if __name__ == '__main__':
    app.run(debug=True)
    