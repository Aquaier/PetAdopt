from flask import Flask, request, jsonify, send_from_directory
import mysql.connector
from flask_cors import CORS
import bcrypt
from flask import session
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
import os

# Inicjalizacja aplikacji Flask
app = Flask(__name__)
CORS(app)
app.secret_key = 'super_secret_key'  

# Funkcja pomocnicza do połączenia z bazą danych MySQL
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='16213303',
        database='petadopt'
    )

# Strona główna API
@app.route('/')
def home():
    return jsonify({'message': 'Welcome to the PetAdopt API!'})

# Funkcja do haszowania hasła
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Funkcja do sprawdzania hasła
def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Funkcja do walidacji emaila
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(email):
    return EMAIL_REGEX.match(email) is not None

# Funkcja do walidacji siły hasła (min. 6 znaków, litera i cyfra)
def is_strong_password(password):
    if len(password) < 6:
        return False
    if not re.search(r"[A-Za-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True

# Funkcja do generowania losowego hasła
def generate_random_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# Funkcja do wysyłania maila z nowym hasłem
def send_reset_email(recipient_email, new_password):
    smtp_servers = [
        {
            'host': 'smtp.gmail.com',
            'port': 587,
            'user': 'apppetadopt@gmail.com',
            'password': 'PetAdopt2025!',
        },
    ]
    subject = 'Reset hasła - PetAdopt'
    body = f'Twoje nowe hasło do konta PetAdopt: {new_password}\nZaloguj się i zmień hasło w ustawieniach.'
    for smtp in smtp_servers:
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp['user']
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP(smtp['host'], smtp['port'])
            server.starttls()
            server.login(smtp['user'], smtp['password'])
            server.sendmail(smtp['user'], recipient_email, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            continue
    return False

# Endpoint logowania użytkownika
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Wprowadź e-mail i hasło'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM uzytkownicy WHERE email=%s', (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not user.get('haslo_hash'):
        return jsonify({'success': False, 'message': 'Nieprawidłowy email lub hasło'}), 401

    if not check_password(password, user['haslo_hash']):
        return jsonify({'success': False, 'message': 'Nieprawidłowy email lub hasło'}), 401

    session['user_id'] = user['id']
    session['email'] = user['email']
    return jsonify({'success': True, 'user': {'id': user['id'], 'email': user['email'], 'czy_schronisko': user['czy_schronisko']}})


# Endpoint rejestracji użytkownika
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not is_valid_email(email):
        return jsonify({'success': False, 'message': 'Niepoprawny adres e-mail. E-mail musi zawierać znak "@" i być poprawny.'}), 400
    if not is_strong_password(password):
        return jsonify({'success': False, 'message': 'Hasło musi mieć min. 6 znaków, zawierać literę i cyfrę.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM uzytkownicy WHERE email=%s', (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Email już istnieje'}), 409
    hashed = hash_password(password)
    cursor.execute('INSERT INTO uzytkownicy (email, haslo_hash, czy_schronisko) VALUES (%s, %s, %s)', (email, hashed, False))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

# Endpoint wylogowania użytkownika
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Wylogowano'})

# Endpoint testowy połączenia z bazą danych
@app.route('/test-db', methods=['GET'])
def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Połączenie z bazą danych działa.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Endpoint resetu hasła
@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')
    if not is_valid_email(email):
        return jsonify({'success': False, 'message': 'Niepoprawny adres e-mail.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM uzytkownicy WHERE email=%s', (email,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika o podanym adresie e-mail.'}), 404
    new_password = generate_random_password()
    hashed = hash_password(new_password)
    cursor.execute('UPDATE uzytkownicy SET haslo_hash=%s WHERE email=%s', (hashed, email))
    conn.commit()
    cursor.close()
    conn.close()
    if send_reset_email(email, new_password):
        return jsonify({'success': True, 'message': 'Nowe hasło zostało wysłane na Twój e-mail.'})
    else:
        return jsonify({'success': False, 'message': 'Nie udało się wysłać e-maila. Skontaktuj się z administratorem.'}), 500

# Endpoint pobierania listy zwierząt
@app.route('/animals', methods=['GET'])
def get_animals():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Pobierz zwierzęta wraz z emailem właściciela i województwem (z obu typów profili)
    cursor.execute('''
        SELECT z.id, z.gatunek, z.rasa, z.tytul, z.imie, z.wiek, z.waga, z.opis, z.zdjecie_url, u.email as owner_email,
               COALESCE(ps.wojewodztwo, pp.wojewodztwo) as wojewodztwo
        FROM zwierzeta z
        JOIN uzytkownicy u ON z.uzytkownik_id = u.id
        LEFT JOIN profile_schronisk ps ON ps.uzytkownik_id = u.id
        LEFT JOIN profile_prywatne pp ON pp.uzytkownik_id = u.id
    ''')
    animals = cursor.fetchall()
    cursor.close()
    conn.close()
    import random
    random.shuffle(animals)
    for animal in animals:
        if animal['zdjecie_url']:
            filename = os.path.basename(animal['zdjecie_url'])
            animal['zdjecie_url'] = f'{request.host_url}images/{filename}'
    return jsonify({'success': True, 'animals': animals})

# Endpoint dodawania nowego zwierzaka
@app.route('/animals', methods=['POST'])
def add_animal():
    print('--- [DEBUG] add_animal wywołane ---')
    tytul = request.form.get('tytul')
    gatunek = request.form.get('gatunek')
    rasa = request.form.get('rasa')
    wiek = request.form.get('wiek')
    waga = request.form.get('waga')
    opis = request.form.get('opis')
    owner_email = request.form.get('owner_email')
    imie = request.form.get('imie')
    image = request.files.get('zdjecie')
    print(f'--- [DEBUG] Dane: tytul={tytul}, gatunek={gatunek}, rasa={rasa}, wiek={wiek}, waga={waga}, opis={opis}, owner_email={owner_email}, imie={imie}, image={image}')
    zdjecie_url = None
    if image:
        images_dir = os.path.join(os.path.dirname(__file__), 'images')
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        filename = f"{random.randint(100000,999999)}_{image.filename}"
        filepath = os.path.join(images_dir, filename)
        image.save(filepath)
        zdjecie_url = f"{request.host_url}images/{filename}"
        print(f'--- [DEBUG] Zdjęcie zapisane: {filepath}')
    conn = get_db_connection()
    try:
        # Pobierz uzytkownik_id na podstawie emaila
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (owner_email,))
        user = cursor.fetchone()
        print(f'--- [DEBUG] Wynik SELECT id FROM uzytkownicy: {user}')
        if not user:
            print('--- [DEBUG] Nie znaleziono użytkownika o podanym emailu ---')
            return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika o podanym emailu.'}), 400
        uzytkownik_id = user['id']
        
        # Wstaw zwierzaka
        cursor.execute('''INSERT INTO zwierzeta (uzytkownik_id, tytul, gatunek, rasa, wiek, waga, opis, zdjecie_url, imie)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (uzytkownik_id, tytul, gatunek, rasa, wiek, waga, opis, zdjecie_url, imie))
        conn.commit()
    except Exception as e:
        print(f'--- [DEBUG] Błąd podczas dodawania zwierzaka: {str(e)} ---')
        return jsonify({'success': False, 'message': 'Błąd podczas dodawania zwierzaka.'}), 500
    finally:
        cursor.close()
        conn.close()
    print('--- [DEBUG] Zwierzak dodany do bazy ---')
    return jsonify({'success': True, 'message': 'Zwierzak dodany!'})

# Endpoint serwowania zdjęć zwierząt
@app.route('/images/<filename>')
def serve_image(filename):
    images_dir = os.path.join(os.path.dirname(__file__), 'images')
    response = send_from_directory(images_dir, filename)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

# Endpoint pobierania numeru telefonu właściciela ogłoszenia
@app.route('/user-phone')
def get_user_phone():
    email = request.args.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Brak adresu e-mail.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Pobierz id użytkownika
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (email,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika.'}), 404
    user_id = user['id']
    # Najpierw sprawdź profil schroniska
    cursor.execute('SELECT telefon FROM profile_schronisk WHERE uzytkownik_id=%s', (user_id,))
    schronisko = cursor.fetchone()
    if schronisko and schronisko.get('telefon'):
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'phone': schronisko['telefon']})
    # Potem sprawdź profil prywatny
    cursor.execute('SELECT telefon FROM profile_prywatne WHERE uzytkownik_id=%s', (user_id,))
    prywatny = cursor.fetchone()
    cursor.close()
    conn.close()
    if prywatny and prywatny.get('telefon'):
        return jsonify({'success': True, 'phone': prywatny['telefon']})
    return jsonify({'success': False, 'message': 'Nie znaleziono numeru telefonu.'}), 404

# Endpoint pobierania listy rozmów użytkownika
@app.route('/conversations', methods=['GET'])
def get_conversations():
    email = request.args.get('user_email')
    if not email:
        return jsonify({'success': False, 'message': 'Brak adresu e-mail.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (email,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika.'}), 404
    user_id = user['id']
    # Pobierz wszystkie id zwierząt wystawionych przez użytkownika
    cursor.execute('SELECT id FROM zwierzeta WHERE uzytkownik_id=%s', (user_id,))
    animals = cursor.fetchall()
    animal_ids = [a['id'] for a in animals]
    # Pobierz rozmowy, w których użytkownik jest stroną (jako uzytkownik1_id/uzytkownik2_id) lub jest właścicielem zwierzęcia
    if animal_ids:
        format_strings = ','.join(['%s'] * len(animal_ids))
        cursor.execute(f'''
            SELECT r.id, u1.email as user1_email, u2.email as user2_email, r.zwierze_id
            FROM rozmowy r
            JOIN uzytkownicy u1 ON r.uzytkownik1_id = u1.id
            JOIN uzytkownicy u2 ON r.uzytkownik2_id = u2.id
            WHERE r.uzytkownik1_id = %s OR r.uzytkownik2_id = %s OR r.zwierze_id IN ({format_strings})
        ''', tuple([user_id, user_id] + animal_ids))
    else:
        cursor.execute('''
            SELECT r.id, u1.email as user1_email, u2.email as user2_email, r.zwierze_id
            FROM rozmowy r
            JOIN uzytkownicy u1 ON r.uzytkownik1_id = u1.id
            JOIN uzytkownicy u2 ON r.uzytkownik2_id = u2.id
            WHERE r.uzytkownik1_id = %s OR r.uzytkownik2_id = %s
        ''', (user_id, user_id))
    conversations = cursor.fetchall()
    # Dodaj ostatnią wiadomość do każdej rozmowy oraz tytuł ogłoszenia
    for c in conversations:
        cursor.execute('''SELECT tresc, czas_wyslania FROM wiadomosci WHERE rozmowa_id=%s ORDER BY czas_wyslania DESC LIMIT 1''', (c['id'],))
        last_msg = cursor.fetchone()
        if last_msg:
            c['last_message'] = last_msg['tresc']
            c['last_message_time'] = last_msg['czas_wyslania']
        else:
            c['last_message'] = ''
            c['last_message_time'] = None
        # Pobierz tytuł ogłoszenia
        cursor.execute('SELECT tytul FROM zwierzeta WHERE id=%s', (c['zwierze_id'],))
        animal = cursor.fetchone()
        c['tytul'] = animal['tytul'] if animal else ''
    cursor.close()
    conn.close()
    # Zwróć listę rozmówców (email) i id rozmowy
    result = []
    for c in conversations:
        if c['user1_email'] == email:
            other_email = c['user2_email']
        elif c['user2_email'] == email:
            other_email = c['user1_email']
        else:
            other_email = f"{c['user1_email']} / {c['user2_email']}"
        result.append({'conversation_id': c['id'], 'with': other_email, 'zwierze_id': c['zwierze_id'], 'tytul': c['tytul'], 'last_message': c['last_message'], 'last_message_time': c['last_message_time']})
    return jsonify({'success': True, 'conversations': result})

# Endpoint pobierania wiadomości z rozmowy
@app.route('/messages', methods=['GET'])
def get_messages():
    conversation_id = request.args.get('conversation_id')
    if not conversation_id:
        return jsonify({'success': False, 'message': 'Brak id rozmowy.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT w.id, w.nadawca_id, u.email as sender_email, w.tresc, w.czas_wyslania
        FROM wiadomosci w
        JOIN uzytkownicy u ON w.nadawca_id = u.id
        WHERE w.rozmowa_id = %s
        ORDER BY w.czas_wyslania ASC
    ''', (conversation_id,))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'messages': messages})

# Endpoint wysyłania wiadomości
@app.route('/messages', methods=['POST'])
def send_message():
    data = request.get_json()
    conversation_id = data.get('conversation_id')
    sender_email = data.get('sender_email')
    text = data.get('text')
    if not conversation_id or not sender_email or not text:
        return jsonify({'success': False, 'message': 'Brak wymaganych danych.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Pobierz id nadawcy
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (sender_email,))
    sender = cursor.fetchone()
    if not sender:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika.'}), 404
    sender_id = sender['id']
    # Sprawdź czy rozmowa istnieje
    cursor.execute('SELECT id FROM rozmowy WHERE id=%s', (conversation_id,))
    conversation = cursor.fetchone()
    if not conversation:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono rozmowy.'}), 404
    # Dodaj wiadomość
    cursor.execute('INSERT INTO wiadomosci (rozmowa_id, nadawca_id, tresc) VALUES (%s, %s, %s)',
        (conversation_id, sender_id, text))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'conversation_id': conversation_id})
    
# Endpoint usuwania ogłoszenia o zwierzaku
@app.route('/animals/<int:animal_id>', methods=['DELETE'])
def delete_animal(animal_id):
    owner_email = request.args.get('owner_email')
    if not owner_email:
        return jsonify({'success': False, 'message': 'Brak adresu e-mail właściciela.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Pobierz id użytkownika
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (owner_email,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika.'}), 404
    user_id = user['id']
    # Sprawdź czy zwierzę istnieje i należy do użytkownika
    cursor.execute('SELECT zdjecie_url FROM zwierzeta WHERE id=%s AND uzytkownik_id=%s', (animal_id, user_id))
    animal = cursor.fetchone()
    if not animal:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono ogłoszenia lub brak uprawnień.'}), 404
    # Usuń zdjęcie z dysku jeśli istnieje
    zdjecie_url = animal.get('zdjecie_url')
    if zdjecie_url:
        filename = os.path.basename(zdjecie_url)
        images_dir = os.path.join(os.path.dirname(__file__), 'images')
        filepath = os.path.join(images_dir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    # Usuń zwierzę
    cursor.execute('DELETE FROM zwierzeta WHERE id=%s', (animal_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'message': 'Ogłoszenie usunięte.'})

# Endpoint edycji ogłoszenia o zwierzaku
@app.route('/animals/<int:animal_id>', methods=['PUT'])
def update_animal(animal_id):
    owner_email = request.form.get('owner_email')
    if not owner_email:
        return jsonify({'success': False, 'message': 'Brak adresu e-mail właściciela.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Pobierz id użytkownika
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (owner_email,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika.'}), 404
    user_id = user['id']
    # Sprawdź czy zwierzę istnieje i należy do użytkownika
    cursor.execute('SELECT zdjecie_url FROM zwierzeta WHERE id=%s AND uzytkownik_id=%s', (animal_id, user_id))
    animal = cursor.fetchone()
    if not animal:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono ogłoszenia lub brak uprawnień.'}), 404
    # Pobierz dane do aktualizacji
    tytul = request.form.get('tytul')
    gatunek = request.form.get('gatunek')
    rasa = request.form.get('rasa')
    wiek = request.form.get('wiek')
    waga = request.form.get('waga')
    opis = request.form.get('opis')
    imie = request.form.get('imie')
    image = request.files.get('zdjecie')
    zdjecie_url = animal.get('zdjecie_url')
    # Jeśli przesłano nowe zdjęcie, usuń stare i zapisz nowe
    if image:
        if zdjecie_url:
            filename = os.path.basename(zdjecie_url)
            images_dir = os.path.join(os.path.dirname(__file__), 'images')
            filepath = os.path.join(images_dir, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
        images_dir = os.path.join(os.path.dirname(__file__), 'images')
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        filename = f"{random.randint(100000,999999)}_{image.filename}"
        filepath = os.path.join(images_dir, filename)
        image.save(filepath)
        zdjecie_url = f"{request.host_url}images/{filename}"
    # Aktualizuj rekord
    cursor.execute('''UPDATE zwierzeta SET tytul=%s, gatunek=%s, rasa=%s, wiek=%s, waga=%s, opis=%s, zdjecie_url=%s, imie=%s WHERE id=%s''',
                   (tytul, gatunek, rasa, wiek, waga, opis, zdjecie_url, imie, animal_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'message': 'Ogłoszenie zaktualizowane!'})
    
# Endpoint tworzenia lub pobierania rozmowy
@app.route('/conversations', methods=['POST'])
def create_or_get_conversation():
    data = request.get_json()
    user1_email = data.get('user1_email')
    user2_email = data.get('user2_email')
    zwierze_id = data.get('zwierze_id')
    if not user1_email or not user2_email or not zwierze_id:
        return jsonify({'success': False, 'message': 'Brak wymaganych danych.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Pobierz id użytkowników
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (user1_email,))
    user1 = cursor.fetchone()
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (user2_email,))
    user2 = cursor.fetchone()
    if not user1 or not user2:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika.'}), 404
    user1_id = user1['id']
    user2_id = user2['id']
    # Sprawdź czy rozmowa już istnieje
    cursor.execute('''SELECT id FROM rozmowy WHERE ((uzytkownik1_id=%s AND uzytkownik2_id=%s) OR (uzytkownik1_id=%s AND uzytkownik2_id=%s)) AND zwierze_id=%s''',
        (user1_id, user2_id, user2_id, user1_id, zwierze_id))
    conversation = cursor.fetchone()
    if conversation:
        conversation_id = conversation['id']
    else:
        cursor.execute('INSERT INTO rozmowy (zwierze_id, uzytkownik1_id, uzytkownik2_id) VALUES (%s, %s, %s)',
            (zwierze_id, user1_id, user2_id))
        conn.commit()
        conversation_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'conversation_id': conversation_id})
    
# Endpoint usuwania użytkownika i jego ogłoszeń
@app.route('/delete-user', methods=['DELETE'])
def delete_user():
    email = request.args.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Brak adresu e-mail.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Pobierz id użytkownika
    cursor.execute('SELECT id FROM uzytkownicy WHERE email=%s', (email,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Nie znaleziono użytkownika.'}), 404
    user_id = user['id']
    # Usuń wszystkie zwierzęta użytkownika
    cursor.execute('DELETE FROM zwierzeta WHERE uzytkownik_id=%s', (user_id,))
    # Usuń użytkownika
    cursor.execute('DELETE FROM uzytkownicy WHERE id=%s', (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'message': 'Konto i ogłoszenia zostały usunięte.'})

# Uruchomienie aplikacji Flask
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

