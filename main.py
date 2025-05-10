

# Импорт необходимых библиотек
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from wtforms.validators import DataRequired
from datetime import datetime
import os
from flask_wtf import FlaskForm
import schedule
from flask import Flask, jsonify, request, render_template_string, redirect, url_for, abort, send_from_directory
import time
from wtforms import StringField, TextAreaField, SubmitField, DateField, SelectField, FileField
import threading

# Создание Flask-приложения
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diary.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
db = SQLAlchemy(app)

# Создание папки для загрузок, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Модель записи в дневнике
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, nullable=False)
    mood = db.Column(db.String(50), nullable=False)
    tags = db.Column(db.String(200))
    image = db.Column(db.String(100))
    likes = db.Column(db.Integer, default=0)

# Модель комментария
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=False)
    author = db.Column(db.String(80), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

# Форма для создания и редактирования записей
class EntryForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired()])
    content = TextAreaField('Запись', validators=[DataRequired()])
    date = DateField('Дата', validators=[DataRequired()], default=datetime.today)
    mood = SelectField('Настроение', choices=[
        ('Весёлый', '😊 Весёлый'),
        ('Грустный', '😢 Грустный'),
        ('Радостный', '🤩 Радостный'),
        ('Уставший', '😴 Уставший'),
        ('Злой', '😠 Злой'),
    ], validators=[DataRequired()])
    tags = StringField('Тэги')
    image = FileField('Прикрепить картинку')
    submit = SubmitField('Создать запись')

# Форма для комментариев
class CommentForm(FlaskForm):
    author = StringField('Author', validators=[DataRequired()])
    text = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Add Comment')

# Проверка допустимого формата файла
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

index_html = """
<!doctype html>
<html lang='ru'>
<head><meta charset='UTF-8'><title>Мой Дневник</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f0f2f5; padding: 20px; }
h1, h2, h3 { color: #333; }
form, .card { background: #fff; padding: 15px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
input, textarea, select { width: 100%; padding: 8px; margin: 5px 0 10px 0; border: 1px solid #ccc; border-radius: 4px; }
ul { list-style-type: none; padding: 0; }
li { background: #fff; margin: 5px 0; padding: 10px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
a { text-decoration: none; color: #007BFF; }
a:hover { text-decoration: underline; }
button, input[type='submit'] { background-color: #007BFF; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
button:hover, input[type='submit']:hover { background-color: #0056b3; }
.stats { margin-top: 20px; background: #e2e6ea; padding: 10px; border-radius: 6px; }
.tag { display: inline-block; background: #e2e6ea; padding: 2px 8px; border-radius: 10px; margin-right: 5px; font-size: 0.8em; }
.entry-image { max-width: 100%; max-height: 300px; margin-top: 10px; }
.search-form { margin-bottom: 20px; }
.like-btn { background: none; border: none; color: #666; cursor: pointer; font-size: 1.2em; }
.like-btn.liked { color: #ff4757; }
</style>
</head>
<body>
<h1>📓 Мой Личный Дневник</h1>

<div class="search-form">
<form method="get" action="{{ url_for('search_entries') }}">
<input type="text" name="q" placeholder="Поиск записей..." value="{{ search_query }}">
<button type="submit">Искать</button>
</form>
</div>

<h2>Добавить запись</h2>
<form method="post" action="{{ url_for('index') }}" enctype="multipart/form-data">
{{ form.hidden_tag() }}
{{ form.title.label }} {{ form.title() }}
{{ form.content.label }} {{ form.content() }}
{{ form.date.label }} {{ form.date() }}
{{ form.mood.label }} {{ form.mood() }}
{{ form.tags.label }} {{ form.tags(placeholder="работа, отпуск, идеи") }}
{{ form.image.label }} {{ form.image() }}
{{ form.submit() }}
</form>

<h2>Записи</h2>
{% if not entries %}
<p>Записей пока нет. Добавьте первую запись выше!</p>
{% else %}
<ul>
{% for entry in entries %}
<li>
<strong><a href="/entry/{{ entry.id }}">{{ entry.title }}</a></strong>
({{ entry.date }} — Настроение: {{ entry.mood }})
{% if entry.tags %}
<div>{% for tag in entry.tags.split(',') %}<span class="tag">{{ tag.strip() }}</span>{% endfor %}</div>
{% endif %}
<div style="margin-top:5px;">
<button class="like-btn {% if entry.likes > 0 %}liked{% endif %}" 
        onclick="likeEntry({{ entry.id }})">❤ {{ entry.likes if entry.likes > 0 else '' }}</button>
</div>
</li>
{% endfor %}
</ul>
{% endif %}

<div class="stats">
<h3>📊 Статистика</h3>
<p>Всего записей: {{ stats.total_entries }}</p>
<p>Всего комментариев: {{ stats.total_comments }}</p>
<p>Самый активный день: {{ stats.most_active_day }}</p>
<p>Чаще всего настроение: {{ stats.most_used_mood }}</p>
</div>

<script>
function likeEntry(entryId) {
    fetch(`/entry/${entryId}/like`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        });
}
</script>
</body>
</html>

"""

