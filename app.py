from flask import Flask, render_template, flash, redirect, url_for, request, session, jsonify, abort
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
import os
from datetime import datetime
from models import db, User, Post, Comment, Like, Experience, Education, Skill, Message, Connection


app = Flask(__name__)
app.config['SECRET_KEY'] = 'linkedin-clone-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///linkedin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Eğer uploads klasörü yoksa oluştur
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Ana sayfa - Feed
@app.route('/')
def index():
    if current_user.is_authenticated:
        posts = current_user.followed_posts()
    else:
        posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()
    return render_template('index.html', title='Ana Sayfa', posts=posts)

# Kayıt ol
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Kullanıcı adı veya e-posta zaten kullanılıyor mu kontrol et
        user_exists = User.query.filter((User.username == username) | (User.email == email)).first()
        if user_exists:
            flash('Kullanıcı adı veya e-posta zaten kullanılıyor.')
            return redirect(url_for('register'))
        
        # Yeni kullanıcı oluştur
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Tebrikler, hesabınız oluşturuldu!')
        return redirect(url_for('login'))
    
    return render_template('register.html', title='Kayıt Ol')

# Giriş yap
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash('Geçersiz e-posta veya şifre.')
            return redirect(url_for('login'))
        
        login_user(user, remember=('remember_me' in request.form))
        flash('Başarıyla giriş yaptınız!')
        
        # Kullanıcı login öncesi başka bir sayfaya erişmeye çalıştıysa o sayfaya yönlendir
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('index')
        return redirect(next_page)
    
    return render_template('login.html', title='Giriş Yap')

# Çıkış yap
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# Profil sayfası
@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.created_at.desc()).all()
    experiences = Experience.query.filter_by(user_id=user.id).order_by(Experience.start_date.desc()).all()
    educations = Education.query.filter_by(user_id=user.id).order_by(Education.start_date.desc()).all()
    skills = Skill.query.filter_by(user_id=user.id).all()
    
    # Bağlantı durumunu kontrol et
    connection = None
    if current_user.is_authenticated and current_user.id != user.id:
        connection = Connection.query.filter(
            ((Connection.user_id == current_user.id) & (Connection.connected_id == user.id)) |
            ((Connection.user_id == user.id) & (Connection.connected_id == current_user.id))
        ).first()
    
    return render_template('profile.html', user=user, posts=posts, 
                           experiences=experiences, educations=educations, 
                           skills=skills, connection=connection)

# Profil düzenleme
@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.headline = request.form['headline']
        current_user.bio = request.form['bio']
        current_user.location = request.form['location']
        current_user.industry = request.form['industry']
        
        # Profil resmi yükleme
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                current_user.profile_pic = filename
        
        db.session.commit()
        flash('Profiliniz güncellendi!')
        return redirect(url_for('profile', username=current_user.username))
    
    return render_template('edit_profile.html', title='Profili Düzenle')

# Yeni gönderi oluştur
@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        content = request.form['content']
        
        post = Post(content=content, author=current_user)
        
        # Gönderiye resim ekleme
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                post.image_url = filename
        
        db.session.add(post)
        db.session.commit()
        flash('Gönderi oluşturuldu!')
        return redirect(url_for('index'))
    
    return render_template('create_post.html', title='Gönderi Oluştur')

# Gönderi sil
@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    
    db.session.delete(post)
    db.session.commit()
    flash('Gönderi silindi!')
    return redirect(url_for('index'))

# Gönderiyi beğen/beğenmekten vazgeç
@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({"status": "unliked", "likes": post.likes.count()})
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()
        return jsonify({"status": "liked", "likes": post.likes.count()})

# Yorumlar
@app.route('/post/<int:post_id>/comments', methods=['GET', 'POST'])
@login_required
def post_comments(post_id):
    post = Post.query.get_or_404(post_id)
    
    if request.method == 'POST':
        content = request.form['content']
        comment = Comment(content=content, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        flash('Yorumunuz eklendi!')
    
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.desc()).all()
    return render_template('post_comments.html', post=post, comments=comments)

