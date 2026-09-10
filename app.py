# -*- coding: utf-8 -*-
"""
校园二手交易平台 - 主应用文件
"""

from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, send, emit, join_room, leave_room
# 不使用 werkzeug.security，手动处理密码
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timezone, timedelta, timedelta

# 创建Flask应用
app = Flask(__name__)

# 添加Jinja2全局函数：UTC时间转本地时间
def to_local_time(dt):
    """将UTC时间转换为本地时间字符串"""
    if dt is None:
        return ''
    try:
        # 统一将时间视为UTC，加上8小时
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        return local_dt.strftime('%H:%M')
    except Exception as e:
        # 如果转换失败，手动加8小时
        try:
            return (dt + timedelta(hours=8)).strftime('%H:%M')
        except:
            return str(dt)

# 注册到Jinja2全局上下文
app.jinja_env.globals.update(to_local_time=to_local_time)

# 添加Jinja2过滤器（备用）
@app.template_filter('localtime')
def localtime_filter_v2(dt):
    """将UTC时间转换为本地时间（备用过滤器）"""
    return to_local_time(dt)

# 获取项目根目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SECRET_KEY'] = 'campus-trading-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "campus_trading.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 文件上传配置
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static', 'chat'), exist_ok=True)

# 初始化扩展
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== 数据库模型 ====================

