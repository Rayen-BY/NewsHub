from fastapi import FastAPI, Form, HTTPException, Body, Request
from fastapi.responses import RedirectResponse
import mysql.connector
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import time
import bcrypt
from datetime import datetime

app = FastAPI()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    process_time = time.time() - start_time
    print(f"Finished request: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.2f}s")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Temporarily allow ALL for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"Hello": "World"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def parse_publication_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    safe_value = value.strip()
    if not safe_value:
        return None

    if safe_value.endswith("Z"):
        safe_value = safe_value.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(safe_value)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def get_or_create_interest_id(cursor, category: Optional[str]) -> Optional[int]:
    if not category:
        return None

    normalized = category.strip()
    if not normalized:
        return None

    cursor.execute("SELECT id FROM interests WHERE LOWER(name) = LOWER(%s)", (normalized,))
    existing = cursor.fetchone()
    if existing:
        return existing[0]

    display_name = normalized[0].upper() + normalized[1:].lower() if len(normalized) > 1 else normalized.upper()
    cursor.execute("INSERT INTO interests (name) VALUES (%s)", (display_name,))
    return cursor.lastrowid


def upsert_news_record(cursor, article) -> int:
    article_url = (article.source_url or "").strip()
    if not article_url:
        raise HTTPException(status_code=400, detail="Article URL is required")

    source_name = (article.source_name or "Unknown source").strip() or "Unknown source"

    cursor.execute(
        """
        INSERT INTO source (source_name, source_url)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
            id = LAST_INSERT_ID(id),
            source_url = VALUES(source_url)
        """,
        (source_name, article_url),
    )
    source_id = cursor.lastrowid

    interest_id = get_or_create_interest_id(cursor, article.category)
    published_at = parse_publication_date(article.published_at)
    article_content = article.content or article.description

    cursor.execute(
        """
        INSERT INTO news (
            external_id,
            title,
            content,
            image_url,
            article_url,
            published_at,
            interest_id,
            source_id,
            datatype,
            country
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            id = LAST_INSERT_ID(id),
            external_id = VALUES(external_id),
            title = VALUES(title),
            content = VALUES(content),
            image_url = VALUES(image_url),
            published_at = VALUES(published_at),
            interest_id = VALUES(interest_id),
            source_id = VALUES(source_id),
            datatype = VALUES(datatype),
            country = VALUES(country)
        """,
        (
            article.article_id,
            article.title,
            article_content,
            article.image_url,
            article_url,
            published_at,
            interest_id,
            source_id,
            article.datatype,
            article.country,
        ),
    )
    return cursor.lastrowid

# Database Settings
db_config = {
    'host': '127.0.0.1', # Use explicit IP
    'user': 'root',      
    'password': '',      
    'database': 'newshub1',
    'connect_timeout': 5 # 5 seconds timeout
}

@app.post("/register")
def register_user(
    full_name: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...)
):
    conn = None
    try:
        print(f"--- Registration attempt for {email} ---")
        print("Connecting to database...")
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print("Connected. Executing insert...")

        password_hash = hash_password(password)
        query = "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(query, (full_name, email, password_hash))
        
        print("Insert executed. Committing...")
        conn.commit()
        user_id = cursor.lastrowid
        
        print(f"Success! User ID: {user_id}")
        return {"message": "Success", "user_id": user_id}

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        if err.errno == 1062:
            raise HTTPException(status_code=400, detail="This email is already registered. Please use a different one.")
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            print("Database connection closed.")
        print("--- Registration attempt finished ---")

@app.get("/interests")
def get_interests():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM interests")
        rows = cursor.fetchall()
        interests = [{"id": row[0], "name": row[1]} for row in rows]
        return interests
    except Exception as e:
        print(f"Error fetching interests: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch interests")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.post("/save-interests")