entry_detail_html = """
<!doctype html>
<html lang='ru'>
<head><meta charset='UTF-8'><title>{{ entry.title }}</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f0f2f5; padding: 20px; }
h1, h2 { color: #333; }
.card { background: #fff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
form { margin-top: 20px; }
input, textarea { width: 100%; padding: 8px; margin: 5px 0 10px 0; border: 1px solid #ccc; border-radius: 4px; }
ul { list-style-type: none; padding: 0; }
li { background: #fff; margin: 5px 0; padding: 10px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
a { text-decoration: none; color: #007BFF; }
a:hover { text-decoration: underline; }
button, input[type='submit'] { background-color: #007BFF; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
button:hover, input[type='submit']:hover { background-color: #0056b3; }
.tag { display: inline-block; background: #e2e6ea; padding: 2px 8px; border-radius: 10px; margin-right: 5px; font-size: 0.8em; }
.entry-image { max-width: 100%; max-height: 300px; margin-top: 10px; }
.edit-btn { background-color: #28a745; margin-right: 10px; }
.like-btn { background: none; border: none; color: #666; cursor: pointer; font-size: 1.2em; margin-right: 10px; }
.like-btn.liked { color: #ff4757; }
.comment-meta { font-size: 0.8em; color: #666; margin-bottom: 5px; }
</style>
</head>
<body>
<div class="card">
<h1>{{ entry.title }}</h1>
<p><strong>Дата:</strong> {{ entry.date }}</p>
<p><strong>Настроение:</strong> {{ entry.mood }}</p>
{% if entry.tags %}
<p><strong>Теги:</strong> {% for tag in entry.tags.split(',') %}<span class="tag">{{ tag.strip() }}</span>{% endfor %}</p>
{% endif %}
{% if entry.image %}
<img src="{{ url_for('uploaded_file', filename=entry.image) }}" class="entry-image">
{% endif %}
<p>{{ entry.content }}</p>
<div style="margin-top: 15px;">
<button class="like-btn {% if entry.likes > 0 %}liked{% endif %}" 
        onclick="likeEntry({{ entry.id }})">❤ {{ entry.likes if entry.likes > 0 else 'Лайк' }}</button>
<a href="/entry/{{ entry.id }}/edit" class="edit-btn">✏ Редактировать</a>
<form action="/entry/{{ entry.id }}/delete" method="post" style="display:inline;">
<input type="submit" value="🗑 Удалить" onclick="return confirm('Вы уверены?');">
</form>
</div>
</div>

<h2>Добавить комментарий</h2>
<form method="post">
{{ form.hidden_tag() }}
{{ form.author.label }} {{ form.author() }}
{{ form.text.label }} {{ form.text() }}
{{ form.submit() }}
</form>

<h2>Комментарии ({{ comments|length }})</h2>
{% if not comments %}
<p>Комментариев пока нет. Будьте первым!</p>
{% else %}
<ul>
{% for comment in comments %}
<li>
<div class="comment-meta">
<strong>{{ comment.author }}</strong> в {{ comment.timestamp.strftime('%Y-%m-%d %H:%M') }}
<form action="/comment/{{ comment.id }}/delete" method="post" style="display:inline; margin-left:10px;">
<input type="submit" value="Удалить" onclick="return confirm('Удалить этот комментарий?');">
</form>
</div>
<p>{{ comment.text }}</p>
</li>
{% endfor %}
</ul>
{% endif %}

<p><a href="/">⬅ Назад на главную</a></p>

<script>
function likeEntry(entryId) {
    fetch(`/entry/${entryId}/like`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        });
}
</script>
</body>
</html>

"""