class User(db.Model):
    """用户模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    contact = db.Column(db.String(100))
    guest_id = db.Column(db.String(64), unique=True)  # 游客ID
    is_guest = db.Column(db.Boolean, default=False)   # 是否是游客账号
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # 关系
    goods = db.relationship('Goods', backref='seller', lazy='dynamic')
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic')
    comments = db.relationship('Comment', backref='user', lazy='dynamic')

    def set_password(self, password):
        import hashlib
        # 手动设置密码，不使用 werkzeug
        self.password_hash = 'sha256$' + hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        import hashlib
        return self.password_hash == 'sha256$' + hashlib.sha256(password.encode()).hexdigest()

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.username}>'


class Goods(db.Model):
    """商品模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0)  # 售价
    original_price = db.Column(db.Float)  # 原价（非必填）
    category = db.Column(db.String(50))  # 分类：教材、数码、生活、其他
    condition = db.Column(db.String(20))  # 成色：全新、九成新、八成新等
    image = db.Column(db.String(200))  # 图片路径
    status = db.Column(db.String(20), default='在售')  # 在售、已售出、已下架
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def get_reference_price(self):
        """计算参考价格"""
        if not self.original_price or not self.condition:
            return None
        discount_rates = {
            '全新': 0.9,
            '九成新': 0.8,
            '八成新': 0.7,
            '七成新': 0.6,
            '六成及以下': 0.5
        }
        rate = discount_rates.get(self.condition, 0.5)
        return round(self.original_price * rate, 2)

    # 关系
    favorites = db.relationship('Favorite', backref='goods', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='goods', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Goods {self.title}>'


class Favorite(db.Model):
    """收藏模型"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('user_id', 'goods_id', name='unique_favorite'),)

    def __repr__(self):
        return f'<Favorite user={self.user_id} goods={self.goods_id}>'


class Comment(db.Model):
    """留言模型"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Comment {self.id}>'


# ==================== 私聊模型 ====================

class ChatRoom(db.Model):
    """私聊房间模型"""
    id = db.Column(db.Integer, primary_key=True)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)  # 为了快速获取商品信息
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 买家
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 卖家
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # 关系
    goods = db.relationship('Goods', backref=db.backref('chat_rooms', lazy='dynamic'))
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref=db.backref('buyer_chats', lazy='dynamic'))
    seller = db.relationship('User', foreign_keys=[seller_id], backref=db.backref('seller_chats', lazy='dynamic'))
    messages = db.relationship('ChatMessage', backref='room', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ChatRoom {self.id}>'


class ChatMessage(db.Model):
    """私聊消息模型"""
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, image, goods_link
    content = db.Column(db.Text, nullable=False)  # 消息内容或图片URL
    is_read = db.Column(db.Boolean, default=False)  # 是否已读
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    sender = db.relationship('User', backref=db.backref('sent_messages', lazy='dynamic'))

    def __repr__(self):
        return f'<ChatMessage {self.id}>'


# 用户加载函数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== 自动登录功能 ====================

@app.route('/auto_login')
def auto_login():
    """自动登录：游客自动注册并登录"""
    # 获取或创建游客ID
    guest_id = request.cookies.get('guest_id')
    if not guest_id:
        import uuid
        guest_id = str(uuid.uuid4())

    # 查找是否已经有这个游客的账号
    user = User.query.filter_by(guest_id=guest_id).first()

    if not user:
        # 创建新游客账号（用户名用guest+随机数）
        import random
        username = f'guest_{random.randint(1000, 9999)}'
        user = User(username=username, is_guest=True, guest_id=guest_id)
        user.set_password(guest_id)  # 用guest_id作为密码
        db.session.add(user)
        db.session.commit()

    # 登录用户
    login_user(user)

    # 设置cookie
    response = make_response(redirect(url_for('index')))
    response.set_cookie('guest_id', guest_id, max_age=365*24*60*60)  # 有效期1年
    return response


@app.route('/upgrade_account', methods=['GET', 'POST'])
@login_required
def upgrade_account():
    """升级游客账号为正式账号"""
    if not current_user.is_guest:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        contact = request.form.get('contact')

        # 检查用户名是否已存在
        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('用户名已存在', 'danger')
            return redirect(url_for('upgrade_account'))

        # 升级账号
        current_user.username = username
        current_user.contact = contact
        current_user.set_password(password)
        current_user.is_guest = False
        current_user.guest_id = None
        db.session.commit()

        flash('账号升级成功！请记住您的用户名和密码', 'success')
        return redirect(url_for('index'))

    return render_template('upgrade_account.html')


# ==================== 路由定义 ====================

@app.route('/')
def index():
    """首页"""
    # 对于未登录的游客，自动登录
    if not current_user.is_authenticated:
        return redirect(url_for('auto_login'))

    # 获取最新商品（最多6个）
    goods_list = Goods.query.filter_by(status='在售').order_by(Goods.created_at.desc()).limit(6).all()
    return render_template('index.html', goods_list=goods_list)


@app.route('/goods')
def goods_list():
    """商品列表"""
    category = request.args.get('category', 'all')
    status_filter = request.args.get('status', '在售')

    query = Goods.query
    if category and category != 'all':
        query = query.filter_by(category=category)
    if status_filter:
        query = query.filter_by(status=status_filter)

    goods_list = query.order_by(Goods.created_at.desc()).all()
    return render_template('goods_list.html', goods_list=goods_list, current_category=category)


@app.route('/goods/<int:goods_id>')
def goods_detail(goods_id):
    """商品详情"""
    goods = Goods.query.get_or_404(goods_id)
    # 获取留言
    comments = Comment.query.filter_by(goods_id=goods_id).order_by(Comment.created_at.desc()).all()
    # 检查是否已收藏
    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = Favorite.query.filter_by(user_id=current_user.id, goods_id=goods_id).first() is not None

    return render_template('goods_detail.html', goods=goods, comments=comments, is_favorited=is_favorited)


@app.route('/goods/publish', methods=['GET', 'POST'])
@login_required
def publish_goods():
    """发布商品"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = float(request.form.get('price', 0))
        # 处理原价（非必填，传空字符串时设为None）
        original_price_str = request.form.get('original_price')
        original_price = float(original_price_str) if original_price_str else None
        category = request.form.get('category')
        condition = request.form.get('condition')

        # 处理图片上传 - 使用相对路径便于部署
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                # 添加时间戳避免重名
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                # 使用相对路径存储到数据库
                image_path = f"static/uploads/{filename}"

        goods = Goods(
            title=title,
            description=description,
            price=price,
            original_price=original_price,
            category=category,
            condition=condition,
            image=image_path,
            user_id=current_user.id
        )
        db.session.add(goods)
        db.session.commit()

        flash('商品发布成功！', 'success')
        return redirect(url_for('goods_detail', goods_id=goods.id))

    return render_template('publish_goods.html')


@app.route('/goods/<int:goods_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_goods(goods_id):
    """编辑商品"""
    goods = Goods.query.get_or_404(goods_id)

    # 检查权限
    if goods.user_id != current_user.id:
        flash('您没有权限编辑此商品', 'danger')
        return redirect(url_for('goods_detail', goods_id=goods_id))

    if request.method == 'POST':
        goods.title = request.form.get('title')
        goods.description = request.form.get('description')
        goods.price = float(request.form.get('price', 0))
        # 处理原价（非必填）
        original_price_str = request.form.get('original_price')
        goods.original_price = float(original_price_str) if original_price_str else None
        goods.category = request.form.get('category')
        goods.condition = request.form.get('condition')
        goods.status = request.form.get('status')

        # 处理图片上传 - 使用相对路径便于部署
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                goods.image = f"static/uploads/{filename}"

        db.session.commit()
        flash('商品更新成功！', 'success')
        return redirect(url_for('goods_detail', goods_id=goods_id))

    return render_template('edit_goods.html', goods=goods)


@app.route('/goods/<int:goods_id>/delete', methods=['POST'])
@login_required
def delete_goods(goods_id):
    """删除商品"""
    goods = Goods.query.get_or_404(goods_id)

    if goods.user_id != current_user.id:
        flash('您没有权限删除此商品', 'danger')
        return redirect(url_for('goods_detail', goods_id=goods_id))

    db.session.delete(goods)
    db.session.commit()
    flash('商品已删除', 'success')
    return redirect(url_for('my_goods'))


@app.route('/search')
def search():
    """搜索商品"""
    q = request.args.get('q', '')
    if q:
        goods_list = Goods.query.filter(
            Goods.title.contains(q) | Goods.description.contains(q),
            Goods.status == '在售'
        ).all()
    else:
        goods_list = []

    return render_template('search.html', goods_list=goods_list, query=q)


# ==================== 用户相关路由 ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        contact = request.form.get('contact')

        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, contact=contact)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('注册成功！请登录', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('登录成功！', 'success')

            # 跳转到之前访问的页面
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('用户名或密码错误', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """退出登录"""
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))


@app.route('/profile')
@login_required
def profile():
    """个人中心"""
    return render_template('profile.html')


@app.route('/my/goods')
@login_required
def my_goods():
    """我的商品"""
    goods_list = Goods.query.filter_by(user_id=current_user.id).order_by(Goods.created_at.desc()).all()
    return render_template('my_goods.html', goods_list=goods_list)


@app.route('/my/favorites')
@login_required
def my_favorites():
    """我的收藏"""
    favorites = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    goods_list = [f.goods for f in favorites]
    return render_template('my_favorites.html', goods_list=goods_list)


# ==================== 互动功能 ====================

@app.route('/favorite/<int:goods_id>')
@login_required
def add_favorite(goods_id):
    """添加收藏"""
    # 检查是否已收藏
    existing = Favorite.query.filter_by(user_id=current_user.id, goods_id=goods_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('已取消收藏', 'info')
    else:
        favorite = Favorite(user_id=current_user.id, goods_id=goods_id)
        db.session.add(favorite)
        db.session.commit()
        flash('已添加到收藏', 'success')

    return redirect(url_for('goods_detail', goods_id=goods_id))


@app.route('/goods/<int:goods_id>/comment', methods=['POST'])
@login_required
def add_comment(goods_id):
    """添加留言"""
    content = request.form.get('content')
    if not content:
        flash('留言内容不能为空', 'danger')
        return redirect(url_for('goods_detail', goods_id=goods_id))

    comment = Comment(
        user_id=current_user.id,
        goods_id=goods_id,
        content=content
    )
    db.session.add(comment)
    db.session.commit()

    flash('留言成功！', 'success')
    return redirect(url_for('goods_detail', goods_id=goods_id))


# ==================== 价格参考功能 ====================

@app.route('/price/ref')
def price_reference():
    """价格参考说明页面"""
    return render_template('price_reference.html')


# ==================== 实时聊天功能 ====================

@app.route('/chat')
@login_required
def chat():
    """实时聊天页面"""
    return render_template('chat.html')


@socketio.on('connect')
def handle_connect():
    """用户连接时"""
    if current_user.is_authenticated:
        join_room('public_chat')
        emit('system_message', {'msg': f'{current_user.username} 加入了聊天'}, to='public_chat')


@socketio.on('disconnect')
def handle_disconnect():
    """用户断开时"""
    if current_user.is_authenticated:
        emit('system_message', {'msg': f'{current_user.username} 离开了聊天'}, to='public_chat')


@socketio.on('message')
def handle_message(data):
    """接收并转发消息"""
    username = current_user.username if current_user.is_authenticated else '游客'
    msg = data.get('msg', '').strip()

    if msg:
        # 发送消息给所有人
        send({
            'username': username,
            'msg': msg,
            'time': (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%H:%M')
        }, to='public_chat')


# ==================== 私聊功能 ====================

@app.route('/chat/<int:room_id>')
@login_required
def private_chat(room_id):
    """私聊页面"""
    chat_room = ChatRoom.query.get_or_404(room_id)

    # 检查权限：必须是买家或卖家
    if current_user.id not in [chat_room.buyer_id, chat_room.seller_id]:
        flash('无权访问此聊天', 'danger')
        return redirect(url_for('index'))

    # 获取商品信息
    goods = chat_room.goods

    # 获取对方信息
    other_user = chat_room.buyer if current_user.id == chat_room.seller_id else chat_room.seller

    # 获取历史消息
    messages = ChatMessage.query.filter_by(room_id=room_id).order_by(ChatMessage.created_at.asc()).all()

    # 将未读消息标记为已读
    ChatMessage.query.filter(
        ChatMessage.room_id == room_id,
        ChatMessage.sender_id != current_user.id,
        ChatMessage.is_read == False
    ).update({'is_read': True})
    db.session.commit()

    return render_template('private_chat.html',
                         chat_room=chat_room,
                         goods=goods,
                         other_user=other_user,
                         messages=messages)


@app.route('/chat/start/<int:goods_id>', methods=['GET', 'POST'])
@login_required
def start_chat(goods_id):
    """开始私聊（从商品详情页）"""
    goods = Goods.query.get_or_404(goods_id)

    # 不能和自己聊天
    if goods.user_id == current_user.id:
        flash('不能和自己聊天', 'warning')
        return redirect(url_for('goods_detail', goods_id=goods_id))

    # 查找是否已存在聊天房间
    chat_room = ChatRoom.query.filter(
        ((ChatRoom.buyer_id == current_user.id) & (ChatRoom.seller_id == goods.user_id) |
         (ChatRoom.buyer_id == goods.user_id) & (ChatRoom.seller_id == current_user.id)),
        ChatRoom.goods_id == goods_id
    ).first()

    # 如果不存在，创建新的聊天房间
    if not chat_room:
        chat_room = ChatRoom(
            goods_id=goods_id,
            buyer_id=current_user.id,
            seller_id=goods.user_id
        )
        db.session.add(chat_room)
        db.session.commit()

    return redirect(url_for('private_chat', room_id=chat_room.id))


@app.route('/chat/list')
@login_required
def chat_list():
    """我的私聊列表"""
    # 获取所有参与的聊天房间
    rooms = ChatRoom.query.filter(
        (ChatRoom.buyer_id == current_user.id) | (ChatRoom.seller_id == current_user.id)
    ).order_by(ChatRoom.updated_at.desc()).all()

    # 获取每个房间的最新消息和未读数
    chat_data = []
    for room in rooms:
        last_message = ChatMessage.query.filter_by(room_id=room.id).order_by(ChatMessage.created_at.desc()).first()
        unread_count = ChatMessage.query.filter(
            ChatMessage.room_id == room.id,
            ChatMessage.sender_id != current_user.id,
            ChatMessage.is_read == False
        ).count()

        other_user = room.buyer if current_user.id == room.seller_id else room.seller

        chat_data.append({
            'room': room,
            'goods': room.goods,
            'other_user': other_user,
            'last_message': last_message,
            'unread_count': unread_count
        })

    return render_template('chat_list.html', chat_data=chat_data)


# 私聊SocketIO事件
@socketio.on('join_room')
def handle_join_room(data):
    """加入私聊房间"""
    room_id = data.get('room_id')
    if room_id:
        join_room(f'chat_{room_id}')


@socketio.on('leave_room')
def handle_leave_room(data):
    """离开私聊房间"""
    room_id = data.get('room_id')
    if room_id:
        leave_room(f'chat_{room_id}')


@socketio.on('private_message')
def handle_private_message(data):
    """处理私聊消息"""
    if not current_user.is_authenticated:
        return

    room_id = data.get('room_id')
    message_type = data.get('type', 'text')
    content = data.get('content', '').strip()

    if not room_id or not content:
        return

    # 检查权限
    chat_room = ChatRoom.query.get(room_id)
    if not chat_room or current_user.id not in [chat_room.buyer_id, chat_room.seller_id]:
        return

    # 保存消息到数据库
    message = ChatMessage(
        room_id=room_id,
        sender_id=current_user.id,
        message_type=message_type,
        content=content
    )
    db.session.add(message)

    # 更新房间时间
    chat_room.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    # 广播给房间内所有人
    emit('new_private_message', {
        'id': message.id,
        'sender_id': current_user.id,
        'sender_name': current_user.username,
        'type': message_type,
        'content': content,
        'time': to_local_time(message.created_at),
        'is_read': False
    }, room=f'chat_{room_id}')


@app.route('/chat/upload_image', methods=['POST'])
@login_required
def upload_chat_image():
    """上传聊天图片"""
    room_id = request.form.get('room_id')
    if 'image' not in request.files:
        return {'success': False, 'error': '没有文件'}

    file = request.files['image']
    if not file.filename:
        return {'success': False, 'error': '没有选择文件'}

    # 检查权限
    if room_id:
        chat_room = ChatRoom.query.get(room_id)
        if not chat_room or current_user.id not in [chat_room.buyer_id, chat_room.seller_id]:
            return {'success': False, 'error': '无权上传'}

    # 保存图片 - 使用相对路径便于部署
    import uuid
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
    filename = f"chat/{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(BASE_DIR, 'static', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    return {'success': True, 'filename': f"static/{filename}"}


# ==================== 启动应用 ====================

if __name__ == '__main__':
    # 创建数据库
    with app.app_context():
        db.create_all()
        print("✅ 数据库创建成功！" if os.path.exists('campus_trading.db') else "数据库已存在")

    print("🚀 校园二手交易平台启动中...")

    # Railway 或生产环境配置
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"📍 访问地址: http://0.0.0.0:{port}")
    # 使用 socketio.run 替代 app.run
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)


# ==================== 生产环境配置 ====================

# PythonAnywhere 部署时不使用 debug 模式
# 如果检测到在生产环境
if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('PYTHONANYWHERE'):
    app.config['DEBUG'] = False
    # 生产环境使用固定的 secret key
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'production-secret-key-change-this')