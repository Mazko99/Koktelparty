from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import sqlite3, os

from admin.routes import admin_bp

app = Flask(__name__)
app.secret_key = 'supersecretkey123'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.permanent_session_lifetime = timedelta(days=7)

def get_db():
    return sqlite3.connect('users.db')

app.register_blueprint(admin_bp, url_prefix='/admin')

@app.before_request
def update_last_seen():
    session.permanent = True
    if "username" in session:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET last_seen = ? WHERE username = ?", (datetime.utcnow().isoformat(), session["username"]))
        conn.commit()
        conn.close()

@app.route('/')
def index():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "adminpass":
            session.permanent = True
            session['username'] = "admin"
            session['is_admin'] = True
            return redirect('/admin')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session.permanent = True
            session['username'] = username
            session['is_admin'] = False
            return redirect('/home')
        else:
            return render_template('login.html', error='Невірний логін або пароль')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        default_avatar = 'static/Sample_User_Icon.png'

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        if cursor.fetchone():
            conn.close()
            return render_template('register.html', error='Користувач вже існує.')
        cursor.execute("INSERT INTO users (username, password, name, avatar, is_verified) VALUES (?, ?, ?, ?, ?)",
                       (username, password, name, default_avatar, 0))
        conn.commit()
        conn.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect('/login')
    return render_template('home.html', username=session['username'])

@app.route('/profiles')
def profiles():
    if 'username' not in session:
        return redirect('/login')
    conn = get_db()
    cursor = conn.cursor()
    # Показати всіх, хто має visible=1
    cursor.execute("SELECT username, name, avatar, is_verified FROM users WHERE visible = 1")
    users = cursor.fetchall()
    conn.close()
    return render_template('profiles.html', users=users)

@app.route('/profile')
def my_profile():
    if 'username' not in session:
        return redirect('/login')
    return redirect(f'/profile/{session["username"]}')

@app.route('/profile/<username>')
def profile(username):
    if 'username' not in session:
        return redirect('/login')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return "Користувача не знайдено", 404
    cursor.execute("SELECT id FROM users WHERE username=?", (username,))
    user_id = cursor.fetchone()[0]
    cursor.execute("SELECT id, title, description, price, image_filename FROM products WHERE user_id=?", (user_id,))
    products = cursor.fetchall()
    conn.close()
    user_folder = os.path.join('static', 'uploads', username)
    photos = os.listdir(user_folder) if os.path.exists(user_folder) else []
    return render_template('profile.html', user=user, username=username, photos=photos, products=products)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return redirect('/login')
    username = session['username']
    description = request.form.get('description', '')
    category = request.form.get('category', 'Без категорії')
    city = request.form.get('city', '')
    visible = int(request.form.get('visible', 0))
    avatar_file = request.files.get('avatar')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET description = ?, category = ?, city = ?, visible = ? WHERE username = ?",
                   (description, category, city, visible, username))

    if avatar_file and avatar_file.filename:
        avatar_path = f"static/uploads/{username}_avatar.png"
        os.makedirs(os.path.dirname(avatar_path), exist_ok=True)
        avatar_file.save(avatar_path)
        cursor.execute("UPDATE users SET avatar = ? WHERE username = ?", (avatar_path, username))

    conn.commit()
    conn.close()
    return redirect(f'/profile/{username}')

@app.route('/category/<int:category_id>')
def category_view(category_id):
    if 'username' not in session:
        return redirect('/login')
    
    category_map = {
        1: 'Віртуальні моделі',
        2: 'Реальні моделі'
    }
    if category_id not in category_map:
        return "Невідома категорія", 404

    category_name = category_map[category_id]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, avatar, is_verified, city FROM users WHERE category = ? AND visible = 1", (category_name,))
    users = cursor.fetchall()
    conn.close()
    return render_template('virtual_models.html', users=users, category_name=category_name)

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'username' not in session:
        return redirect('/login')
    username = session['username']
    photo = request.files.get('photo')
    if not photo or photo.filename == '':
        flash('Файл не вибрано')
        return redirect(f'/profile/{username}')
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    if not allowed_file(photo.filename):
        flash('Неприпустимий формат')
        return redirect(f'/profile/{username}')
    filename = secure_filename(photo.filename)
    user_folder = os.path.join('static', 'uploads', username)
    os.makedirs(user_folder, exist_ok=True)
    if len(os.listdir(user_folder)) >= 10:
        flash('Максимум 10 фото')
        return redirect(f'/profile/{username}')
    photo.save(os.path.join(user_folder, filename))
    flash('Фото завантажено')
    return redirect(f'/profile/{username}')

@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    if 'username' not in session:
        return redirect('/login')
    username = session['username']
    filename = request.form.get('filename')
    user_folder = os.path.join('static', 'uploads', username)
    file_path = os.path.join(user_folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash('Фото видалено')
    return redirect(f'/profile/{username}')

@app.route('/chat_with/<username>', methods=['GET', 'POST'])
def chat_with(username):
    if 'username' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        msg = request.form['msg']
        sender = session['username']
        receiver = username
        cursor.execute("INSERT INTO private_messages (sender, receiver, msg) VALUES (?, ?, ?)", (sender, receiver, msg))
        conn.commit()

    cursor.execute("""
        SELECT sender, msg FROM private_messages
        WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)
        ORDER BY rowid ASC
    """, (session['username'], username, username, session['username']))
    messages = cursor.fetchall()
    conn.close()

    return render_template('private_chat.html', messages=messages, receiver=username)

if __name__ == '__main__':
    app.run(debug=True)
