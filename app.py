<<<<<<< HEAD
# app.py
import os, json, csv, io, base64
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from werkzeug.utils import secure_filename

# Optional ML libs
try:
    from tensorflow.keras.models import load_model
except:
    load_model = None
try:
    import joblib
except:
    joblib = None

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ---------------- paths ----------------
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolios.json")
RECENT_PRED_FILE = os.path.join(DATA_DIR, "recent_predictions.csv")
SETTINGS_FILE = os.path.join(DATA_DIR, "user_settings.json")
MODELS_DIR = "models"
MODEL_PATH = os.path.join(MODELS_DIR, "stock_model.h5")
SCALER_PATH = os.path.join(MODELS_DIR, "scaler.save")

# ---------------- in-memory / temp ----------------
users = {}  # temporary users
recent_predictions = []

# ---------------- Upload config ----------------
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- Load/Save Helpers ----------------
def load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f:
                return json.load(f)
        except: return default
    return default

def save_json_file(path, data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_portfolios():
    return load_json_file(PORTFOLIO_FILE, {})

def save_portfolios(portfolios):
    save_json_file(PORTFOLIO_FILE, portfolios)

def load_recent_predictions():
    global recent_predictions
    recent_predictions = []
    if os.path.exists(RECENT_PRED_FILE):
        try:
            with open(RECENT_PRED_FILE, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row['current_price'] = float(row['current_price'])
                    row['predicted_price'] = float(row['predicted_price'])
                    row['percent_change'] = float(row['percent_change'])
                    recent_predictions.append(row)
        except Exception as e:
            print("Failed to load recent predictions:", e)

def save_recent_predictions():
    max_rows = 50
    to_save = recent_predictions[:max_rows]
    with open(RECENT_PRED_FILE,'w',newline='',encoding='utf-8') as f:
        fieldnames = ['symbol','current_price','predicted_price','percent_change','timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in to_save:
            writer.writerow(row)

load_recent_predictions()

# ---------------- Load model/scaler (optional) ----------------
model = None
scaler = None
if load_model and os.path.exists(MODEL_PATH):
    try:
        model = load_model(MODEL_PATH)
    except Exception as e:
        print("Model load error:", e)
if joblib and os.path.exists(SCALER_PATH):
    try:
        scaler = joblib.load(SCALER_PATH)
    except Exception as e:
        print("Scaler load error:", e)

# ---------------- Authentication ----------------
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    theme = session.get('theme','light')
    if request.method=="POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        email = request.form.get("email","").strip()
        if not username or not password:
            flash("Enter username & password","danger")
            return redirect(url_for("register"))
        if username in users:
            flash("Username exists","danger")
            return redirect(url_for("register"))
        users[username] = {"password": password, "email": email}
        flash("Registered. Please login.","success")
        return redirect(url_for("login"))
    return render_template("register.html", theme=theme)

@app.route("/login", methods=["GET","POST"])
def login():
    theme = session.get('theme','light')
    if request.method=="POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        if username in users and users[username]["password"]==password:
            session['username'] = username
            session.setdefault('theme','light')
            flash("Login successful","success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials","danger")
            return redirect(url_for("login"))
    return render_template("login.html", theme=theme)

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Logged out","success")
    return redirect(url_for("login"))

# ---------------- Stock Prediction ----------------
def predict_stock_data(stock_symbol):
    try:
        data = yf.download(stock_symbol, start="2020-01-01", end=datetime.today().strftime("%Y-%m-%d"))
        if data.empty:
            return None,None,None,None,None
        close = data['Close'].values.reshape(-1,1)
        current_price = round(float(close[-1][0]),2)
        if model is None or scaler is None:
            predicted_price = current_price
            percent_change = 0.0
            return current_price, predicted_price, percent_change, None, None
        scaled = scaler.transform(close) if scaler else close
        X = [scaled[i-60:i,0] for i in range(60,len(scaled))]
        X = np.array(X)
        if X.size==0:
            return current_price,None,None,None,None
        X = np.reshape(X,(X.shape[0],X.shape[1],1))
        pred_arr = model.predict(X)
        if scaler:
            pred_arr = scaler.inverse_transform(pred_arr)
        predicted_price = round(float(pred_arr[-1][0]),2)
        percent_change = round((predicted_price-current_price)/current_price*100,2)
        # Plot
        buf = io.BytesIO()
        plt.figure(figsize=(8,4))
        plt.plot(close,label="Actual")
        plt.plot(range(60,60+len(pred_arr)), pred_arr,label="Predicted")
        plt.legend()
        plt.tight_layout()
        plt.savefig(buf,format="png")
        buf.seek(0)
        plot_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        plt.close()
        return current_price,predicted_price,percent_change,plot_b64,None
    except:
        return None,None,None,None,None

# ---------------- Home Route ----------------
@app.route("/home", methods=["GET","POST"])
def home():
    if 'username' not in session:
        return redirect(url_for("login"))
    theme = session.get("theme","light")
    stock_symbol=current_price=predicted_price=percent_change=plot_image=None
    if request.method=="POST":
        stock_symbol = request.form.get("stock_symbol","").upper().strip()
        if stock_symbol:
            current_price,predicted_price,percent_change,plot_image,alert_msg = predict_stock_data(stock_symbol)
            if current_price is not None and predicted_price is not None:
                recent_predictions.insert(0,{
                    "symbol": stock_symbol,
                    "current_price": current_price,
                    "predicted_price": predicted_price,
                    "percent_change": percent_change,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                if len(recent_predictions)>50:
                    recent_predictions.pop()
                save_recent_predictions()
            if alert_msg:
                flash(alert_msg,"success" if percent_change>0 else "danger")
    total_stocks = len(set([r['symbol'] for r in recent_predictions])) if recent_predictions else 0
    total_predictions = len(recent_predictions)
    portfolio_value = sum([r['current_price'] for r in recent_predictions if r.get('current_price')]) if recent_predictions else 0
    active_stocks = total_stocks
    return render_template("dashboard.html",
                           theme=theme,
                           stock_symbol=stock_symbol,
                           current_price=current_price,
                           predicted_price=predicted_price,
                           percent_change=percent_change,
                           plot_image=plot_image,
                           total_stocks=total_stocks,
                           total_predictions=total_predictions,
                           portfolio_value=portfolio_value,
                           active_stocks=active_stocks,
                           recent_predictions=recent_predictions)

# ---------------- Delete Prediction ----------------
@app.route('/delete_prediction/<string:timestamp>', methods=['POST'])
def delete_prediction(timestamp):
    global recent_predictions
    recent_predictions = [r for r in recent_predictions if r['timestamp'] != timestamp]
    save_recent_predictions()
    flash("Prediction deleted successfully!","success")
    return redirect(url_for('home'))

# ---------------- Predict Route ----------------
@app.route("/predict", methods=["GET","POST"])
def predict():
    if 'username' not in session:
        return redirect(url_for("login"))
    theme = session.get("theme","light")
    stock_symbol=current_price=predicted_price=percent_change=plot_image=None
    if request.method=="POST":
        stock_symbol = request.form.get("stock_symbol","").upper().strip()
        current_price,predicted_price,percent_change,plot_image,alert_msg = predict_stock_data(stock_symbol)
        if current_price is not None and predicted_price is not None:
            recent_predictions.insert(0,{
                "symbol": stock_symbol,
                "current_price": current_price,
                "predicted_price": predicted_price,
                "percent_change": percent_change,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            if len(recent_predictions)>50:
                recent_predictions.pop()
            save_recent_predictions()
        if alert_msg:
            flash(alert_msg,"success" if percent_change>0 else "danger")
    return render_template("predict.html",
                           theme=theme,
                           stock_symbol=stock_symbol,
                           current_price=current_price,
                           predicted_price=predicted_price,
                           percent_change=percent_change,
                           plot_image=plot_image)

# ---------------- Portfolio ----------------
@app.route("/portfolio", methods=["GET"])
def portfolio():
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    theme = session.get("theme","light")
    portfolios = load_portfolios()
    user_holdings = portfolios.get(username, [])
    display_holdings = []

    for h in user_holdings:
        symbol = h.get("symbol")
        qty = float(h.get("quantity",0))
        buy_price = float(h.get("buy_price",0))
        current_price = total_value = pl = None
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = round(float(hist['Close'][-1]),2)
                total_value = round(current_price * qty,2)
                pl = round((current_price - buy_price)*qty,2)
        except:
            current_price = None
        display = h.copy()
        display.update({"current_price":current_price,"total_value":total_value,"pl":pl})
        display_holdings.append(display)

    portfolio_total = sum([d['total_value'] for d in display_holdings if d.get('total_value')])
    return render_template("portfolio.html", theme=theme, holdings=display_holdings, portfolio_total=round(portfolio_total,2))

@app.route("/portfolio/add", methods=["POST"])
def portfolio_add():
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    symbol = request.form.get("symbol","").upper().strip()
    try:
        quantity = float(request.form.get("quantity","0"))
        buy_price = float(request.form.get("buy_price","0"))
    except:
        flash("Invalid input","danger")
        return redirect(url_for("portfolio"))

    portfolios = load_portfolios()
    user_holdings = portfolios.get(username,[])
    new_id = max([h.get("id",0) for h in user_holdings]+[0])+1
    holding = {
        "id": new_id,
        "symbol": symbol,
        "quantity": quantity,
        "buy_price": buy_price,
        "added_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    user_holdings.append(holding)
    portfolios[username] = user_holdings
    save_portfolios(portfolios)
    flash(f"Added {symbol} to portfolio","success")
    return redirect(url_for("portfolio"))

@app.route("/portfolio/edit/<int:hid>", methods=["POST"])
def portfolio_edit(hid):
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    portfolios = load_portfolios()
    user_holdings = portfolios.get(username,[])
    found = False
    for h in user_holdings:
        if int(h.get("id",0)) == hid:
            try:
                h["quantity"] = float(request.form.get("quantity", h.get("quantity",0)))
                h["buy_price"] = float(request.form.get("buy_price", h.get("buy_price",0)))
                h["updated_on"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                found = True
            except:
                flash("Invalid input","danger")
                return redirect(url_for("portfolio"))
            break
    if not found:
        flash("Holding not found","danger")
    else:
        portfolios[username] = user_holdings
        save_portfolios(portfolios)
        flash("Holding updated successfully","success")
    return redirect(url_for("portfolio"))

@app.route("/portfolio/delete/<int:hid>", methods=["POST"])
def portfolio_delete(hid):
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    portfolios = load_portfolios()
    user_holdings = portfolios.get(username,[])
    portfolios[username] = [h for h in user_holdings if int(h.get("id",0))!=hid]
    save_portfolios(portfolios)
    flash("Holding removed","success")
    return redirect(url_for("portfolio"))

# ---------------- Settings ----------------
@app.route("/settings", methods=["GET","POST"])
def settings():
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    theme = session.get("theme","light")
    settings_data = load_json_file(SETTINGS_FILE, {})
    if request.method=="POST":
        theme = request.form.get("theme","light")
        session['theme'] = theme
        settings_data.setdefault(username,{})['theme'] = theme
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{username}_{file.filename}")
                os.makedirs(app.config['UPLOAD_FOLDER'],exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'],filename))
                settings_data[username]['profile_pic'] = filename
                flash("Profile picture updated!","success")
        save_json_file(SETTINGS_FILE,settings_data)
        flash("Settings updated!","success")
        return redirect(url_for("settings"))
    user_data = settings_data.get(username,{})
    profile_pic = user_data.get("profile_pic","default_avatar.png")
    email = users.get(username,{}).get("email","")
    current_theme = user_data.get("theme",theme)
    return render_template("settings.html",theme=current_theme,username=username,email=email,profile_pic=profile_pic)

# ---------------- Reset Password ----------------
@app.route("/reset-password", methods=["POST"])
def reset_password():
    if 'username' not in session:
        flash("Please login first","danger")
        return redirect(url_for("login"))
    username = session['username']
    user = users.get(username)
    if not user:
        flash("User not found","danger")
        return redirect(url_for("settings"))
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    if new_password != confirm_password:
        flash("Passwords do not match!","danger")
        return redirect(url_for("settings"))
    user["password"] = new_password
    flash("Password updated successfully!","success")
    return redirect(url_for("settings"))

# ---------------- Run ----------------
if __name__=="__main__":
    app.run(debug=True)
=======
# app.py
import os, json, csv, io, base64
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from werkzeug.utils import secure_filename

# Optional ML libs
try:
    from tensorflow.keras.models import load_model
except:
    load_model = None
try:
    import joblib
except:
    joblib = None

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ---------------- paths ----------------
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolios.json")
RECENT_PRED_FILE = os.path.join(DATA_DIR, "recent_predictions.csv")
SETTINGS_FILE = os.path.join(DATA_DIR, "user_settings.json")
MODELS_DIR = "models"
MODEL_PATH = os.path.join(MODELS_DIR, "stock_model.h5")
SCALER_PATH = os.path.join(MODELS_DIR, "scaler.save")

# ---------------- in-memory / temp ----------------
users = {}  # temporary users
recent_predictions = []

# ---------------- Upload config ----------------
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- Load/Save Helpers ----------------
def load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f:
                return json.load(f)
        except: return default
    return default

def save_json_file(path, data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_portfolios():
    return load_json_file(PORTFOLIO_FILE, {})

def save_portfolios(portfolios):
    save_json_file(PORTFOLIO_FILE, portfolios)

def load_recent_predictions():
    global recent_predictions
    recent_predictions = []
    if os.path.exists(RECENT_PRED_FILE):
        try:
            with open(RECENT_PRED_FILE, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row['current_price'] = float(row['current_price'])
                    row['predicted_price'] = float(row['predicted_price'])
                    row['percent_change'] = float(row['percent_change'])
                    recent_predictions.append(row)
        except Exception as e:
            print("Failed to load recent predictions:", e)

def save_recent_predictions():
    max_rows = 50
    to_save = recent_predictions[:max_rows]
    with open(RECENT_PRED_FILE,'w',newline='',encoding='utf-8') as f:
        fieldnames = ['symbol','current_price','predicted_price','percent_change','timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in to_save:
            writer.writerow(row)

load_recent_predictions()

# ---------------- Load model/scaler (optional) ----------------
model = None
scaler = None
if load_model and os.path.exists(MODEL_PATH):
    try:
        model = load_model(MODEL_PATH)
    except Exception as e:
        print("Model load error:", e)
if joblib and os.path.exists(SCALER_PATH):
    try:
        scaler = joblib.load(SCALER_PATH)
    except Exception as e:
        print("Scaler load error:", e)

# ---------------- Authentication ----------------
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    theme = session.get('theme','light')
    if request.method=="POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        email = request.form.get("email","").strip()
        if not username or not password:
            flash("Enter username & password","danger")
            return redirect(url_for("register"))
        if username in users:
            flash("Username exists","danger")
            return redirect(url_for("register"))
        users[username] = {"password": password, "email": email}
        flash("Registered. Please login.","success")
        return redirect(url_for("login"))
    return render_template("register.html", theme=theme)

@app.route("/login", methods=["GET","POST"])
def login():
    theme = session.get('theme','light')
    if request.method=="POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        if username in users and users[username]["password"]==password:
            session['username'] = username
            session.setdefault('theme','light')
            flash("Login successful","success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials","danger")
            return redirect(url_for("login"))
    return render_template("login.html", theme=theme)

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Logged out","success")
    return redirect(url_for("login"))

# ---------------- Stock Prediction ----------------
def predict_stock_data(stock_symbol):
    try:
        data = yf.download(stock_symbol, start="2020-01-01", end=datetime.today().strftime("%Y-%m-%d"))
        if data.empty:
            return None,None,None,None,None
        close = data['Close'].values.reshape(-1,1)
        current_price = round(float(close[-1][0]),2)
        if model is None or scaler is None:
            predicted_price = current_price
            percent_change = 0.0
            return current_price, predicted_price, percent_change, None, None
        scaled = scaler.transform(close) if scaler else close
        X = [scaled[i-60:i,0] for i in range(60,len(scaled))]
        X = np.array(X)
        if X.size==0:
            return current_price,None,None,None,None
        X = np.reshape(X,(X.shape[0],X.shape[1],1))
        pred_arr = model.predict(X)
        if scaler:
            pred_arr = scaler.inverse_transform(pred_arr)
        predicted_price = round(float(pred_arr[-1][0]),2)
        percent_change = round((predicted_price-current_price)/current_price*100,2)
        # Plot
        buf = io.BytesIO()
        plt.figure(figsize=(8,4))
        plt.plot(close,label="Actual")
        plt.plot(range(60,60+len(pred_arr)), pred_arr,label="Predicted")
        plt.legend()
        plt.tight_layout()
        plt.savefig(buf,format="png")
        buf.seek(0)
        plot_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        plt.close()
        return current_price,predicted_price,percent_change,plot_b64,None
    except:
        return None,None,None,None,None

# ---------------- Home Route ----------------
@app.route("/home", methods=["GET","POST"])
def home():
    if 'username' not in session:
        return redirect(url_for("login"))
    theme = session.get("theme","light")
    stock_symbol=current_price=predicted_price=percent_change=plot_image=None
    if request.method=="POST":
        stock_symbol = request.form.get("stock_symbol","").upper().strip()
        if stock_symbol:
            current_price,predicted_price,percent_change,plot_image,alert_msg = predict_stock_data(stock_symbol)
            if current_price is not None and predicted_price is not None:
                recent_predictions.insert(0,{
                    "symbol": stock_symbol,
                    "current_price": current_price,
                    "predicted_price": predicted_price,
                    "percent_change": percent_change,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                if len(recent_predictions)>50:
                    recent_predictions.pop()
                save_recent_predictions()
            if alert_msg:
                flash(alert_msg,"success" if percent_change>0 else "danger")
    total_stocks = len(set([r['symbol'] for r in recent_predictions])) if recent_predictions else 0
    total_predictions = len(recent_predictions)
    portfolio_value = sum([r['current_price'] for r in recent_predictions if r.get('current_price')]) if recent_predictions else 0
    active_stocks = total_stocks
    return render_template("dashboard.html",
                           theme=theme,
                           stock_symbol=stock_symbol,
                           current_price=current_price,
                           predicted_price=predicted_price,
                           percent_change=percent_change,
                           plot_image=plot_image,
                           total_stocks=total_stocks,
                           total_predictions=total_predictions,
                           portfolio_value=portfolio_value,
                           active_stocks=active_stocks,
                           recent_predictions=recent_predictions)

# ---------------- Delete Prediction ----------------
@app.route('/delete_prediction/<string:timestamp>', methods=['POST'])
def delete_prediction(timestamp):
    global recent_predictions
    recent_predictions = [r for r in recent_predictions if r['timestamp'] != timestamp]
    save_recent_predictions()
    flash("Prediction deleted successfully!","success")
    return redirect(url_for('home'))

# ---------------- Predict Route ----------------
@app.route("/predict", methods=["GET","POST"])
def predict():
    if 'username' not in session:
        return redirect(url_for("login"))
    theme = session.get("theme","light")
    stock_symbol=current_price=predicted_price=percent_change=plot_image=None
    if request.method=="POST":
        stock_symbol = request.form.get("stock_symbol","").upper().strip()
        current_price,predicted_price,percent_change,plot_image,alert_msg = predict_stock_data(stock_symbol)
        if current_price is not None and predicted_price is not None:
            recent_predictions.insert(0,{
                "symbol": stock_symbol,
                "current_price": current_price,
                "predicted_price": predicted_price,
                "percent_change": percent_change,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            if len(recent_predictions)>50:
                recent_predictions.pop()
            save_recent_predictions()
        if alert_msg:
            flash(alert_msg,"success" if percent_change>0 else "danger")
    return render_template("predict.html",
                           theme=theme,
                           stock_symbol=stock_symbol,
                           current_price=current_price,
                           predicted_price=predicted_price,
                           percent_change=percent_change,
                           plot_image=plot_image)

# ---------------- Portfolio ----------------
@app.route("/portfolio", methods=["GET"])
def portfolio():
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    theme = session.get("theme","light")
    portfolios = load_portfolios()
    user_holdings = portfolios.get(username, [])
    display_holdings = []

    for h in user_holdings:
        symbol = h.get("symbol")
        qty = float(h.get("quantity",0))
        buy_price = float(h.get("buy_price",0))
        current_price = total_value = pl = None
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = round(float(hist['Close'][-1]),2)
                total_value = round(current_price * qty,2)
                pl = round((current_price - buy_price)*qty,2)
        except:
            current_price = None
        display = h.copy()
        display.update({"current_price":current_price,"total_value":total_value,"pl":pl})
        display_holdings.append(display)

    portfolio_total = sum([d['total_value'] for d in display_holdings if d.get('total_value')])
    return render_template("portfolio.html", theme=theme, holdings=display_holdings, portfolio_total=round(portfolio_total,2))

@app.route("/portfolio/add", methods=["POST"])
def portfolio_add():
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    symbol = request.form.get("symbol","").upper().strip()
    try:
        quantity = float(request.form.get("quantity","0"))
        buy_price = float(request.form.get("buy_price","0"))
    except:
        flash("Invalid input","danger")
        return redirect(url_for("portfolio"))

    portfolios = load_portfolios()
    user_holdings = portfolios.get(username,[])
    new_id = max([h.get("id",0) for h in user_holdings]+[0])+1
    holding = {
        "id": new_id,
        "symbol": symbol,
        "quantity": quantity,
        "buy_price": buy_price,
        "added_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    user_holdings.append(holding)
    portfolios[username] = user_holdings
    save_portfolios(portfolios)
    flash(f"Added {symbol} to portfolio","success")
    return redirect(url_for("portfolio"))

@app.route("/portfolio/edit/<int:hid>", methods=["POST"])
def portfolio_edit(hid):
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    portfolios = load_portfolios()
    user_holdings = portfolios.get(username,[])
    found = False
    for h in user_holdings:
        if int(h.get("id",0)) == hid:
            try:
                h["quantity"] = float(request.form.get("quantity", h.get("quantity",0)))
                h["buy_price"] = float(request.form.get("buy_price", h.get("buy_price",0)))
                h["updated_on"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                found = True
            except:
                flash("Invalid input","danger")
                return redirect(url_for("portfolio"))
            break
    if not found:
        flash("Holding not found","danger")
    else:
        portfolios[username] = user_holdings
        save_portfolios(portfolios)
        flash("Holding updated successfully","success")
    return redirect(url_for("portfolio"))

@app.route("/portfolio/delete/<int:hid>", methods=["POST"])
def portfolio_delete(hid):
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    portfolios = load_portfolios()
    user_holdings = portfolios.get(username,[])
    portfolios[username] = [h for h in user_holdings if int(h.get("id",0))!=hid]
    save_portfolios(portfolios)
    flash("Holding removed","success")
    return redirect(url_for("portfolio"))

# ---------------- Settings ----------------
@app.route("/settings", methods=["GET","POST"])
def settings():
    if 'username' not in session:
        return redirect(url_for("login"))
    username = session['username']
    theme = session.get("theme","light")
    settings_data = load_json_file(SETTINGS_FILE, {})
    if request.method=="POST":
        theme = request.form.get("theme","light")
        session['theme'] = theme
        settings_data.setdefault(username,{})['theme'] = theme
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{username}_{file.filename}")
                os.makedirs(app.config['UPLOAD_FOLDER'],exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'],filename))
                settings_data[username]['profile_pic'] = filename
                flash("Profile picture updated!","success")
        save_json_file(SETTINGS_FILE,settings_data)
        flash("Settings updated!","success")
        return redirect(url_for("settings"))
    user_data = settings_data.get(username,{})
    profile_pic = user_data.get("profile_pic","default_avatar.png")
    email = users.get(username,{}).get("email","")
    current_theme = user_data.get("theme",theme)
    return render_template("settings.html",theme=current_theme,username=username,email=email,profile_pic=profile_pic)

# ---------------- Reset Password ----------------
@app.route("/reset-password", methods=["POST"])
def reset_password():
    if 'username' not in session:
        flash("Please login first","danger")
        return redirect(url_for("login"))
    username = session['username']
    user = users.get(username)
    if not user:
        flash("User not found","danger")
        return redirect(url_for("settings"))
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    if new_password != confirm_password:
        flash("Passwords do not match!","danger")
        return redirect(url_for("settings"))
    user["password"] = new_password
    flash("Password updated successfully!","success")
    return redirect(url_for("settings"))

# ---------------- Run ----------------
if __name__=="__main__":
    app.run(debug=True)
>>>>>>> b8f160e5449efa8e8041d80c439f442850a9978f
