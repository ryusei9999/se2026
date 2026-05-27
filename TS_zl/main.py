from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os

DB_FILE = "todo.db"
app = FastAPI()

# データベースの初期化
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                is_completed INTEGER DEFAULT 0,
                due_date TEXT,
                is_important INTEGER DEFAULT 0
            )
        """)
        conn.commit()

init_db()

# リクエストモデルの定義
class TodoCreate(BaseModel):
    title: str
    due_date: Optional[str] = None
    is_important: Optional[bool] = False

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    is_completed: Optional[bool] = None
    due_date: Optional[str] = None
    is_important: Optional[bool] = None

# --- API ルート ---

@app.get("/api/todos")
def get_todos(sort_by: str = "id"):
    """タスク一覧を取得（締め切り順などのソートに対応）"""
    order_query = "id DESC"
    if sort_by == "due_date":
        # 締め切りが近い順（未設定は後ろにする処理）
        order_query = "CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC"
    elif sort_by == "important":
        order_query = "is_important DESC, id DESC"

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM todos ORDER BY {order_query}")
        rows = cursor.fetchall()
        
    return [
        {
            "id": r["id"], "title": r["title"], 
            "is_completed": bool(r["is_completed"]), 
            "due_date": r["due_date"], "is_important": bool(r["is_important"])
        } for r in rows
    ]

@app.post("/api/todos")
def create_todo(todo: TodoCreate):
    """新規タスク追加"""
    if not todo.title.strip():
        raise HTTPException(status_code=400, detail="タイトルが空です")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO todos (title, due_date, is_important) VALUES (?, ?, ?)",
            (todo.title, todo.due_date, int(todo.is_important))
        )
        conn.commit()
    return {"status": "success"}

@app.put("/api/todos/{todo_id}")
def update_todo(todo_id: int, todo: TodoUpdate):
    """タスクの更新（完了チェック、星マーク、修正すべてに対応）"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # 動的にクエリを組み立て
        update_fields = []
        params = []
        if todo.title is not None:
            update_fields.append("title = ?")
            params.append(todo.title)
        if todo.is_completed is not None:
            update_fields.append("is_completed = ?")
            params.append(int(todo.is_completed))
        if todo.due_date is not None:
            update_fields.append("due_date = ?")
            params.append(todo.due_date)
        if todo.is_important is not None:
            update_fields.append("is_important = ?")
            params.append(int(todo.is_important))
        
        if not update_fields:
            return {"status": "no change"}
            
        params.append(todo_id)
        cursor.execute(f"UPDATE todos SET {', '.join(update_fields)} WHERE id = ?", params)
        conn.commit()
    return {"status": "success"}

@app.delete("/api/todos/completed")
def delete_completed_todos():
    """完了済みタスクの一括削除"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM todos WHERE is_completed = 1")
        conn.commit()
    return {"status": "success"}

# --- 画面の配信 ---
@app.get("/")
def read_index():
    return FileResponse("index.html")
