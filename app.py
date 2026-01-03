from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.post("/whatsapp")
def whatsapp():
    resp = MessagingResponse()
    resp.message("Bot is running ✅ Reply MENU to start.")
    return str(resp)
