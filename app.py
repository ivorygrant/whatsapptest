from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import re

app = Flask(__name__)

# ====== CONFIG ======
MENU = {
    "taco": {"name": "Tacos", "price": 50},
    "burrito": {"name": "Burrito", "price": 80},
    "quesadilla": {"name": "Quesadilla", "price": 70},
    "soda": {"name": "Soda", "price": 25},
}

# In-memory sessions keyed by sender (e.g., "whatsapp:+1404...")
# Later we can replace this with SQLite.
SESSIONS = {}


# ====== HELPERS ======
def menu_text() -> str:
    lines = ["🍽 MENU (type your order in one message)\n"]
    for item in MENU.values():
        lines.append(f"- {item['name']} – ${item['price']}")
    lines.append("\nExample: 2 tacos and 1 soda")
    lines.append("Then reply CONFIRM, then send: address: <your address>")
    return "\n".join(lines)


def normalize(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\sx:]", " ", t)  # keep words, spaces, x, colon
    t = re.sub(r"\s+", " ", t)
    return t


def parse_order(text: str):
    """
    Parse natural language order.
    Supports:
      - "2 tacos and 1 soda"
      - "tacos x2, soda"
      - "1 burrito"
      - item names without qty => assumed qty=1

    Returns dict like {"taco": 2, "soda": 1}
    Returns {} if no items recognized.
    Returns None if message is clearly not an order command.
    """
    t = normalize(text)

    # commands we don't want to treat as orders
    if t in ("hi", "hello", "hola", "menu", "help", "confirm", "change"):
        return None

    items = {}

    for key, item in MENU.items():
        name = item["name"].lower()

        qty = 0

        # patterns like: "tacos x2" or "taco x 2"
        for m in re.finditer(rf"\b{name}s?\s*x\s*(\d+)\b", t):
            qty += int(m.group(1))

        # patterns like: "2 tacos"
        for m in re.finditer(rf"\b(\d+)\s*{name}s?\b", t):
            qty += int(m.group(1))

        if qty > 0:
            items[key] = qty

    # If they mentioned item names but no quantities, assume 1
    for key, item in MENU.items():
        if key in items:
            continue
        name = item["name"].lower()
        if re.search(rf"\b{name}s?\b", t):
            items[key] = 1

    return items


def format_order(items_dict: dict) -> tuple[str, int]:
    lines = []
    total = 0
    for key, qty in items_dict.items():
        item = MENU[key]
        line_total = qty * item["price"]
        total += line_total
        lines.append(f"- {item['name']} x{qty} = ${line_total}")
    return "\n".join(lines), total


# ====== ROUTES ======
@app.post("/whatsapp")
def whatsapp():
    body_raw = (request.form.get("Body") or "").strip()
    body = body_raw.lower().strip()
    from_ = request.form.get("From")  # e.g. "whatsapp:+14046645731"

    resp = MessagingResponse()

    # Start / help
    if body in ("hi", "hello", "hola", "menu", "help"):
        resp.message(menu_text())
        return str(resp)

    # Confirm order
    if body == "confirm":
        s = SESSIONS.get(from_)
        if not s or not s.get("items"):
            resp.message("No order found. Reply MENU to start.")
            return str(resp)

        resp.message(
            "✅ Confirmed!\n"
            "Now send your delivery address like:\n"
            "address: 123 Main St, Apt 2"
        )
        return str(resp)

    # Change order (simple reset)
    if body == "change":
        if from_ in SESSIONS:
            del SESSIONS[from_]
        resp.message("Okay — order cleared. Reply MENU and send a new order.")
        return str(resp)

    # Capture address
    if body.startswith("address:"):
        s = SESSIONS.get(from_)
        if not s or not s.get("items"):
            resp.message("Please place an order first. Reply MENU to start.")
            return str(resp)

        address = body_raw.split(":", 1)[1].strip()
        s["address"] = address

        resp.message(
            f"📍 Address saved: {address}\n\n"
            "Next step: payment link (we’ll add this next).\n"
            "For now, reply DONE to finish the demo."
        )
        return str(resp)

    # Demo done
    if body == "done":
        s = SESSIONS.get(from_)
        if not s or not s.get("items") or not s.get("address"):
            resp.message("You’re missing order or address. Reply MENU to start.")
            return str(resp)

        resp.message("🎉 Demo complete. Next we’ll add payment + admin updates.")
        return str(resp)

    # Try parsing as a natural language order
    items_dict = parse_order(body_raw)
    if items_dict is None:
        resp.message("Reply MENU to start ordering.")
        return str(resp)

    if items_dict == {}:
        resp.message("I didn’t recognize that order. Reply MENU to see items.")
        return str(resp)

    order_lines, total = format_order(items_dict)

    SESSIONS[from_] = {"items": items_dict, "total": total}

    resp.message(
        "✅ I got:\n" +
        order_lines +
        f"\n\nTotal: ${total}\n"
        "Reply CONFIRM or send a corrected order.\n"
        "(Reply CHANGE to clear.)"
    )
    return str(resp)


# Optional: local run support (Render uses gunicorn app:app)
if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