edit_entry_html = """
<!doctype html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Edit Entry</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f0f2f5; padding: 20px; }
h1, h2 { color: #333; }
form, .card { background: #fff; padding: 15px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
input, textarea, select { width: 100%; padding: 8px; margin: 5px 0 10px 0; border: 1px solid #ccc; border-radius: 4px; }
a { text-decoration: none; color: #007BFF; }
a:hover { text-decoration: underline; }
button, input[type='submit'] { background-color: #007BFF; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
button:hover, input[type='submit']:hover { background-color: #0056b3; }
.tag { display: inline-block; background: #e2e6ea; padding: 2px 8px; border-radius: 10px; margin-right: 5px; font-size: 0.8em; }
.entry-image { max-width: 100%; max-height: 300px; margin-top: 10px; }
</style>
</head>
<body>
<h1>Edit Entry</h1>

<form method="post" enctype="multipart/form-data">
{{ form.hidden_tag() }}
{{ form.title.label }} {{ form.title() }}
{{ form.content.label }} {{ form.content() }}
{{ form.date.label }} {{ form.date() }}
{{ form.mood.label }} {{ form.mood() }}
{{ form.tags.label }} {{ form.tags() }}

{% if entry.image %}
<div>
    <p>Current image:</p>
    <img src="{{ url_for('uploaded_file', filename=entry.image) }}" class="entry-image">
    <label>
        <input type="checkbox" name="remove_image"> Remove image
    </label>
</div>
{% endif %}

{{ form.image.label }} {{ form.image() }}

{{ form.submit() }}
</form>

<p><a href="{{ url_for('entry_detail', entry_id=entry.id) }}">⬅ Back to entry</a></p>
</body>
</html>
"""

# Главная страница: отображение и добавление записей
@app.route('/', methods=['GET', 'POST'])
def index():
    form = EntryForm()
    if form.validate_on_submit():
        file = request.files.get('image')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        entry = Entry(
            title=form.title.data,
            content=form.content.data,
            date=form.date.data,
            mood=form.mood.data,
            tags=form.tags.data,
            image=filename
        )
        db.session.add(entry)
        db.session.commit()
        return redirect(url_for('index'))

    entries = Entry.query.order_by(Entry.date.desc()).all()
    total_entries = Entry.query.count()
    total_comments = Comment.query.count()

    # Вычисление статистики
    most_active_day = db.session.query(
        db.func.strftime('%Y-%m-%d', Entry.date),
        db.func.count(Entry.id)
    ).group_by(db.func.strftime('%Y-%m-%d', Entry.date)) \
        .order_by(db.func.count(Entry.id).desc()).first()

    most_used_mood = db.session.query(
        Entry.mood,
        db.func.count(Entry.id)
    ).group_by(Entry.mood) \
        .order_by(db.func.count(Entry.id).desc()).first()

    stats = {
        'total_entries': total_entries,
        'total_comments': total_comments,
        'most_active_day': most_active_day[0] if most_active_day else 'N/A',
        'most_used_mood': most_used_mood[0] if most_used_mood else 'N/A'
    }

    return render_template_string(index_html, form=form, entries=entries, stats=stats, search_query='')

# Поиск записей
@app.route('/search')
def search_entries():
    query = request.args.get('q', '')
    if query:
        entries = Entry.query.filter(
            Entry.title.contains(query) |
            Entry.content.contains(query) |
            Entry.tags.contains(query)
        ).order_by(Entry.date.desc()).all()
    else:
        entries = Entry.query.order_by(Entry.date.desc()).all()

    total_entries = Entry.query.count()
    total_comments = Comment.query.count()

    most_active_day = db.session.query(
        db.func.strftime('%Y-%m-%d', Entry.date),
        db.func.count(Entry.id)
    ).group_by(db.func.strftime('%Y-%m-%d', Entry.date)) \
        .order_by(db.func.count(Entry.id).desc()).first()

    most_used_mood = db.session.query(
        Entry.mood,
        db.func.count(Entry.id)
    ).group_by(Entry.mood) \
        .order_by(db.func.count(Entry.id).desc()).first()

    stats = {
        'total_entries': total_entries,
        'total_comments': total_comments,
        'most_active_day': most_active_day[0] if most_active_day else 'N/A',
        'most_used_mood': most_used_mood[0] if most_used_mood else 'N/A'
    }

    return render_template_string(index_html, form=EntryForm(), entries=entries, stats=stats, search_query=query)

# Просмотр отдельной записи и добавление комментариев
@app.route('/entry/<int:entry_id>', methods=['GET', 'POST'])
def entry_detail(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    form = CommentForm()

    if form.validate_on_submit():
        comment = Comment(entry_id=entry.id, author=form.author.data, text=form.text.data)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('entry_detail', entry_id=entry.id))

    comments = Comment.query.filter_by(entry_id=entry.id).order_by(Comment.timestamp.desc()).all()
    return render_template_string(entry_detail_html, entry=entry, form=form, comments=comments)