# İş deneyimi ekle
@app.route('/add_experience', methods=['GET', 'POST'])
@login_required
def add_experience():
    if request.method == 'POST':
        title = request.form['title']
        company = request.form['company']
        location = request.form['location']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        
        # Bitiş tarihi belirtilmişse al, belirtilmemişse None olarak bırak
        end_date = None
        if request.form['end_date'] and request.form['end_date'] != "":
            end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        
        description = request.form['description']
        
        experience = Experience(
            title=title,
            company=company,
            location=location,
            start_date=start_date,
            end_date=end_date,
            description=description,
            user_id=current_user.id
        )
        
        db.session.add(experience)
        db.session.commit()
        flash('İş deneyimi eklendi!')
        return redirect(url_for('profile', username=current_user.username))
    
    return render_template('add_experience.html', title='İş Deneyimi Ekle')

# Eğitim bilgisi ekle
@app.route('/add_education', methods=['GET', 'POST'])
@login_required
def add_education():
    if request.method == 'POST':
        school = request.form['school']
        degree = request.form['degree']
        field_of_study = request.form['field_of_study']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        
        # Bitiş tarihi belirtilmişse al, belirtilmemişse None olarak bırak
        end_date = None
        if request.form['end_date'] and request.form['end_date'] != "":
            end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        
        description = request.form['description']
        
        education = Education(
            school=school,
            degree=degree,
            field_of_study=field_of_study,
            start_date=start_date,
            end_date=end_date,
            description=description,
            user_id=current_user.id
        )
        
        db.session.add(education)
        db.session.commit()
        flash('Eğitim bilgisi eklendi!')
        return redirect(url_for('profile', username=current_user.username))
    
    return render_template('add_education.html', title='Eğitim Bilgisi Ekle')

# Yetenek ekle
@app.route('/add_skill', methods=['GET', 'POST'])
@login_required
def add_skill():
    if request.method == 'POST':
        name = request.form['name']
        
        skill = Skill(name=name, user_id=current_user.id)
        db.session.add(skill)
        db.session.commit()
        flash('Yetenek eklendi!')
        return redirect(url_for('profile', username=current_user.username))
    
    return render_template('add_skill.html', title='Yetenek Ekle')

# Kullanıcı ara
@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        users = User.query.filter(User.username.like(f'%{query}%') | 
                                 User.headline.like(f'%{query}%') | 
                                 User.location.like(f'%{query}%')).all()
    else:
        users = []
    
    return render_template('search_results.html', users=users, query=query)

# Bağlantı istekleri
@app.route('/connections')
@login_required
def connections():
    # Gelen bağlantı istekleri
    incoming_requests = Connection.query.filter_by(connected_id=current_user.id, status='pending').all()
    
    # Gönderilen bağlantı istekleri
    outgoing_requests = Connection.query.filter_by(user_id=current_user.id, status='pending').all()
    
    # Kabul edilen bağlantılar
    accepted_connections = Connection.query.filter(
        ((Connection.user_id == current_user.id) | (Connection.connected_id == current_user.id)) & 
        (Connection.status == 'accepted')
    ).all()
    
    return render_template('connections.html', 
                          incoming_requests=incoming_requests,
                          outgoing_requests=outgoing_requests,
                          accepted_connections=accepted_connections)

# Bağlantı isteği gönder
@app.route('/send_connection_request/<int:user_id>', methods=['POST'])
@login_required
def send_connection_request(user_id):
    user = User.query.get_or_404(user_id)
    
    if user == current_user:
        flash('Kendinize bağlantı isteği gönderemezsiniz!')
        return redirect(url_for('profile', username=user.username))
    
    # Zaten bağlantı isteği var mı kontrol et
    existing_connection = Connection.query.filter(
        ((Connection.user_id == current_user.id) & (Connection.connected_id == user_id)) |
        ((Connection.user_id == user_id) & (Connection.connected_id == current_user.id))
    ).first()
    
    if existing_connection:
        flash('Bu kullanıcıyla zaten bir bağlantı isteği mevcut!')
        return redirect(url_for('profile', username=user.username))
    
    connection = Connection(user_id=current_user.id, connected_id=user_id)
    db.session.add(connection)
    db.session.commit()
    flash(f'{user.username} kullanıcısına bağlantı isteği gönderildi!')
    return redirect(url_for('profile', username=user.username))

