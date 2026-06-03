"""
================================================================================
                    B U I L D C R U M B . C O M
         The social platform for the CRUMB ecosystem.
         Every device gets a number. Every builder gets a profile.
================================================================================
"""

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, abort, Response)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import re

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
app.config['SECRET_KEY']                  = os.environ.get('SECRET_KEY', 'dev-only-change-in-production')

# Render's managed Postgres can hand back a postgres:// URL; SQLAlchemy 2.0
# (used by flask-sqlalchemy 3.1) only accepts the postgresql:// scheme. Normalise
# it so the same code runs on SQLite locally and Postgres in production.
database_url = os.environ.get('DATABASE_URL', 'sqlite:///crumb.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI']     = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

FOUNDER_LIMIT    = 100
RATE_LIMIT_MAX   = 5          # max registration attempts
RATE_LIMIT_WINDOW = 3600      # per hour (seconds)

# ── Extensions ────────────────────────────────────────────────────────────────
db           = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ── Models ────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer,     primary_key=True)
    username      = db.Column(db.String(40),  unique=True,  nullable=False)
    email         = db.Column(db.String(120), unique=True,  nullable=False)
    password_hash = db.Column(db.String(256),              nullable=False)
    crumb_number  = db.Column(db.Integer,     unique=True)
    is_founder    = db.Column(db.Boolean,     default=False)
    bio           = db.Column(db.String(300), default='')
    location      = db.Column(db.String(100), default='')
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    devices       = db.relationship('Device', backref='owner', lazy=True,
                                    cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def crumb_tag(self):
        return f"#{str(self.crumb_number).zfill(4)}"

    @property
    def days_member(self):
        return (datetime.utcnow() - self.created_at).days


class Device(db.Model):
    id          = db.Column(db.Integer,    primary_key=True)
    user_id     = db.Column(db.Integer,    db.ForeignKey('user.id'), nullable=False)
    name        = db.Column(db.String(80), nullable=False)
    device_type = db.Column(db.String(30), default='custom')
    description = db.Column(db.String(300), default='')
    added_at    = db.Column(db.DateTime,   default=datetime.utcnow)


class AccessCode(db.Model):
    id       = db.Column(db.Integer,    primary_key=True)
    code     = db.Column(db.String(24), unique=True, nullable=False)
    used     = db.Column(db.Boolean,    default=False)
    used_by  = db.Column(db.Integer,    db.ForeignKey('user.id'), nullable=True)
    used_at  = db.Column(db.DateTime,   nullable=True)


class RegistrationAttempt(db.Model):
    """Tracks failed registration attempts per IP for rate limiting."""
    id         = db.Column(db.Integer,    primary_key=True)
    ip_address = db.Column(db.String(48), nullable=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Builds models ───────────────────────────────────────────────────────────────

class Forum(db.Model):
    id          = db.Column(db.Integer,     primary_key=True)
    name        = db.Column(db.String(80),  nullable=False)
    slug        = db.Column(db.String(80),  unique=True, nullable=False)
    description = db.Column(db.String(300), default='')
    icon        = db.Column(db.String(8),   default='⚡')
    is_pinned   = db.Column(db.Boolean,     default=False)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)
    posts       = db.relationship('Post', backref='forum', lazy=True)


class Post(db.Model):
    id            = db.Column(db.Integer,     primary_key=True)
    user_id       = db.Column(db.Integer,     db.ForeignKey('user.id'),  nullable=False)
    forum_id      = db.Column(db.Integer,     db.ForeignKey('forum.id'), nullable=False)
    title         = db.Column(db.String(160), nullable=False)
    description   = db.Column(db.Text,        default='')
    hardware_list = db.Column(db.Text,        default='')
    wiring        = db.Column(db.Text,        default='')
    time_to_build = db.Column(db.String(60),  default='')
    difficulty    = db.Column(db.Integer,     default=1)       # 1–5
    images        = db.Column(db.Text,        default='')      # up to 5 comma-separated URLs
    code          = db.Column(db.Text,        nullable=True)   # optional
    code_approved = db.Column(db.Boolean,     default=False)
    vote_score    = db.Column(db.Integer,     default=0)
    is_pinned     = db.Column(db.Boolean,     default=False)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    author        = db.relationship('User', backref='posts', lazy=True)
    comments      = db.relationship('Comment', backref='post', lazy=True,
                                    cascade='all, delete-orphan')


class Comment(db.Model):
    id         = db.Column(db.Integer,  primary_key=True)
    user_id    = db.Column(db.Integer,  db.ForeignKey('user.id'),    nullable=False)
    post_id    = db.Column(db.Integer,  db.ForeignKey('post.id'),    nullable=False)
    parent_id  = db.Column(db.Integer,  db.ForeignKey('comment.id'), nullable=True)
    body       = db.Column(db.Text,     nullable=False)
    vote_score = db.Column(db.Integer,  default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author     = db.relationship('User', backref='comments', lazy=True)
    replies    = db.relationship('Comment', lazy=True,
                                 backref=db.backref('parent', remote_side=[id]),
                                 cascade='all, delete-orphan')


class Vote(db.Model):
    id         = db.Column(db.Integer,  primary_key=True)
    user_id    = db.Column(db.Integer,  db.ForeignKey('user.id'),    nullable=False)
    post_id    = db.Column(db.Integer,  db.ForeignKey('post.id'),    nullable=True)
    comment_id = db.Column(db.Integer,  db.ForeignKey('comment.id'), nullable=True)
    value      = db.Column(db.Integer,  nullable=False)              # 1 or -1
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id',    name='uq_vote_user_post'),
        db.UniqueConstraint('user_id', 'comment_id', name='uq_vote_user_comment'),
    )


class Download(db.Model):
    """Audit trail — who downloaded which build's code."""
    id            = db.Column(db.Integer,  primary_key=True)
    user_id       = db.Column(db.Integer,  db.ForeignKey('user.id'), nullable=False)
    post_id       = db.Column(db.Integer,  db.ForeignKey('post.id'), nullable=False)
    downloaded_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Builds helpers ──────────────────────────────────────────────────────────────

VALID_SORTS = ('new', 'top', 'hot')


@app.template_filter('timeago')
def timeago(dt):
    """Human-readable relative time, e.g. '5m ago'."""
    if not dt:
        return ''
    secs = (datetime.utcnow() - dt).total_seconds()
    if secs < 60:
        return 'just now'
    mins = secs / 60
    if mins < 60:
        return f'{int(mins)}m ago'
    hrs = mins / 60
    if hrs < 24:
        return f'{int(hrs)}h ago'
    days = hrs / 24
    if days < 30:
        return f'{int(days)}d ago'
    if days < 365:
        return f'{int(days / 30)}mo ago'
    return f'{int(days / 365)}y ago'


def slugify(text):
    text = re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')
    return text[:60]


def order_posts(posts, sort):
    """Pinned posts first, then by the chosen sort (new / top / hot)."""
    now = datetime.utcnow()

    def hotness(p):
        age_h = max((now - p.created_at).total_seconds() / 3600, 0)
        return p.vote_score / ((age_h + 2) ** 1.5)

    if sort == 'top':
        posts.sort(key=lambda p: (p.is_pinned, p.vote_score, p.created_at), reverse=True)
    elif sort == 'hot':
        posts.sort(key=lambda p: (p.is_pinned, hotness(p), p.created_at), reverse=True)
    else:  # new
        posts.sort(key=lambda p: (p.is_pinned, p.created_at), reverse=True)
    return posts


def post_votes_map(user, posts):
    """{post_id: value} for the current user across the given posts."""
    if not getattr(user, 'is_authenticated', False) or not posts:
        return {}
    ids = [p.id for p in posts]
    rows = Vote.query.filter(Vote.user_id == user.id, Vote.post_id.in_(ids)).all()
    return {r.post_id: r.value for r in rows}


def comment_votes_map(user, comment_ids):
    """{comment_id: value} for the current user across the given comments."""
    if not getattr(user, 'is_authenticated', False) or not comment_ids:
        return {}
    rows = Vote.query.filter(Vote.user_id == user.id, Vote.comment_id.in_(comment_ids)).all()
    return {r.comment_id: r.value for r in rows}


def apply_vote(user, value, post=None, comment=None):
    """Cast a vote with toggle semantics — one vote per user per thing.
    Same direction again removes it; the opposite direction switches it."""
    if value not in (1, -1):
        return
    target = post if post is not None else comment
    if post is not None:
        existing = Vote.query.filter_by(user_id=user.id, post_id=post.id).first()
    else:
        existing = Vote.query.filter_by(user_id=user.id, comment_id=comment.id).first()

    if existing is None:
        db.session.add(Vote(
            user_id=user.id, value=value,
            post_id=post.id if post is not None else None,
            comment_id=comment.id if comment is not None else None,
        ))
        target.vote_score += value
    elif existing.value == value:
        target.vote_score -= existing.value          # toggle off
        db.session.delete(existing)
    else:
        target.vote_score += value - existing.value  # switch direction (±2)
        existing.value = value
    db.session.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    # Every builder, oldest number first — feeds the live network ticker.
    users = User.query.order_by(User.crumb_number.asc()).all()
    stats = {
        'builders': User.query.count(),
        'devices':  Device.query.count(),
        'founders': User.query.filter_by(is_founder=True).count(),
        'spots':    max(0, FOUNDER_LIMIT - User.query.count()),
    }
    return render_template('index.html', users=users, stats=stats)


@app.route('/discover')
def discover():
    q     = request.args.get('q', '').strip()
    query = User.query
    if q:
        query = query.filter(User.username.ilike(f'%{q}%'))
    users = query.order_by(User.crumb_number.asc()).all()
    return render_template('discover.html', users=users, q=q)


@app.route('/constitution')
def constitution():
    return render_template('constitution.html')


@app.route('/get-started')
def get_started():
    return render_template('get_started.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('profile', username=current_user.username))

    if request.method == 'POST':
        # ── Rate limiting ─────────────────────────────────────────────────────
        # Max 5 registration attempts per IP per hour
        # This makes brute forcing access codes computationally impossible
        ip = request.remote_addr or '0.0.0.0'
        window_start = datetime.utcnow() - timedelta(seconds=RATE_LIMIT_WINDOW)
        recent_attempts = RegistrationAttempt.query.filter(
            RegistrationAttempt.ip_address == ip,
            RegistrationAttempt.attempted_at > window_start
        ).count()
        if recent_attempts >= RATE_LIMIT_MAX:
            flash('Too many registration attempts. Please try again in an hour.', 'error')
            return render_template('register.html', form=request.form)
        username = request.form.get('username','').strip().lower()
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        code     = request.form.get('code','').strip().upper()
        bio      = request.form.get('bio','').strip()
        location = request.form.get('location','').strip()

        # ── Validation ────────────────────────────────────────────────────────
        errors = []
        if not all([username, email, password, code]):
            errors.append('All fields are required.')
        if username and (len(username) < 3 or len(username) > 30):
            errors.append('Username must be 3-30 characters.')
        if username and not username.replace('_','').replace('-','').isalnum():
            errors.append('Username may only contain letters, numbers, - and _.')
        if password and len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.query.filter_by(username=username).first():
            errors.append('That username is already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('That email is already registered.')

        # ── Code validation ───────────────────────────────────────────────────
        access_code = AccessCode.query.filter_by(code=code, used=False).first()
        if not access_code:
            # Log this failed attempt for rate limiting
            db.session.add(RegistrationAttempt(ip_address=ip))
            db.session.commit()
            errors.append('That access code is invalid or has already been used.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html', form=request.form)

        # ── Create user ───────────────────────────────────────────────────────
        crumb_number = User.query.count() + 1
        is_founder   = crumb_number <= FOUNDER_LIMIT

        user = User(
            username     = username,
            email        = email,
            crumb_number = crumb_number,
            is_founder   = is_founder,
            bio          = bio[:300],
            location     = location[:100],
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        access_code.used    = True
        access_code.used_by = user.id
        access_code.used_at = datetime.utcnow()
        db.session.commit()

        login_user(user, remember=True)

        if is_founder:
            flash(f'Welcome, {username}. You are Founding Member {user.crumb_tag}.', 'success')
        else:
            flash(f'Welcome to CRUMB, {username}. You are {user.crumb_tag}.', 'success')

        return redirect(url_for('profile', username=username))

    return render_template('register.html', form={})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile', username=current_user.username))

    if request.method == 'POST':
        username = request.form.get('username','').strip().lower()
        password = request.form.get('password','')
        user     = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            nxt = request.args.get('next')
            return redirect(nxt or url_for('profile', username=user.username))

        flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/u/<username>')
def profile(username):
    user    = User.query.filter_by(username=username).first_or_404()
    devices = Device.query.filter_by(user_id=user.id).order_by(Device.added_at.asc()).all()
    is_own  = current_user.is_authenticated and current_user.id == user.id
    return render_template('profile.html', user=user, devices=devices, is_own=is_own)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio      = request.form.get('bio','').strip()[:300]
        current_user.location = request.form.get('location','').strip()[:100]
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('profile', username=current_user.username))
    return render_template('profile_edit.html')


@app.route('/device/add', methods=['POST'])
@login_required
def add_device():
    name        = request.form.get('name','').strip()[:80]
    device_type = request.form.get('device_type','custom')
    description = request.form.get('description','').strip()[:300]

    if name:
        device = Device(
            user_id     = current_user.id,
            name        = name,
            device_type = device_type,
            description = description,
        )
        db.session.add(device)
        db.session.commit()
        flash(f'{name} added to your ecosystem.', 'success')

    return redirect(url_for('profile', username=current_user.username))


@app.route('/device/remove/<int:device_id>', methods=['POST'])
@login_required
def remove_device(device_id):
    device = Device.query.get_or_404(device_id)
    if device.user_id == current_user.id:
        db.session.delete(device)
        db.session.commit()
        flash(f'{device.name} removed.', 'success')
    return redirect(url_for('profile', username=current_user.username))


# ── Builds routes ───────────────────────────────────────────────────────────────

@app.route('/builds')
def builds():
    sort = request.args.get('sort', 'new')
    if sort not in VALID_SORTS:
        sort = 'new'
    forums = Forum.query.order_by(Forum.is_pinned.desc(), Forum.created_at.asc()).all()
    posts = order_posts(Post.query.all(), sort)
    return render_template('builds.html', forums=forums, posts=posts, sort=sort,
                           user_votes=post_votes_map(current_user, posts))


@app.route('/builds/post/new', methods=['GET', 'POST'])
@login_required
def builds_post_new():
    forums = Forum.query.order_by(Forum.is_pinned.desc(), Forum.created_at.asc()).all()
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        forum       = Forum.query.get(request.form.get('forum_id', type=int))
        difficulty  = request.form.get('difficulty', type=int) or 1
        difficulty  = max(1, min(5, difficulty))
        images      = [request.form.get(f'image{i}', '').strip() for i in range(1, 6)]
        images      = ','.join([u for u in images if u][:5])
        code        = request.form.get('code', '').strip()

        errors = []
        if not title:
            errors.append('A title is required.')
        if not description:
            errors.append('A description is required.')
        if not forum:
            errors.append('Choose a forum.')
        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('builds_new.html', forums=forums, form=request.form)

        post = Post(
            user_id=current_user.id, forum_id=forum.id,
            title=title[:160], description=description,
            hardware_list=request.form.get('hardware_list', '').strip(),
            wiring=request.form.get('wiring', '').strip(),
            time_to_build=request.form.get('time_to_build', '').strip()[:60],
            difficulty=difficulty, images=images, code=(code or None),
        )
        db.session.add(post)
        db.session.commit()
        flash('Your build is live.', 'success')
        return redirect(url_for('builds_post', id=post.id))

    return render_template('builds_new.html', forums=forums, form={})


@app.route('/builds/post/<int:id>')
def builds_post(id):
    post = Post.query.get_or_404(id)

    # Build threaded comments: top-level in order, all descendants flattened
    # to one visual level (unlimited depth preserved via the parent_id chain).
    all_comments = Comment.query.filter_by(post_id=post.id).all()
    children = {}
    for c in all_comments:
        children.setdefault(c.parent_id, []).append(c)
    for group in children.values():
        group.sort(key=lambda c: c.created_at)
    top_level = children.get(None, [])
    top_level.sort(key=lambda c: (c.vote_score, c.created_at), reverse=True)

    def descendants(parent):
        out = []
        for child in children.get(parent.id, []):
            out.append(child)
            out.extend(descendants(child))
        return out

    threads = [{'top': t, 'replies': descendants(t)} for t in top_level]

    return render_template(
        'builds_post.html', post=post, threads=threads,
        post_vote=post_votes_map(current_user, [post]).get(post.id),
        comment_votes=comment_votes_map(current_user, [c.id for c in all_comments]),
    )


@app.route('/builds/post/<int:id>/vote', methods=['POST'])
@login_required
def builds_post_vote(id):
    post = Post.query.get_or_404(id)
    apply_vote(current_user, request.form.get('value', type=int), post=post)
    return redirect(request.form.get('next') or request.referrer
                    or url_for('builds_post', id=id))


@app.route('/builds/comment/<int:id>/vote', methods=['POST'])
@login_required
def builds_comment_vote(id):
    comment = Comment.query.get_or_404(id)
    apply_vote(current_user, request.form.get('value', type=int), comment=comment)
    return redirect(request.form.get('next') or request.referrer
                    or url_for('builds_post', id=comment.post_id))


@app.route('/builds/post/<int:id>/comment', methods=['POST'])
@login_required
def builds_comment(id):
    post = Post.query.get_or_404(id)
    body = request.form.get('body', '').strip()
    parent_id = request.form.get('parent_id', type=int)
    if body:
        parent = Comment.query.get(parent_id) if parent_id else None
        if parent and parent.post_id != post.id:
            parent = None  # never let a reply jump to another post's thread
        db.session.add(Comment(
            user_id=current_user.id, post_id=post.id,
            parent_id=parent.id if parent else None, body=body,
        ))
        db.session.commit()
    return redirect(url_for('builds_post', id=post.id) + '#comments')


@app.route('/builds/post/<int:id>/download')
@login_required
def builds_download(id):
    post = Post.query.get_or_404(id)
    if not post.code or not post.code_approved:
        flash('That code is still under review — not available to download yet.', 'error')
        return redirect(url_for('builds_post', id=id))
    db.session.add(Download(user_id=current_user.id, post_id=post.id))
    db.session.commit()
    filename = slugify(post.title) or f'crumb-build-{post.id}'
    resp = Response(post.code, mimetype='text/plain; charset=utf-8')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}.txt"'
    return resp


@app.route('/builds/admin/review', methods=['GET', 'POST'])
@login_required
def builds_review():
    if current_user.username != 'wyetherp':          # hardcoded admin for now
        abort(403)
    if request.method == 'POST':
        post = Post.query.get(request.form.get('post_id', type=int))
        if post:
            post.code_approved = True
            db.session.commit()
            flash(f'Approved code for "{post.title}".', 'success')
        return redirect(url_for('builds_review'))
    posts = (Post.query
             .filter(Post.code.isnot(None), Post.code != '', Post.code_approved == False)
             .order_by(Post.created_at.desc()).all())
    return render_template('builds_review.html', posts=posts)


@app.route('/builds/<slug>')
def builds_forum(slug):
    forum = Forum.query.filter_by(slug=slug).first_or_404()
    sort = request.args.get('sort', 'new')
    if sort not in VALID_SORTS:
        sort = 'new'
    posts = order_posts(Post.query.filter_by(forum_id=forum.id).all(), sort)
    return render_template('builds_forum.html', forum=forum, posts=posts, sort=sort,
                           user_votes=post_votes_map(current_user, posts))


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


# ── Seed + init ─────────────────────────────────────────────────────────────────

def seed_builds():
    """Create the starter forums and the three founding builds. Idempotent —
    safe to call on every boot; it checks for existence before inserting."""
    if not Forum.query.filter_by(slug='ember').first():
        db.session.add(Forum(
            name='Ember', slug='ember', icon='🜂', is_pinned=True,
            description='Extensions and builds for Ember — The Oracle. '
                        'Every post here becomes part of what Ember can be.',
        ))
    if not Forum.query.filter_by(slug='community').first():
        db.session.add(Forum(
            name='Community Builds', slug='community', icon='⚡', is_pinned=False,
            description='Everything the community is making.',
        ))
    db.session.commit()

    ember   = Forum.query.filter_by(slug='ember').first()
    founder = User.query.filter_by(crumb_number=1).first()
    if not (ember and founder):
        return  # the founding builds are authored by CRUMB #0001 — skip until it exists

    seed_posts = [
        dict(
            title='Ember — The Oracle',
            is_pinned=True, difficulty=3, time_to_build='1 weekend', images='',
            description=(
                "Ember is the brain of the CRUMB ecosystem. A Raspberry Pi running a "
                "custom pygame interface with an emotional face, Claude AI integration, "
                "MQTT ecosystem broadcasting, and a dark fantasy UI. It discovers "
                "connected devices automatically, plays a birthday song generated from "
                "pure mathematics, and serves as the hub every other CRUMB device "
                "reports to. This is the first build. Everything else connects here."
            ),
            hardware_list='\n'.join([
                'Raspberry Pi 4 (4GB)',
                '7 inch DSI touchscreen',
                'USB microphone',
                'USB speaker',
                'Wooden chest enclosure',
                'MicroSD card (32GB+)',
            ]),
            wiring=(
                "Screen connects via DSI ribbon cable to Pi. USB mic connects to USB "
                "port (card 2). USB speaker connects to USB port (card 1). Power via "
                "USB-C to Pi. Everything lives inside the chest — power cable exits "
                "through a hole in the back."
            ),
        ),
        dict(
            title='Ignis — The Light Bringer',
            is_pinned=False, difficulty=2, time_to_build='2 hours', images='',
            description=(
                "An ESP32 microcontroller driving 300 WS2812B LEDs across 16.4 feet. "
                "Ignis connects to Ember automatically over WiFi via MQTT and responds "
                "to color commands, runs seven ambient lighting effects, and displays a "
                "visual countdown bar when Ember's timer is running. It announces itself "
                "to Ember on boot and sends a heartbeat every 25 seconds. The room "
                "changes color when Ember's mood changes. Nobody touches a switch."
            ),
            hardware_list='\n'.join([
                'ESP32 Dev Module',
                'BTF-LIGHTING ECO WS2812B 16.4ft 300 LED strip (GRB)',
                '5V USB charger (2A+)',
                'USB cable (sacrificed for power)',
                '220 ohm resistor',
                'Hot glue for connections',
            ]),
            wiring='\n'.join([
                'Strip 5V → USB charger 5V (direct)',
                'Strip GND → USB charger GND + ESP32 GND (shared)',
                'Strip DATA → 220 ohm resistor → ESP32 GPIO 4',
                'ESP32 powered separately via USB. Critical: COLOR_ORDER is GRB not RGB '
                'on BTF-LIGHTING ECO strips.',
            ]),
        ),
        dict(
            title='Morpheus — The Dream Keeper',
            is_pinned=False, difficulty=2, time_to_build='2 hours', images='',
            description=(
                "An ESP32 with a 16-LED WS2812B ring and a 0.96 inch OLED screen. Lives "
                "on the nightstand. Knows what time it is via NTP sync. Dims at 9pm "
                "without being asked. Begins a 20-minute sunrise fade at 5:40am. When "
                "Ember sends a message, it appears on the OLED screen within 2 seconds. "
                "At 10pm it drops to 3 percent brightness — a barely visible ember glow — "
                "and tells Ignis to rest. Nobody told it to. It just knows."
            ),
            hardware_list='\n'.join([
                'ESP32 Dev Module',
                '16-LED WS2812B ring',
                '0.96 inch I2C OLED display (128x64, SSD1306)',
                'DuPont wires',
            ]),
            wiring='\n'.join([
                'OLED GND → ESP32 GND',
                'OLED VCC → ESP32 3.3V',
                'OLED SCL → ESP32 GPIO 22',
                'OLED SDA → ESP32 GPIO 21',
                'LED Ring 5V → ESP32 VIN',
                'LED Ring GND → ESP32 GND',
                'LED Ring DIN → 220 ohm → ESP32 GPIO 4',
                'Single USB cable powers everything — 16 LEDs at moderate brightness '
                'draws under 500mA which the ESP32 5V pin handles.',
            ]),
        ),
    ]

    for sp in seed_posts:
        if not Post.query.filter_by(title=sp['title'], forum_id=ember.id).first():
            db.session.add(Post(user_id=founder.id, forum_id=ember.id,
                                code=None, code_approved=False, **sp))
    db.session.commit()


def init_db():
    db.create_all()
    seed_builds()


# Run on import so tables exist + seed data is present under any launcher
# (python app.py, gunicorn, or tests). All seeding is existence-checked.
with app.app_context():
    init_db()


if __name__ == '__main__':
    with app.app_context():
        if AccessCode.query.count() == 0:
            print("No access codes found. Run generate_codes.py first.")
    debug_mode = os.environ.get('FLASK_DEBUG', 'False') == 'True'
    app.run(debug=debug_mode,
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)))
