from fastapi import FastAPI, Depends, Form, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime
from fastapi.responses import RedirectResponse
from sqlalchemy import func

from .database import engine, Base, SessionLocal
from . import models
from .auth import hash_password, verify_password

import re

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="your-secret-key"
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ログイン画面
@app.get("/")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


# 新規登録画面
@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={}
    )


# 新規登録処理
@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    hashed_password = hash_password(password)

    if username == "admin":
        role = "admin"
    else:
        role = "user"

    user = models.User(
        username=username,
        password=hashed_password,
        name=name,
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return templates.TemplateResponse(
        request=request,
        name="register_success.html",
        context={
            "message": "ユーザー登録成功",
            "username": user.username
        }
    )

# ホーム画面

@app.get("/home")
def home_page(request: Request, db: Session = Depends(get_db)):
    # セッションからユーザー名を取得
    username = request.session.get("username")

    # 未ログインの場合
    if not username:
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # データベースからユーザー情報を取得
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    # ユーザーが存在しない場合
    if not user:
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # 未読通知件数
    unread_count = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username,
        models.Notification.is_read == False
    ).count()

    # 通知一覧（新しい順に5件）
    notifications = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username
    ).order_by(
        models.Notification.created_at.desc()
    ).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "user_name": user.username,
            "name": getattr(user, "name", user.username),
            "username": user.username,
            "unread_count": unread_count,
            "notifications": notifications
        }
    )

# ログイン処理
@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    # ユーザーが存在しない
    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="login_error.html",
            context={
                "message": "ユーザー名またはパスワードが違います"
            }
        )

    # パスワードが違う
    if not verify_password(password, user.password):
        return templates.TemplateResponse(
            request=request,
            name="login_error.html",
            context={
                "message": "ユーザー名またはパスワードが違います"
            }
        )

    # ログイン成功

    # ログイン成功

    request.session["username"] = user.username
    request.session["name"] = user.name
    request.session["role"] = user.role

    if user.role == "admin":
        return RedirectResponse(
            url="/admin/home",
            status_code=303
        )

    else:
        return RedirectResponse(
            url="/home",
            status_code=303
        )

@app.post("/logout")
def logout(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )

@app.get("/inquiry/register")
def inquiry_register_page(
    request: Request,
    db: Session = Depends(get_db)
):
    username = request.session.get("username")
    name = request.session.get("name")

    # 未ログイン
    if not username:
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # 未読通知件数
    unread_count = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username,
        models.Notification.is_read == False
    ).count()

    # 通知一覧（新しい順に5件）
    notifications = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username
    ).order_by(
        models.Notification.created_at.desc()
    ).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="inquiry_register.html",
        context={
            "username": username,
            "name": name,
            "unread_count": unread_count,
            "notifications": notifications
        }
    )

@app.post("/inquiry/register")
def inquiry_register(
    request: Request,
    category: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    priority: str = Form(...),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    username = request.session.get("username")

    inquiry = models.Inquiry(
        username=username,
        category=category,
        title=title,
        content=content,
        priority=priority,
        status="未対応"
    )

    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    #担当staffへの通知

    staff_users = db.query(models.User).filter(
        models.User.role == "staff",
        models.User.staff_category == category
    ).all()

    for staff in staff_users:
        notification = models.Notification(
            username=staff.username,
            message=f"新しい問い合わせがあります:{title}",
            inquiry_id=inquiry.id,
            is_read=False
        )

        db.add(notification)

    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="inquiry_register_success.html",
        context={
            "message": "問い合わせを登録しました",
            "title": inquiry.title
        }
    )

@app.get("/inquiry/history")
def get_history(
    request: Request,
    db: Session = Depends(get_db)
):
    username = request.session.get("username")
    role = request.session.get("role")

    # 未ログイン
    if not username:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    # ログインユーザー取得
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "ユーザーが見つかりません"
            }
        )

    # 管理者
    if role == "admin":

        inquiries = db.query(
            models.Inquiry
        ).order_by(
            models.Inquiry.created_at.desc()
        ).all()

    # staff
    elif role == "staff":

        inquiries = db.query(
            models.Inquiry
        ).filter(
            (models.Inquiry.username == username) |
            (models.Inquiry.category == user.staff_category)
        ).order_by(
            models.Inquiry.created_at.desc()
        ).all()

    # 一般ユーザー
    else:

        inquiries = db.query(
            models.Inquiry
        ).filter(
            models.Inquiry.username == username
        ).order_by(
            models.Inquiry.created_at.desc()
        ).all()

    unread_count = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username,
        models.Notification.is_read == False
    ).count()

    notifications = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username
    ).order_by(
        models.Notification.created_at.desc()
    ).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="inquiry_history.html",
        context={
            "user_name": username,
            "name": user.name,
            "role": role,
            "inquiries": inquiries,
            "unread_count": unread_count,
            "notifications": notifications
        }
    )

