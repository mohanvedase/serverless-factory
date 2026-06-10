#!/usr/bin/env python3
"""
Serverless Automation Factory — Entry Point
Usage:  python run.py
"""

from app import app, init_db
from config import Config

if __name__ == "__main__":
    init_db()
    print("""
╔══════════════════════════════════════════════════════════╗
║       🏭  SERVERLESS AUTOMATION FACTORY                  ║
║          AWS Training Dashboard                          ║
╠══════════════════════════════════════════════════════════╣
║  Dashboard   →  http://localhost:{port}                  ║
║  Resume      →  http://localhost:{port}/resume-pipeline  ║
║  Orders      →  http://localhost:{port}/order-pipeline   ║
╚══════════════════════════════════════════════════════════╝
""".format(port=Config.PORT))
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
