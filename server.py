#!/usr/bin/env python3
"""Web Answer Assistant – Ready to Use"""
import json, os, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
API_URL = "https://api.openai.com/v1/responses"

class Handler(BaseHTTPRequestHandler):
    def send_data(self, code, data, content_type="application/json; charset=utf-8"):
        raw = data if isinstance(data, bytes) else data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_data(200, (ROOT / "index.html").read_text(encoding="utf-8"),
                           "text/html; charset=utf-8")
        elif self.path == "/health":
            self.send_data(200, '{"ok":true}')
        else:
            self.send_data(404, '{"error":"Not found"}')

    def do_POST(self):
        if self.path != "/api/answer":
            return self.send_data(404, '{"error":"Not found"}')
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return self.send_data(503, json.dumps({
                "error":"ระบบยังไม่ได้ตั้งค่า AI API Key กรุณาติดต่อผู้ดูแลระบบ"
            }, ensure_ascii=False))
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 25000:
                return self.send_data(413, '{"error":"ขนาดข้อความไม่ถูกต้องหรือยาวเกินไป"}')
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            question = str(payload.get("question", "")).strip()
            if not question:
                return self.send_data(400, '{"error":"กรุณาเลือกหรือวางข้อความโจทย์"}')
            if len(question) > 10000:
                return self.send_data(400, '{"error":"ข้อความยาวเกิน 10,000 ตัวอักษร"}')

            request_body = {
                "model": MODEL,
                "instructions": (
                    "คุณเป็นผู้ช่วยการเรียนรู้ วิเคราะห์โจทย์และตัวเลือกที่ผู้ใช้ส่งมา "
                    "ตอบเป็นภาษาไทยอย่างชัดเจน โดยระบุคำตอบที่เหมาะสมและเหตุผลสั้น ๆ "
                    "หากมีตัวเลือกให้ระบุตัวอักษรหรือหมายเลขพร้อมข้อความ "
                    "หากข้อมูลไม่เพียงพอหรือโจทย์กำกวม ให้แจ้งข้อจำกัดและอย่าเดา"
                ),
                "input": question
            }
            req = urllib.request.Request(
                API_URL, data=json.dumps(request_body).encode(),
                headers={"Authorization":"Bearer "+key, "Content-Type":"application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.loads(response.read().decode("utf-8"))
            chunks = []
            for item in result.get("output", []):
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        chunks.append(part.get("text", ""))
            answer = "\n".join(chunks).strip() or "ไม่พบคำตอบจาก AI"
            self.send_data(200, json.dumps({"answer":answer}, ensure_ascii=False))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            self.send_data(502, json.dumps({
                "error":"บริการ AI ตอบกลับผิดพลาด กรุณาลองใหม่",
                "detail":detail[:700]
            }, ensure_ascii=False))
        except Exception as e:
            self.send_data(500, json.dumps({"error":"ระบบเกิดข้อผิดพลาด: "+str(e)}, ensure_ascii=False))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

if __name__ == "__main__":
    print(f"Listening on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