@app.get("/profile")
def get_profile(request: Request, db: Session = Depends(get_db)):
    # 1. セッションからユーザー名を取得
    username = request.session.get("username")
    
    # 2. 未ログインの場合はログイン画面へリダイレクト
    if not username:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # 3. データベースから該当ユーザーの情報を取得
    user = db.query(models.User).filter(models.User.username == username).first()
    
    # ユーザーが存在しない場合（退会済みなど）の安全策
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    unread_count = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username,
        models.Notification.is_read == False
    ).count()

    notifications = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username
    ).order_by(
        models.Notification.created_at.desc()
    ).limit(5).all()

    # 4. プロフィール用テンプレート（profile.html）をレンダリング
    return templates.TemplateResponse(
        request=request, 
        name="profile.html", 
        context={
            "user_name": user.username, # ヘッダー表示用
            "name": getattr(user, "name", user.username), # 氏名カラムがない場合は username で代用
            "username": user.username,
            "unread_count": unread_count,
            "notifications": notifications
        }
    )

@app.post("/profile/username")
def update_username(
    request: Request,
    new_username: str = Form(...),
    db: Session = Depends(get_db)
):
    # ログインユーザー取得
    username = request.session.get("username")

    if not username:
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # 前後の空白を削除
    new_username = new_username.strip()

    # -------------------------
    # ID形式チェック
    # -------------------------

    if len(new_username) < 3 or len(new_username) > 50:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "ユーザーIDは3～50文字で入力してください"
            }
        )

    if not re.fullmatch(r"[A-Za-z0-9_]+", new_username):
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "ユーザーIDは英数字と「_」のみ使用できます"
            }
        )

    # 現在のユーザー取得
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # 同じIDなら何もしない
    if new_username == username:
        return RedirectResponse(
            url="/profile",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # -------------------------
    # 重複チェック
    # -------------------------

    existing_user = db.query(models.User).filter(
        models.User.username == new_username
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "そのユーザーIDはすでに使用されています"
            }
        )

    # -------------------------
    # ID変更
    # -------------------------

    user.username = new_username

    db.commit()

    # セッション更新
    request.session["username"] = new_username

    return RedirectResponse(
        url="/profile",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/profile/password")
def update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    username = request.session.get("username")

    if not username:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # ユーザー取得
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # 現在のパスワード確認
    if not verify_password(current_password, user.password):
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "現在のパスワードが正しくありません"
            }
        )

    # 新しいパスワード確認
    if new_password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "新しいパスワードが一致していません"
            }
        )

    # 新しいパスワードをハッシュ化
    user.password = hash_password(new_password)

    db.commit()

    return RedirectResponse(
        url="/profile",
        status_code=303
    )

@app.get("/inquiry/{inquiry_id}")
def inquiry_detail(
    inquiry_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    # ログイン情報
    username = request.session.get("username")
    role = request.session.get("role")

    # 未ログイン
    if not username:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={}
        )

    # ログインユーザー取得
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    # 問い合わせ取得
    inquiry = db.query(models.Inquiry).filter(
        models.Inquiry.id == inquiry_id
    ).first()

    # 問い合わせが存在しない
    if inquiry is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "問い合わせが見つかりません"
            }
        )

    # =========================
    # 権限チェック
    # =========================

    # adminは全問い合わせOK
    if role == "admin":
        pass

    # staffの場合
    elif role == "staff":

        # 自分の問い合わせ
        if inquiry.username == username:
            pass

        # 担当カテゴリの問い合わせ
        elif user.staff_category == inquiry.category:
            pass

        # それ以外はアクセス禁止
        else:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "message": "この問い合わせを閲覧する権限がありません"
                }
            )

    # 一般ユーザー
    else:

        # 自分の問い合わせ以外は禁止
        if inquiry.username != username:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "message": "この問い合わせを閲覧する権限がありません"
                }
            )

    unread_count = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username,
        models.Notification.is_read == False
    ).count()

    notifications = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username
    ).order_by(
        models.Notification.created_at.desc()
    ).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="inquiry_detail.html",
        context={
            "name": request.session.get("name"),
            "role": role,
            "staff_category": user.staff_category,
            "inquiry": inquiry,
            "unread_count": unread_count,
            "notifications": notifications
        }
    )   

