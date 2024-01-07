import win32clipboard
from flask import Flask

app = Flask(__name__)

@app.route('/')
def getClipboard():
	win32clipboard.OpenClipboard()
	data = win32clipboard.GetClipboardData()
	win32clipboard.CloseClipboard()
	print(data)
	return data

app.run(debug=True)