# Редактирование записи
@app.route('/entry/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    form = EntryForm(obj=entry)

    if form.validate_on_submit():
        entry.title = form.title.data
        entry.content = form.content.data
        entry.date = form.date.data
        entry.mood = form.mood.data
        entry.tags = form.tags.data

        # Загрузка нового изображения
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '' and allowed_file(file.filename):
                if entry.image:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], entry.image))
                    except OSError:
                        pass
                filename = secure_filename(f"{entry_id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                entry.image = filename

        # Удаление текущего изображения
        if 'remove_image' in request.form and request.form['remove_image'] == 'on':
            if entry.image:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], entry.image))
                except OSError:
                    pass
                entry.image = None

        db.session.commit()
        return redirect(url_for('entry_detail', entry_id=entry.id))

    return render_template_string(edit_entry_html, entry=entry, form=form)

# Удаление записи
@app.route('/entry/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)

    if entry.image:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], entry.image))
        except OSError:
            pass

    Comment.query.filter_by(entry_id=entry.id).delete()
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('index'))

# Лайк записи
@app.route('/entry/<int:entry_id>/like', methods=['POST'])
def like_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    entry.likes += 1
    db.session.commit()
    return jsonify({'success': True})

# Удаление комментария
@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    entry_id = comment.entry_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('entry_detail', entry_id=entry_id))

# Получение загруженных файлов
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- API эндпоинты ---

# Получить все записи
@app.route('/api/entries', methods=['GET'])
def api_get_entries():
    entries = Entry.query.all()
    return jsonify([{
        'id': e.id,
        'title': e.title,
        'content': e.content,
        'date': e.date.isoformat(),
        'mood': e.mood,
        'tags': e.tags,
        'likes': e.likes,
        'image': e.image
    } for e in entries])

# Получить одну запись
@app.route('/api/entry/<int:entry_id>', methods=['GET'])
def api_get_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    return jsonify({
        'id': entry.id,
        'title': entry.title,
        'content': entry.content,
        'date': entry.date.isoformat(),
        'mood': entry.mood,
        'tags': entry.tags,
        'likes': entry.likes,
        'image': entry.image
    })

# Создать запись через API
@app.route('/api/entry', methods=['POST'])
def api_create_entry():
    data = request.json
    entry = Entry(
        title=data['title'],
        content=data['content'],
        date=datetime.strptime(data['date'], '%Y-%m-%d'),
        mood=data['mood'],
        tags=data.get('tags', ''),
        likes=0
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Entry created', 'id': entry.id}), 201

# Обновить запись через API
@app.route('/api/entry/<int:entry_id>', methods=['PUT'])
def api_update_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    data = request.json
    entry.title = data.get('title', entry.title)
    entry.content = data.get('content', entry.content)
    if 'date' in data:
        entry.date = datetime.strptime(data['date'], '%Y-%m-%d')
    entry.mood = data.get('mood', entry.mood)
    entry.tags = data.get('tags', entry.tags)
    db.session.commit()
    return jsonify({'message': 'Entry updated'})

# Удалить запись через API
@app.route('/api/entry/<int:entry_id>', methods=['DELETE'])
def api_delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    Comment.query.filter_by(entry_id=entry.id).delete()
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'message': 'Entry deleted'})

# Лайк через API
@app.route('/api/entry/<int:entry_id>/like', methods=['POST'])
def api_like_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    entry.likes += 1
    db.session.commit()
    return jsonify({'message': 'Entry liked', 'likes': entry.likes})

# Получить комментарии через API
@app.route('/api/entry/<int:entry_id>/comments', methods=['GET'])
def api_get_comments(entry_id):
    comments = Comment.query.filter_by(entry_id=entry_id).all()
    return jsonify([{
        'id': c.id,
        'author': c.author,
        'text': c.text,
        'timestamp': c.timestamp.isoformat()
    } for c in comments])

# Добавить комментарий через API
@app.route('/api/entry/<int:entry_id>/comment', methods=['POST'])
def api_add_comment(entry_id):
    data = request.json
    comment = Comment(
        entry_id=entry_id,
        author=data['author'],
        text=data['text']
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify({'message': 'Comment added', 'id': comment.id}), 201

# Функция для расчёта статистики (выводит в консоль)
def calculate_diary_stats():
    with app.app_context():
        total_entries = Entry.query.count()
        total_comments = Comment.query.count()
        print(f"[Stats] Entries: {total_entries}, Comments: {total_comments}")

# Планировщик задач с библиотекой schedule
def run_scheduler():
    schedule.every(1).hour.do(calculate_diary_stats)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Запуск приложения
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    threading.Thread(target=run_scheduler, daemon=True).start()
    app.run(debug=True)
