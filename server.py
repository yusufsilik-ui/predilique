from flask import Flask, render_template

app = Flask(name)

@app.route("/") def index(): return render_template("index.html", title="Predilique")

if name == "main": import os port = int(os.getenv("PORT", 5000)) app.run(host="0.0.0.0", port=port, debug=True)
