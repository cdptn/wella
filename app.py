import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Needed for session management

DATABASE = 'desk_booking.db'

# Database connection setup
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

# Close database connection
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Initialize the database with the required schema
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Create the bookings table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                desk TEXT NOT NULL,
                date TEXT NOT NULL,
                user TEXT NOT NULL
            )
        ''')

        # Create the users table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        ''')

        db.commit()

# Home Route
@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('desk_map'))  # Redirect to desk map if logged in
    return render_template('home.html')  # Show the home page if not logged in

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()

        # Check if the username exists
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

        if user:
            # Check if the password matches
            if check_password_hash(user[2], password):
                session['user'] = user[1]  # Store the username in the session
                return redirect(url_for('desk_map'))
            else:
                flash('Invalid password')
                return redirect(url_for('login'))
        else:
            flash('Username does not exist')
            return redirect(url_for('login'))

    return render_template('login.html')

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        db = get_db()
        cursor = db.cursor()

        # Check if username already exists
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Username already exists')
        else:
            # Insert the new user into the users table
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            db.commit()
            flash('Registration successful, please login')
            return redirect(url_for('login'))

    return render_template('register.html')

# Password Reset Route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['new_password']
        hashed_password = generate_password_hash(new_password)

        db = get_db()
        cursor = db.cursor()

        # Check if username exists
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

        if user:
            # Update the password
            cursor.execute('UPDATE users SET password = ? WHERE username = ?', (hashed_password, username))
            db.commit()
            flash('Password reset successful, please login')
            return redirect(url_for('login'))
        else:
            flash('Username not found')

    return render_template('forgot_password.html')

# Desk Map Route (Displays the desk availability map with date filtering)
@app.route('/desk_map', methods=['GET'])
def desk_map():
    if 'user' not in session:
        return redirect(url_for('login'))

    selected_date = request.args.get('date')

    # If no date is selected, use today's date as default
    if not selected_date:
        selected_date = date.today().isoformat()

    # Calculate previous and next days
    selected_date_obj = date.fromisoformat(selected_date)
    previous_day = (selected_date_obj - timedelta(days=1)).isoformat()
    next_day = (selected_date_obj + timedelta(days=1)).isoformat()

    db = get_db()
    cursor = db.cursor()

    # Get all booked desks and the users who booked them for the selected date
    cursor.execute('SELECT desk, user FROM bookings WHERE date = ?', (selected_date,))
    bookings = cursor.fetchall()

    booked_desks = {str(row[0]): row[1] for row in bookings}  # Create a dictionary {desk: user}

    # Render the desk map with booked desk info, users, and the selected date
    return render_template('desk_map.html', 
                           booked_desks=booked_desks, 
                           selected_date=selected_date, 
                           previous_day=previous_day, 
                           next_day=next_day)

# Booking a desk route (prevents booking more than one desk per day)
@app.route('/book_desk', methods=['POST'])
def book_desk():
    if 'user' not in session:
        return redirect(url_for('login'))

    desk = request.form.get('desk')
    booking_date = request.form.get('date')
    user = session['user']  # Get the logged-in user from the session

    # Check if the user already has a booking on the selected date
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM bookings WHERE date = ? AND user = ?', (booking_date, user))
    existing_booking = cursor.fetchone()

    if existing_booking:
        return f"Error: You have already booked a desk for {booking_date}."

    # Insert the booking if available
    cursor.execute('INSERT INTO bookings (desk, date, user) VALUES (?, ?, ?)', (desk, booking_date, user))
    db.commit()

    return redirect(f'/desk_map?date={booking_date}')

# View Bookings Route (to view current bookings)
@app.route('/my_bookings')
def my_bookings():
    if 'user' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT desk, date FROM bookings WHERE user = ?', (session['user'],))
    bookings = cursor.fetchall()

    return render_template('my_bookings.html', bookings=bookings)

# Logout route to clear session
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
