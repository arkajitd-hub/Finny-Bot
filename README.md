# Finny-Bot
---

## 🧪 How It Works (Basic Flow)

1. User interacts with the bot via WhatsApp (via Twilio API).
2. `main.py` receives the message and routes it through `message_router.py`.
3. Based on detected intent, it forwards the message to relevant modules:
   - `invoice_reminder` for due dates
   - `ledger` and `granite` for forecasting
   - `loan` for credit advisory
   - `tax` for tax estimation
4. AI responses are generated using Granite 13B or Vision models as needed.
5. Responses are sent back to the user via WhatsApp in conversational format.

---

## 🔧 Setup (Coming Soon)

Instructions for:
- Setting up environment variables
- Running Flask app
- Connecting WhatsApp via Twilio
- Optional dashboard deployment

---

## 👥 Authors

Developed by Jiya Rathi and Arkajit Dutta for IBM Hackathon.

---
