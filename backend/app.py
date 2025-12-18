from flask import Flask, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import bcrypt

app = Flask(__name__)
app.secret_key = 'secret-key'  # Change in production

# ===== Config =====
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email config (Gmail)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'       # Change to your email
app.config['MAIL_PASSWORD'] = 'your_app_password'          # Gmail App Password
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

# ===== Initialize =====
db = SQLAlchemy(app)
mail = Mail(app)
s = URLSafeTimedSerializer(app.secret_key)

# ===== User Model =====
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# ===== Routes =====

# Home
@app.route('/')
def home():
    return render_template('index.html')

# Register
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            return 'User already exists', 400
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user = User(email=email, password=hashed.decode('utf-8'))
        db.session.add(user)
        db.session.commit()
        return 'Registration successful!'
    return render_template('register.html')

# Login
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if not user:
            return 'User not found', 404
        if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            session['email'] = email
            return render_template('dashboard.html', email=email)
        else:
            return 'Invalid password', 401
    return render_template('login.html')

# Request Password Reset
@app.route('/request-reset', methods=['GET','POST'])
def request_reset():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if not user:
            return 'User not found', 404
        token = s.dumps(email, salt='password-reset-salt')
        reset_url = url_for('reset_password', token=token, _external=True)
        msg = Message('Password Reset', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Click here to reset your password: {reset_url}'
        mail.send(msg)
        return f'Password reset link sent to {email}'
    return render_template('reset_password_request.html')

# Reset Password
@app.route('/reset-password/<token>', methods=['GET','POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        return 'The reset link is invalid or expired.'
    if request.method == 'POST':
        new_password = request.form['password']
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        user = User.query.filter_by(email=email).first()
        user.password = hashed.decode('utf-8')
        db.session.commit()
        return 'Password successfully updated!'
    return render_template('reset_password_form.html')  # Create this template

# Dashboard (optional route if you want a separate dashboard URL)
@app.route('/dashboard')
def dashboard():
    if 'email' in session:
        return render_template('dashboard.html', email=session['email'])
    return redirect(url_for('login'))

# ===== Run App =====
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