def save_interests(user_id: int = Body(...), interest_ids: List[int] = Body(...)):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Delete existing interests for this user to avoid duplicates if re-submitting
        cursor.execute("DELETE FROM user_interests WHERE user_id = %s", (user_id,))
        
        # Insert new interests
        query = "INSERT INTO user_interests (user_id, interest_id) VALUES (%s, %s)"
        data = [(user_id, i_id) for i_id in interest_ids]
        cursor.executemany(query, data)
        
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Interests saved successfully"}

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))

from pydantic import BaseModel

class SignupData(BaseModel):
    full_name: str
    email: str
    password: str
    interest_ids: List[int]

@app.post("/complete-signup")
async def complete_signup(data: SignupData):
    full_name = data.full_name
    email = data.email
    password = data.password
    interest_ids = data.interest_ids

    conn = None
    try:
        print(f"--- Atomic Signup attempt for {email} ---")
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Start transaction
        conn.start_transaction()

        # 1. Insert User with a hashed password
        password_hash = hash_password(password)
        query_user = "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)"
        try:
            cursor.execute(query_user, (full_name, email, password_hash))
        except mysql.connector.Error as err:
            if err.errno == 1062:
                raise HTTPException(status_code=400, detail="This email is already registered.")
            raise err
            
        user_id = cursor.lastrowid
        print(f"User created with ID: {user_id}")

        # 2. Insert Interests
        if interest_ids:
            query_interests = "INSERT INTO user_interests (user_id, interest_id) VALUES (%s, %s)"
            interest_data = [(user_id, i_id) for i_id in interest_ids]
            cursor.executemany(query_interests, interest_data)
            print(f"Linked {len(interest_ids)} interests.")

        conn.commit()
        print("Signup transaction committed successfully.")
        return {"message": "Signup complete", "user_id": user_id}

    except HTTPException as he:
        if conn: conn.rollback()
        raise he
    except mysql.connector.Error as err:
        if conn: conn.rollback()
        print(f"Database error during signup: {err}")
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    except Exception as e:
        if conn: conn.rollback()
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            print("Database connection closed.")
        print("--- Atomic Signup finished ---")

@app.get("/check-email/{email}")
def check_email(email: str):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        return {"exists": user is not None}
    except Exception as e:
        print(f"Error checking email: {e}")
        raise HTTPException(status_code=500, detail="Error checking email")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

class LoginData(BaseModel):
    email: str
    password: str


class FavoriteArticleData(BaseModel):
    article_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    source_url: str
    source_name: Optional[str] = None
    published_at: Optional[str] = None
    category: Optional[str] = None
    datatype: Optional[str] = None
    country: Optional[str] = None


class SaveFavoriteRequest(BaseModel):
    user_id: int
    article: FavoriteArticleData


class RemoveFavoriteRequest(BaseModel):
    user_id: int
    news_id: Optional[int] = None
    article_url: Optional[str] = None


class CommentRequest(BaseModel):
    user_id: int
    article: FavoriteArticleData
    comment_text: str


def ensure_user_exists(cursor, user_id: int) -> None:
    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

@app.post("/login")
def login(data: LoginData):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, full_name, email, password_hash FROM users WHERE email = %s", (data.email,))
        user = cursor.fetchone()
        
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user.pop("password_hash", None)
            
        return {"message": "Login successful", "user": user}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@app.post("/favorites")
