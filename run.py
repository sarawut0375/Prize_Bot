"""Start Price Bot:  python run.py   then open http://localhost:8000"""
import uvicorn

from pricebot.config import HOST, PORT

if __name__ == "__main__":
    print(f"\n  Price Bot -> http://localhost:{PORT}\n  (กด Ctrl+C เพื่อหยุด)\n")
    uvicorn.run("pricebot.main:app", host=HOST, port=PORT, reload=False)
