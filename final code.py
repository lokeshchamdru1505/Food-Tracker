import os, csv
from flask import Flask, request, render_template_string, redirect
from PIL import Image
from werkzeug.utils import secure_filename
import tkinter as tk
from tkinter import filedialog

# ================= BASIC SETUP =================
app = Flask(__name__)
UPLOADS = "uploads"
PORT = 8088
ALLOWED_EXT = {"jpg", "jpeg", "png"}

os.makedirs(UPLOADS, exist_ok=True)

# ================= SELECT CSV =================
root = tk.Tk()
root.withdraw()
csv_path = filedialog.askopenfilename(
    title="Select food CSV file",
    filetypes=[("CSV files", "*.csv")]
)

if not csv_path:
    raise SystemExit("❌ No CSV selected")

# ================= LOAD CSV =================
FOODS = []
with open(csv_path, newline="", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        FOODS.append({k.lower(): v for k, v in r.items()})

# ================= DATA =================
daily_log = []

def f(x):
    try: return float(x)
    except: return 0.0

def calc(row, grams):
    g = grams / 100
    cal = f(row.get("calories"))
    p = f(row.get("protein"))
    c = f(row.get("carbs"))
    fat = f(row.get("fat"))
    fi = f(row.get("fiber"))
    if cal == 0:
        cal = p*4 + c*4 + fat*9
    return {
        "food": row["food"],
        "grams": grams,
        "cal": round(cal*g, 2),
        "p": round(p*g, 2),
        "c": round(c*g, 2),
        "fat": round(fat*g, 2),
        "fi": round(fi*g, 2)
    }

# ================= IMAGE HELPERS =================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

def detect_food(path):
    name = os.path.basename(path).lower()
    for k in ["banana","apple","rice","chicken","egg","bread"]:
        if k in name:
            return k

    img = Image.open(path).convert("RGB").resize((60,60))
    px = list(img.getdata())
    r = sum(p[0] for p in px)/len(px)
    g = sum(p[1] for p in px)/len(px)

    if r > 200 and g > 200:
        return "banana"
    if r > g:
        return "apple"
    return "rice"

# ================= BMR =================
def bmr(weight, height, age, sex):
    if sex == "male":
        return 10*weight + 6.25*height - 5*age + 5
    return 10*weight + 6.25*height - 5*age - 161

ACTIVITY = {
    "sedentary": 1.2,
    "light": 1.375,
    "normal": 1.55,
    "heavy": 1.725,
    "very": 1.9
}

# ================= UI =================
HTML = """
<!doctype html>
<title>Nutrition Tracker</title>
<style>
body{font-family:Segoe UI;background:#eef2ff;padding:20px}
.card{background:white;padding:20px;border-radius:14px;margin-bottom:20px;
box-shadow:0 8px 20px rgba(0,0,0,.1)}
h2{margin-top:0;color:#1e3a8a}
button{background:#2563eb;color:white;border:none;
padding:10px 14px;border-radius:8px;cursor:pointer}
input,select{padding:10px;width:100%;margin:6px 0;
border-radius:8px;border:1px solid #ccc}
table{width:100%;border-collapse:collapse}
th,td{padding:8px;border-bottom:1px solid #ddd;text-align:center}
.total{font-size:18px;font-weight:bold;color:#16a34a}
.error{color:red;font-weight:bold}
</style>

<div class="card">
<h2>📷 Add Food by Image</h2>
<form method="post" action="/image" enctype="multipart/form-data">
<input type="file" name="img" required>
<input name="grams" placeholder="grams" required>
<button>Add</button>
</form>
{% if img_error %}
<p class="error">{{img_error}}</p>
{% endif %}
</div>

<div class="card">
<h2>✍️ Add Food by Text</h2>
<form method="post" action="/text">
<input name="food" placeholder="banana / rice / chicken" required>
<input name="grams" placeholder="grams" required>
<button>Add</button>
</form>
</div>

<div class="card">
<h2>📊 Today</h2>
<table>
<tr><th>Food</th><th>g</th><th>Cal</th><th>P</th><th>C</th><th>F</th><th>Fi</th></tr>
{% for i in log %}
<tr>
<td>{{i.food}}</td><td>{{i.grams}}</td>
<td>{{i.cal}}</td><td>{{i.p}}</td>
<td>{{i.c}}</td><td>{{i.fat}}</td><td>{{i.fi}}</td>
</tr>
{% endfor %}
</table>

<div class="total">
Calories: {{tot.cal}} |
Protein: {{tot.p}} |
Carbs: {{tot.c}} |
Fat: {{tot.fat}} |
Fiber: {{tot.fi}}
</div>

<form method="post" action="/reset">
<button>Reset Day</button>
</form>
</div>

<div class="card">
<h2>🔥 BMR & Maintenance</h2>
<form method="post" action="/bmr">
<input name="weight" placeholder="Weight (kg)" required>
<input name="height" placeholder="Height (cm)" required>
<input name="age" placeholder="Age" required>
<select name="sex">
<option value="male">Male</option>
<option value="female">Female</option>
</select>
<select name="activity">
<option value="sedentary">Sedentary</option>
<option value="light">Light</option>
<option value="normal">Normal</option>
<option value="heavy">Heavy</option>
<option value="very">Very Active</option>
</select>
<button>Calculate</button>
</form>

{% if bmrval %}
<p class="total">
BMR: {{bmrval}} kcal<br>
Maintenance: {{maint}} kcal
</p>
{% endif %}
</div>
"""

# ================= ROUTES =================
@app.route("/")
def home():
    tot = {
        "cal": round(sum(i["cal"] for i in daily_log),2),
        "p": round(sum(i["p"] for i in daily_log),2),
        "c": round(sum(i["c"] for i in daily_log),2),
        "fat": round(sum(i["fat"] for i in daily_log),2),
        "fi": round(sum(i["fi"] for i in daily_log),2),
    }
    return render_template_string(HTML, log=daily_log, tot=tot)

@app.route("/image", methods=["POST"])
def image():
    if "img" not in request.files:
        return redirect("/")

    img = request.files["img"]
    if img.filename == "":
        return redirect("/")

    if not allowed_file(img.filename):
        return render_template_string(
            HTML, log=daily_log,
            tot={"cal":0,"p":0,"c":0,"fat":0,"fi":0},
            img_error="Only JPG / PNG images allowed"
        )

    grams = float(request.form["grams"])
    filename = secure_filename(img.filename)
    path = os.path.join(UPLOADS, filename)
    img.save(path)

    try:
        guess = detect_food(path)
    except Exception:
        return "❌ Image processing failed"

    for r in FOODS:
        if guess in r["food"].lower():
            daily_log.append(calc(r, grams))
            break

    return redirect("/")

@app.route("/text", methods=["POST"])
def text():
    food = request.form["food"].lower()
    grams = float(request.form["grams"])
    for r in FOODS:
        if food in r["food"].lower():
            daily_log.append(calc(r, grams))
            break
    return redirect("/")

@app.route("/reset", methods=["POST"])
def reset():
    daily_log.clear()
    return redirect("/")

@app.route("/bmr", methods=["POST"])
def bmr_route():
    w = float(request.form["weight"])
    h = float(request.form["height"])
    a = int(request.form["age"])
    s = request.form["sex"]
    act = request.form["activity"]

    b = round(bmr(w, h, a, s), 2)
    m = round(b * ACTIVITY[act], 2)

    tot = {
        "cal": sum(i["cal"] for i in daily_log),
        "p": sum(i["p"] for i in daily_log),
        "c": sum(i["c"] for i in daily_log),
        "fat": sum(i["fat"] for i in daily_log),
        "fi": sum(i["fi"] for i in daily_log),
    }

    return render_template_string(
        HTML, log=daily_log, tot=tot, bmrval=b, maint=m
    )

# ================= RUN =================
if __name__ == "__main__":
    print(f"🚀 Open http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=True)