@app.post("/inquiry/{inquiry_id}/response")
def inquiry_response(
    inquiry_id: int,
    request: Request,
    response: str = Form(...),
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    # ログイン情報
    username = request.session.get("username")
    role = request.session.get("role")

    # 未ログイン
    if not username:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={}
        )

    # ログインユーザー取得
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    # 問い合わせ取得
    inquiry = db.query(models.Inquiry).filter(
        models.Inquiry.id == inquiry_id
    ).first()

    # 問い合わせが存在しない
    if inquiry is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "問い合わせが見つかりません"
            }
        )

    # =========================
    # 回答権限チェック
    # =========================

    # admin → 全問い合わせ回答OK
    if role == "admin":
        pass

    # staff → 担当カテゴリのみ回答OK
    elif role == "staff":

        if user.staff_category != inquiry.category:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "message": "この問い合わせに回答する権限がありません"
                }
            )

    # user → 回答不可
    else:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "回答する権限がありません"
            }
        )

    # =========================
    # 回答内容を保存
    # =========================

    inquiry.response = response
    inquiry.status = status

    db.commit()
    db.refresh(inquiry)

    #申請者への通知

    notification = models.Notification(
        username=inquiry.username,
        message=f"問い合わせ「{inquiry.title}」に回答があります",
        inquiry_id=inquiry.id,
        is_read=False
    )

    db.add(notification)
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="inquiry_detail.html",
        context={
            "name": request.session.get("name"),
            "role": role,
            "inquiry": inquiry
        }
    )

@app.get("/admin/home")
def admin_home(
    request: Request,
    db: Session = Depends(get_db)
):
    #ログインユーザーの情報を取得
    username = request.session.get("username")
    name = request.session.get("name")
    role = request.session.get("role")

    #管理者以外はアクセスさせない
    if role != "admin":
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={}
        )

    #未対応件数
    pending_count = db.query(models.Inquiry).filter(
        models.Inquiry.status == "未対応"
    ).count()

    #今月の開始日時
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)

    #今月の対応件数
    #「対応中」または「対応済」を対応件数としてカウント
    response_count = db.query(models.Inquiry).filter(
        models.Inquiry.created_at >= month_start,
        models.Inquiry.status.in_(["対応中", "対応済"])
    ).count()

    #今月の完了件数
    completed_count = db.query(models.Inquiry).filter(
        models.Inquiry.created_at >= month_start,
        models.Inquiry.status == "対応済"
    ).count()

    category_counts = db.query(
        models.Inquiry.category,
        func.count(models.Inquiry.id)
    ).group_by(
        models.Inquiry.category
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin_home.html",
        context={
            "username": username,
            "name": name,
            "role": role,
            "pending_count": pending_count,
            "response_count": response_count,
            "completed_count": completed_count,
            "category_counts": category_counts
        }
    )

@app.get("/admin/staff")
def admin_staff(
    request: Request,
    db: Session = Depends(get_db)
):

    #ログイン情報
    username = request.session.get("username")
    name = request.session.get("name")
    role = request.session.get("role")

    #管理者以外はアクセス禁止
    if role != "admin":
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={}
        )

    #ユーザーを取得
    users = db.query(models.User).order_by(
        models.User.id
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin_staff.html",
        context={
            "username": username,
            "name": name,
            "role": role,
            "users": users
        }
    )

@app.post("/admin/staff/{user_id}")
def update_staff_category(
    user_id: int,
    request: Request,
    staff_category: str = Form(...),
    db: Session = Depends(get_db)
):
    # ログインユーザーの権限
    role = request.session.get("role")

    # 管理者以外は変更不可
    if role != "admin":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "権限がありません"
            }
        )

    # ユーザー取得
    user = db.query(models.User).filter(
        models.User.id == user_id
    ).first()

    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "ユーザーが見つかりません"
            }
        )

    # 担当カテゴリを変更
    user.staff_category = staff_category if staff_category else None

    # staff_categoryが設定されたらstaffにする
    if user.role != "admin":
        if staff_category:
            user.role = "staff"
        else:
            user.role = "user"

    db.commit()

    # 担当者変更画面へ戻る
    return RedirectResponse(
        url="/admin/staff",
        status_code=303
    )