def save_favorite(payload: SaveFavoriteRequest): #model :319
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor() # création du curseur SQL.
        conn.start_transaction() # démarre explicitement une transaction.
        ensure_user_exists(cursor, payload.user_id)   #vérifie que l’utilisateur existe; sinon lève HTTP 401.

        news_id = upsert_news_record(cursor, payload.article) #vérifie que l’utilisateur existe; sinon lève HTTP 401 puis récupère son id.

        cursor.execute(
            """
            INSERT INTO favorite (user_id, news_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE saved_at = CURRENT_TIMESTAMP
            """,
            (payload.user_id, news_id),
        )

        conn.commit()
        return {"message": "Article saved", "news_id": news_id}

    except HTTPException as he:
        if conn:
            conn.rollback()
        raise he
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@app.post("/comments")
def add_comment(payload: CommentRequest):
    conn = None
    try:
        cleaned_comment = payload.comment_text.strip()
        if not cleaned_comment:
            raise HTTPException(status_code=400, detail="Comment text is required")

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        conn.start_transaction()
        ensure_user_exists(cursor, payload.user_id)

        news_id = upsert_news_record(cursor, payload.article)

        cursor.execute(
            """
            INSERT INTO comments (user_id, news_id, comment_content)
            VALUES (%s, %s, %s)
            """,
            (payload.user_id, news_id, cleaned_comment),
        )

        conn.commit()
        return {"message": "Comment added", "comment_id": cursor.lastrowid, "news_id": news_id}

    except HTTPException as he:
        if conn:
            conn.rollback()
        raise he
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@app.delete("/favorites")
def remove_favorite(payload: RemoveFavoriteRequest):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        if payload.news_id is not None:
            cursor.execute(
                "DELETE FROM favorite WHERE user_id = %s AND news_id = %s",
                (payload.user_id, payload.news_id),
            )
        elif payload.article_url:
            cursor.execute(
                """
                DELETE f
                FROM favorite f
                INNER JOIN news n ON n.id = f.news_id
                WHERE f.user_id = %s AND n.article_url = %s
                """,
                (payload.user_id, payload.article_url),
            )
        else:
            raise HTTPException(status_code=400, detail="Provide news_id or article_url")

        conn.commit()
        return {"message": "Article removed from favorites", "removed": cursor.rowcount > 0}

    except HTTPException as he:
        raise he
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@app.get("/favorites-status")
def check_favorite(user_id: int, article_url: str):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT f.news_id
            FROM favorite f
            INNER JOIN news n ON n.id = f.news_id
            WHERE f.user_id = %s AND n.article_url = %s
            LIMIT 1
            """,
            (user_id, article_url),
        )
        row = cursor.fetchone()
        return {"saved": row is not None, "news_id": row["news_id"] if row else None}

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@app.get("/favorites/{user_id}")
def get_favorites(user_id: int):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                n.id,
                n.external_id,
                n.title,
                n.content,
                n.image_url,
                n.article_url,
                n.published_at,
                COALESCE(i.name, 'Technology') AS category,
                COALESCE(s.source_name, 'Unknown source') AS source_name,
                f.saved_at
            FROM favorite f
            INNER JOIN news n ON n.id = f.news_id
            LEFT JOIN interests i ON i.id = n.interest_id
            LEFT JOIN source s ON s.id = n.source_id
            WHERE f.user_id = %s
            ORDER BY f.saved_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()

        favorites = [
            {
                "news_id": row["id"],
                "id": row["external_id"] or str(row["id"]),
                "title": row["title"],
                "description": row["content"] or "",
                "content": row["content"] or "",
                "imageUrl": row["image_url"] or "",
                "sourceName": row["source_name"],
                "publishedAt": row["published_at"].isoformat() if row["published_at"] else datetime.utcnow().isoformat(),
                "url": row["article_url"],
                "category": row["category"].lower(),
                "savedAt": row["saved_at"].isoformat() if row["saved_at"] else None,
            }
            for row in rows
        ]
        return favorites

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@app.get("/comments")
def get_comments(article_url: str):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                c.comment_id,
                c.comment_content,
                c.createdAt,
                u.id AS user_id,
                u.full_name
            FROM comments c
            INNER JOIN users u ON u.id = c.user_id
            INNER JOIN news n ON n.id = c.news_id
            WHERE n.article_url = %s
            ORDER BY c.createdAt DESC
            """,
            (article_url,),
        )
        rows = cursor.fetchall()
        return [
            {
                "comment_id": row["comment_id"],
                "comment_content": row["comment_content"],
                "createdAt": row["createdAt"].isoformat() if row["createdAt"] else None,
                "user_id": row["user_id"],
                "full_name": row["full_name"],
            }
            for row in rows
        ]

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# To run: uvicorn main:app --reload
