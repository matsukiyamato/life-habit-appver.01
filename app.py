import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///life_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- データベースモデル ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    habits = db.relationship('Habit', backref='owner', lazy=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    frequency = db.Column(db.String(50))
    start_date = db.Column(db.Date, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    logs = db.relationship('HabitLog', backref='parent_habit', lazy=True, cascade="all, delete-orphan")

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date())
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ルート定義 ---

@app.route('/')
@login_required
def home():
    now = datetime.now()
    wdays = ["月", "火", "水", "木", "金", "土", "日"]
    date_str = now.strftime(f'%m月%d日 ({wdays[now.weekday()]})')
    hour = now.hour
    greeting = "おはよう" if 5 <= hour < 12 else "こんにちは" if 12 <= hour < 18 else "こんばんは"

    user_habits = Habit.query.filter_by(user_id=current_user.id).all()
    today = datetime.utcnow().date()
    
    habits_list = []
    done_count = 0
    for h in user_habits:
        is_done = HabitLog.query.filter_by(habit_id=h.id, date=today).first() is not None
        if is_done: done_count += 1
        
        # 進捗計算（開始日から今日までの達成率）
        total_days = (today - h.start_date).days + 1
        total_achieved = HabitLog.query.filter_by(habit_id=h.id).count()
        progress_pct = int((total_achieved / total_days) * 100) if total_days > 0 else 0
        
        habits_list.append({
            'id': h.id, 'name': h.name, 'freq': h.frequency, 'category': h.category,
            'is_done': is_done, 'progress': progress_pct, 'streak': total_achieved
        })

    rate = int((done_count / len(user_habits)) * 100) if user_habits else 0
    remaining = len(user_habits) - done_count

    return render_template('home.html', date=date_str, greeting=greeting, 
                           habits=habits_list, rate=rate, remaining=remaining)

@app.route('/habit/toggle/<int:habit_id>', methods=['POST'])
@login_required
def toggle_habit(habit_id):
    today = datetime.utcnow().date()
    log = HabitLog.query.filter_by(habit_id=habit_id, date=today).first()
    if log:
        db.session.delete(log)
    else:
        db.session.add(HabitLog(habit_id=habit_id, date=today))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/habit/add', methods=['GET', 'POST'])
@login_required
def add_habit():
    if request.method == 'POST':
        habit = Habit(
            name=request.form.get('habit_name'),
            category=request.form.get('category'),
            frequency=request.form.get('frequency'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
            user_id=current_user.id
        )
        db.session.add(habit)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('add_habit.html')

@app.route('/habit/delete/<int:habit_id>', methods=['POST'])
@login_required
def delete_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id == current_user.id:
        db.session.delete(habit)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/habit/<int:habit_id>')
@login_required
def detail(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    logs = HabitLog.query.filter_by(habit_id=habit_id).order_by(HabitLog.date.desc()).all()
    return render_template('detail.html', habit=habit, logs=logs, total=len(logs))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('password_confirm')
        
        # 企画書要件：パスワード確認ロジック
        if password != confirm:
            flash('パスワードが一致しません')
            return redirect(url_for('signup'))
            
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=request.form.get('username'), email=request.form.get('email'), password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and bcrypt.check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)