@app.get("/admin/inquiry")
def admin_inquiry(
    request: Request,
    db:Session = Depends(get_db)
):

    #管理者チェック
    if request.session.get("role") != "admin":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "権限がありません"
            }
        )

    #全問い合わせ取得
    inquiries = db.query(
        models.Inquiry
    ).order_by(
        models.Inquiry.created_at.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin_inquiry.html",
        context={
            "name": request.session.get("name"),
            "role": request.session.get("role"),
            "inquiries": inquiries
        }
    )

@app.get("/admin/inquiry/{inquiry_id}")
def admin_inquiry_detail(
    inquiry_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    #管理者チェック
    if request.session.get("role") != "admin":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "権限がありません"
            }
        )

    #問い合わせ取得
    inquiry = db.query(models.Inquiry).filter(
        models.Inquiry.id == inquiry_id
    ).first()

    if inquiry is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "問い合わせが見つかりません"
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="admin_inquiry_detail.html",
        context={
            "name": request.session.get("name"),
            "role": request.session.get("role"),
            "inquiry": inquiry
        }
    )

@app.get("/admin/inquiry/{inquiry_id}/edit")
def admin_inquiry_edit_page(
    inquiry_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    #管理者チェック
    if request.session.get("role") != "admin":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message":"権限がありません"
            }
        )
    
    #問い合わせ取得
    inquiry = db.query(models.Inquiry).filter(
        models.Inquiry.id == inquiry_id
    ).first()

    if inquiry is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "問い合わせが見つかりません"
            }
        )

    
    return templates.TemplateResponse(
        request=request,
        name="admin_inquiry_edit.html",
        context={
            "name": request.session.get("name"),
            "role": request.session.get("role"),
            "inquiry": inquiry
        }
    )

@app.post("/admin/inquiry/{inquiry_id}/edit")
def admin_inquiry_edit(
    inquiry_id: int,
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    priority: str = Form(...),
    status: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

        #管理者チェック
    if request.session.get("role") != "admin":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message":"権限がありません"
            }
        )
    
    #問い合わせ取得
    inquiry = db.query(models.Inquiry).filter(
        models.Inquiry.id == inquiry_id
    ).first()

    if inquiry is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "問い合わせが見つかりません"
            }
        )

    #DB更新
    inquiry.title = title
    inquiry.category = category
    inquiry.priority = priority
    inquiry.status = status
    inquiry.content = content

    db.commit()
    db.refresh(inquiry)

    return RedirectResponse(
        url=f"/admin/inquiry/{inquiry.id}",
        status_code=303
    )


@app.post("/admin/inquiry/{inquiry_id}/delete")
def admin_inquiry_delete(
    inquiry_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    # 管理者チェック
    if request.session.get("role") != "admin":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "権限がありません"
            }
        )

    # 問い合わせ取得
    inquiry = db.query(models.Inquiry).filter(
        models.Inquiry.id == inquiry_id
    ).first()

    if inquiry is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "問い合わせが見つかりません"
            }
        )

    #削除
    db.delete(inquiry)
    db.commit()

     # 管理者一覧へ戻る
    return RedirectResponse(
        url="/admin/inquiry",
        status_code=303
    )

@app.get("/notifications")
def notifications_page(
    request: Request,
    db: Session = Depends(get_db)
):
    username = request.session.get("username")

    # 未ログイン
    if not username:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    notifications = db.query(
        models.Notification
    ).filter(
        models.Notification.username == username
    ).order_by(
        models.Notification.created_at.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="notifications.html",
        context={
            "name": request.session.get("name"),
            "notifications": notifications
        }
    )

@app.get("/notifications/{notification_id}")
def open_notification(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    username = request.session.get("username")

    # 未ログイン
    if not username:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # 自分の通知だけ取得
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.username == username
    ).first()

    if notification is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "message": "通知が見つかりません"
            }
        )

    # 既読にする
    notification.is_read = True
    db.commit()

    # 対象問い合わせへ移動
    return RedirectResponse(
        url=f"/inquiry/{notification.inquiry_id}",
        status_code=303
    )