# Bağlantı isteğini kabul et
@app.route('/accept_connection/<int:connection_id>', methods=['POST'])
@login_required
def accept_connection(connection_id):
    connection = Connection.query.get_or_404(connection_id)
    
    if connection.connected_id != current_user.id:
        abort(403)
    
    connection.status = 'accepted'
    db.session.commit()
    flash('Bağlantı isteği kabul edildi!')
    return redirect(url_for('connections'))

# Bağlantı isteğini reddet
@app.route('/reject_connection/<int:connection_id>', methods=['POST'])
@login_required
def reject_connection(connection_id):
    connection = Connection.query.get_or_404(connection_id)
    
    if connection.connected_id != current_user.id:
        abort(403)
    
    connection.status = 'rejected'
    db.session.commit()
    flash('Bağlantı isteği reddedildi!')
    return redirect(url_for('connections'))

# Mesaj gönderme
@app.route('/send_message/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def send_message(recipient_id):
    recipient = User.query.get_or_404(recipient_id)
    
    if request.method == 'POST':
        content = request.form['content']
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            content=content
        )
        db.session.add(message)
        db.session.commit()
        flash(f'{recipient.username} kullanıcısına mesaj gönderildi!')
        return redirect(url_for('messages'))
    
    return render_template('send_message.html', recipient=recipient)

# Mesajları görüntüle
@app.route('/messages')
@login_required
def messages():
    # Kullanıcının mesajlaştığı diğer kullanıcıları bul
    user_messages = db.session.query(Message).filter(
        (Message.sender_id == current_user.id) | (Message.recipient_id == current_user.id)
    ).order_by(Message.timestamp.desc()).all()
    
    contacts = {}
    for message in user_messages:
        other_user_id = message.sender_id if message.recipient_id == current_user.id else message.recipient_id
        if other_user_id not in contacts:
            contacts[other_user_id] = {
                'user': User.query.get(other_user_id),
                'last_message': message
            }
    
    return render_template('messages.html', contacts=contacts)

# Mesaj konuşması görüntüle
@app.route('/conversation/<int:user_id>')
@login_required
def conversation(user_id):
    user = User.query.get_or_404(user_id)
    
    # İki kullanıcı arasındaki mesajları al
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    # Okunmamış mesajları okundu olarak işaretle
    for message in messages:
        if message.recipient_id == current_user.id and not message.read:
            message.read = True
    
    db.session.commit()
    
    return render_template('conversation.html', user=user, messages=messages)

# Bildirimler
@app.route('/notifications')
@login_required
def notifications():
    # Okunmamış mesajlar
    unread_messages = Message.query.filter_by(recipient_id=current_user.id, read=False).all()
    
    # Bağlantı istekleri
    connection_requests = Connection.query.filter_by(connected_id=current_user.id, status='pending').all()
    
    return render_template('notifications.html', 
                          unread_messages=unread_messages,
                          connection_requests=connection_requests)

# Veritabanını oluştur
#@app.before_first_request
#def create_tables():
#    db.create_all()


@app.context_processor
def inject_now():
    return {'now': datetime.now()}

@app.context_processor
def utility_functions():
    def connection_status(user_id, connected_id):
        return Connection.query.filter(
            ((Connection.user_id == user_id) & (Connection.connected_id == connected_id)) |
            ((Connection.user_id == connected_id) & (Connection.connected_id == user_id))
        ).first()
    
    return dict(connection_status=connection_status)





if __name__ == '__main__':
    app.run(debug=True)