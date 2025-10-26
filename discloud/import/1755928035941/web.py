from flask import Flask, send_file

app = Flask(__name__)

@app.route("/riot.txt")
def riot_verify():
    return send_file("riot.txt", mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


